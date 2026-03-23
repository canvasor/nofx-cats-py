from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
import uuid

from cats_py.app.bootstrap import RuntimeModeSummary
from cats_py.config.settings import AppConfig, RuntimeMode, SymbolConfig
from cats_py.connectors.nofx.normalizers import normalize_coin_snapshot
from cats_py.domain.enums import DecisionStatus, MarketRegime, OrderType
from cats_py.domain.models import AccountSnapshot, AccountState, FeatureVector, TradeDecision
from cats_py.journal.recorder import JournalRecorder
from cats_py.services.decision_engine import DecisionEngine
from cats_py.services.paper_execution import PaperExecutionService
from cats_py.services.reconciliation import AccountReconciler


@dataclass(slots=True)
class NofxRequestStats:
    api_requests: int = 0
    cache_hits: int = 0


@dataclass(slots=True)
class CachedPayload:
    payload: dict[str, object]
    fetched_at: datetime


@dataclass(slots=True)
class DecisionRuntimeResult:
    cycle_id: str
    account_state: AccountState
    decisions: list[TradeDecision]
    request_stats: NofxRequestStats = field(default_factory=NofxRequestStats)


class NofxClientProtocol(Protocol):
    async def coin(self, symbol: str) -> dict[str, object]: ...

    async def funding_rate(self, symbol: str) -> dict[str, object]: ...

    async def heatmap_future(self, symbol: str) -> dict[str, object]: ...


def _object_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _int_config(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


class DecisionRuntimeService:
    def __init__(
        self,
        *,
        nofx: NofxClientProtocol,
        decision_engine: DecisionEngine,
        reconciler: AccountReconciler,
        journal: JournalRecorder,
        app_config: AppConfig,
        symbol_config: SymbolConfig,
        mode_summary: RuntimeModeSummary,
        paper_execution: PaperExecutionService | None = None,
    ) -> None:
        self.nofx = nofx
        self.decision_engine = decision_engine
        self.reconciler = reconciler
        self.journal = journal
        self.app_config = app_config
        self.symbol_config = symbol_config
        self.mode_summary = mode_summary
        self.paper_execution = paper_execution
        self.response_cache: dict[tuple[str, str], CachedPayload] = {}
        collectors = _object_mapping(app_config.nofx.get("collectors", {}))
        self.coin_ttl_seconds = _int_config(
            collectors.get("coin_interval_seconds"), app_config.core_loop_interval_seconds
        )
        self.funding_ttl_seconds = _int_config(
            collectors.get("funding_interval_seconds"), app_config.core_loop_interval_seconds
        )
        self.heatmap_ttl_seconds = _int_config(
            collectors.get("heatmap_interval_seconds"), app_config.core_loop_interval_seconds
        )

    def configured_symbols(self) -> list[str]:
        if self.mode_summary.mode == RuntimeMode.LIVE_MICRO:
            return list(self.symbol_config.core)

        symbols: list[str] = []
        symbols.extend(self.symbol_config.core)
        symbols.extend(self.symbol_config.liquid_alt)
        symbols.extend(self.symbol_config.experimental)
        return list(dict.fromkeys(symbols))

    def symbol_sources(self) -> dict[str, str]:
        sources: dict[str, str] = {}
        for symbol in self.symbol_config.core:
            sources[symbol] = "core"
        for symbol in self.symbol_config.liquid_alt:
            sources.setdefault(symbol, "liquid_alt")
        for symbol in self.symbol_config.experimental:
            sources.setdefault(symbol, "experimental")
        return sources

    def decision_stream(self) -> str:
        if self.mode_summary.mode == RuntimeMode.SHADOW:
            return "shadow_decision_log"
        if self.mode_summary.mode == RuntimeMode.PAPER:
            return "paper_decision_log"
        return "decision_log"

    async def run_cycle(self) -> DecisionRuntimeResult:
        cycle_started_at = datetime.now(timezone.utc)
        cycle_id = str(uuid.uuid4())
        request_stats = NofxRequestStats()
        features: dict[str, FeatureVector] = {}
        symbol_sources = self.symbol_sources()
        for symbol in self.configured_symbols():
            try:
                features[symbol] = await self._build_feature(symbol, now=cycle_started_at, request_stats=request_stats)
            except Exception as exc:  # noqa: BLE001
                self.journal.record(
                    "decision_cycle_error",
                    {
                        "ts": cycle_started_at.isoformat(),
                        "cycle_id": cycle_id,
                        "symbol": symbol,
                        "mode": self.mode_summary.mode.value,
                        "error": str(exc),
                    },
                )

        if self.mode_summary.paper_execution and self.paper_execution is not None:
            self.paper_execution.mark_to_market(features, cycle_id=cycle_id, ts=cycle_started_at)
            account_state = self.paper_execution.account_state(now=cycle_started_at)
        else:
            account_state = await self.reconciler.reconcile()
        account_snapshot = account_state.to_snapshot(now=cycle_started_at)

        decisions: list[TradeDecision] = []
        for symbol in self.configured_symbols():
            feature = features.get(symbol)
            if feature is None:
                continue

            if feature.stale_seconds > self.app_config.nofx_stale_kill_seconds:
                decision = TradeDecision.no_trade(
                    decision_id=f"stale-{symbol.lower()}-{cycle_id[:8]}",
                    symbol=symbol,
                    regime=MarketRegime.DEFENSE,
                    rationale=[
                        "nofx feature stale",
                        f"feature stale for {feature.stale_seconds:.1f}s",
                    ],
                )
            else:
                decision = self.decision_engine.decide(feature, account_snapshot)

            order_request_preview = self._build_order_request_preview(decision)
            self.journal.record(
                self.decision_stream(),
                self._build_journal_entry(
                    cycle_id=cycle_id,
                    symbol=symbol,
                    symbol_source=symbol_sources.get(symbol, "unknown"),
                    feature=feature,
                    decision=decision,
                    account_snapshot=account_snapshot,
                    order_request_preview=order_request_preview,
                ),
            )
            decisions.append(decision)

            if self.mode_summary.paper_execution and self.paper_execution is not None:
                self.paper_execution.apply_decision(
                    decision,
                    feature,
                    cycle_id=cycle_id,
                    ts=cycle_started_at,
                )
                account_state = self.paper_execution.account_state(now=cycle_started_at)
                account_snapshot = account_state.to_snapshot(now=cycle_started_at)

        return DecisionRuntimeResult(
            cycle_id=cycle_id,
            account_state=account_state,
            decisions=decisions,
            request_stats=request_stats,
        )

    async def _build_feature(
        self,
        symbol: str,
        *,
        now: datetime | None = None,
        request_stats: NofxRequestStats | None = None,
    ) -> FeatureVector:
        base_symbol = symbol.replace("USDT", "")
        coin = await self._get_cached_payload(
            endpoint="coin",
            key=symbol,
            ttl_seconds=self.coin_ttl_seconds,
            fetcher=lambda: self.nofx.coin(symbol),
            request_stats=request_stats,
        )
        funding = await self._get_cached_payload(
            endpoint="funding_rate",
            key=base_symbol,
            ttl_seconds=self.funding_ttl_seconds,
            fetcher=lambda: self.nofx.funding_rate(base_symbol),
            request_stats=request_stats,
        )
        heatmap = await self._get_cached_payload(
            endpoint="heatmap_future",
            key=base_symbol,
            ttl_seconds=self.heatmap_ttl_seconds,
            fetcher=lambda: self.nofx.heatmap_future(base_symbol),
            request_stats=request_stats,
        )
        feature = normalize_coin_snapshot(symbol, coin, funding, heatmap)
        reference_time = now or datetime.now(timezone.utc)
        feature.stale_seconds = max((reference_time - feature.ts).total_seconds(), 0.0)
        return feature

    async def _get_cached_payload(
        self,
        *,
        endpoint: str,
        key: str,
        ttl_seconds: int,
        fetcher: Callable[[], Awaitable[dict[str, object]]],
        request_stats: NofxRequestStats | None,
    ) -> dict[str, object]:
        cache_key = (endpoint, key)
        cached = self.response_cache.get(cache_key)
        now = datetime.now(timezone.utc)
        if cached is not None and max(ttl_seconds, 0) > 0:
            age_seconds = (now - cached.fetched_at).total_seconds()
            if age_seconds < ttl_seconds:
                if request_stats is not None:
                    request_stats.cache_hits += 1
                return cached.payload

        payload = await fetcher()
        self.response_cache[cache_key] = CachedPayload(payload=payload, fetched_at=now)
        if request_stats is not None:
            request_stats.api_requests += 1
        return payload

    def _build_order_request_preview(self, decision: TradeDecision) -> dict[str, object] | None:
        if decision.status != DecisionStatus.EXECUTE or decision.side is None or decision.risk is None:
            return None

        preview: dict[str, object] = {
            "symbol": decision.symbol,
            "side": decision.side.value,
            "order_type": OrderType.MARKET.value,
            "position_side": "BOTH",
            "target_notional": decision.risk.approved_notional,
            "approved_leverage": decision.risk.approved_leverage,
            "live_submission_enabled": self.mode_summary.live_order_submission,
        }
        if not self.mode_summary.live_order_submission:
            preview["submission_blocked_by_mode"] = self.mode_summary.mode.value
        return preview

    def _build_journal_entry(
        self,
        *,
        cycle_id: str,
        symbol: str,
        symbol_source: str,
        feature: FeatureVector,
        decision: TradeDecision,
        account_snapshot: AccountSnapshot,
        order_request_preview: dict[str, object] | None,
    ) -> dict[str, object]:
        risk_payload = None
        if decision.risk is not None:
            risk_payload = {
                "status": decision.risk.status.value,
                "reason": decision.risk.reason,
                "symbol_tier": decision.risk.symbol_tier.value if decision.risk.symbol_tier else None,
                "approved_notional": decision.risk.approved_notional,
                "approved_leverage": decision.risk.approved_leverage,
                "risk_budget_bps": decision.risk.risk_budget_bps,
            }

        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "cycle_id": cycle_id,
            "symbol": symbol,
            "symbol_source": symbol_source,
            "mode": self.mode_summary.mode.value,
            "feature_ts": feature.ts.isoformat(),
            "feature_stale_seconds": feature.stale_seconds,
            "decision": decision,
            "decision_status": decision.status.value,
            "regime": decision.regime.value,
            "selected_strategy": decision.selected_strategy,
            "action_score": decision.action_score,
            "risk": risk_payload,
            "order_request_preview": order_request_preview,
            "account_snapshot": account_snapshot,
        }
