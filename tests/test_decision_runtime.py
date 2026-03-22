import asyncio
from datetime import datetime, timezone

from cats_py.app.bootstrap import RuntimeModeSummary
from cats_py.config.settings import AppConfig, RuntimeMode, SymbolConfig
from cats_py.domain.enums import DecisionStatus, MarketRegime, RiskDecisionStatus, Side, SymbolTier
from cats_py.domain.models import AccountState, BalanceState, RiskDecision, TradeDecision
from cats_py.services.decision_runtime import DecisionRuntimeService


class DummyNofx:
    def __init__(self, *, timestamp_ms: int | None = None) -> None:
        self.requested_symbols: list[str] = []
        self.timestamp_ms = timestamp_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
        self.coin_calls = 0
        self.funding_calls = 0
        self.heatmap_calls = 0

    async def coin(self, symbol: str) -> dict[str, object]:
        self.coin_calls += 1
        self.requested_symbols.append(symbol)
        return {
            "data": {
                "timestamp": self.timestamp_ms,
                "price": 50_000,
                "price_change": {"15m": 0.01, "1h": 0.02, "4h": 0.03},
                "netflow": {
                    "institution": {"future": {"15m": 1.0, "1h": 1.0, "4h": 1.0}},
                    "personal": {"future": {"1h": 0.0}},
                },
                "oi": {
                    "binance": {"delta": {"1h": {"oi_delta_percent": 5.0}}},
                    "bybit": {"delta": {"1h": {"oi_delta_percent": 2.0}}},
                },
                "ai500": {"score": 75.0},
            }
        }

    async def funding_rate(self, symbol: str) -> dict[str, object]:
        self.funding_calls += 1
        return {"data": {"funding_rate": 0.2, "timestamp": self.timestamp_ms}}

    async def heatmap_future(self, symbol: str) -> dict[str, object]:
        self.heatmap_calls += 1
        return {"data": {"heatmap": {"delta": 1000, "timestamp": self.timestamp_ms}}}


class DummyDecisionEngine:
    def __init__(self) -> None:
        self.received_snapshots = []

    def decide(self, feature, account_snapshot) -> TradeDecision:
        self.received_snapshots.append(account_snapshot)
        return TradeDecision.no_trade(
            decision_id=f"decision-{feature.symbol.lower()}",
            symbol=feature.symbol,
            regime=MarketRegime.TREND,
            rationale=["test"],
            action_score=0.0,
        )


class ExecuteDecisionEngine:
    def decide(self, feature, account_snapshot) -> TradeDecision:
        return TradeDecision.execute(
            decision_id=f"decision-{feature.symbol.lower()}",
            symbol=feature.symbol,
            regime=MarketRegime.TREND,
            side=Side.BUY,
            rationale=["signal approved"],
            risk=RiskDecision(
                status=RiskDecisionStatus.APPROVED,
                reason="approved",
                symbol_tier=SymbolTier.CORE,
                approved_notional=125.0,
                approved_leverage=1.5,
                risk_budget_bps=25.0,
            ),
            action_score=12.0,
            selected_strategy="trend_following",
        )


class DummyReconciler:
    def __init__(self, account_state: AccountState) -> None:
        self.account_state = account_state
        self.calls = 0

    async def reconcile(self):
        self.calls += 1
        return self.account_state


class MemoryJournal:
    def __init__(self) -> None:
        self.entries: list[tuple[str, object]] = []

    def record(self, stream: str, payload) -> None:
        self.entries.append((stream, payload))


def make_mode_summary(mode: RuntimeMode) -> RuntimeModeSummary:
    return RuntimeModeSummary(
        env="test",
        mode=mode,
        decision_loop_enabled=True,
        live_order_submission=mode == RuntimeMode.LIVE_MICRO,
        paper_execution=mode == RuntimeMode.PAPER,
        allowed_symbol_tiers=("core",) if mode == RuntimeMode.LIVE_MICRO else ("core", "liquid_alt", "experimental"),
        configured_symbol_counts={"core": 1, "liquid_alt": 1, "experimental": 1},
        core_loop_interval_seconds=1,
    )


def make_app_config() -> AppConfig:
    return AppConfig(
        mode=RuntimeMode.SHADOW,
        core_loop_interval_seconds=1,
        nofx_stale_kill_seconds=45,
        nofx={
            "collectors": {
                "coin_interval_seconds": 30,
                "funding_interval_seconds": 30,
                "heatmap_interval_seconds": 30,
            }
        },
    )


def test_decision_runtime_limits_symbols_in_live_micro() -> None:
    service = DecisionRuntimeService(
        nofx=DummyNofx(),
        decision_engine=DummyDecisionEngine(),
        reconciler=DummyReconciler(AccountState()),
        journal=MemoryJournal(),  # type: ignore[arg-type]
        app_config=make_app_config(),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=["ETHUSDT"], experimental=["DOGEUSDT"]),
        mode_summary=make_mode_summary(RuntimeMode.LIVE_MICRO),
    )

    assert service.configured_symbols() == ["BTCUSDT"]


def test_decision_runtime_uses_reconciled_account_snapshot_and_records_decisions() -> None:
    account_state = AccountState()
    account_state.upsert_balance(BalanceState(asset="USDT", wallet_balance=1000))  # type: ignore[arg-type]
    account_state.record_user_stream_event(datetime.now(timezone.utc))
    nofx = DummyNofx()
    decision_engine = DummyDecisionEngine()
    reconciler = DummyReconciler(account_state)
    journal = MemoryJournal()
    service = DecisionRuntimeService(
        nofx=nofx,
        decision_engine=decision_engine,
        reconciler=reconciler,
        journal=journal,  # type: ignore[arg-type]
        app_config=make_app_config(),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=["ETHUSDT"], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.SHADOW),
    )

    result = asyncio.run(service.run_cycle())

    assert reconciler.calls == 1
    assert len(result.decisions) == 2
    assert nofx.requested_symbols == ["BTCUSDT", "ETHUSDT"]
    assert decision_engine.received_snapshots[0].equity == 1000.0
    assert journal.entries[0][0] == "shadow_decision_log"
    assert journal.entries[0][1]["symbol_source"] == "core"
    assert result.decisions[0].status == DecisionStatus.NO_TRADE


def test_decision_runtime_records_order_preview_when_execution_is_mode_blocked() -> None:
    account_state = AccountState()
    account_state.upsert_balance(BalanceState(asset="USDT", wallet_balance=1000))  # type: ignore[arg-type]
    account_state.record_user_stream_event(datetime.now(timezone.utc))
    journal = MemoryJournal()
    service = DecisionRuntimeService(
        nofx=DummyNofx(),
        decision_engine=ExecuteDecisionEngine(),  # type: ignore[arg-type]
        reconciler=DummyReconciler(account_state),  # type: ignore[arg-type]
        journal=journal,  # type: ignore[arg-type]
        app_config=make_app_config(),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.SHADOW),
    )

    result = asyncio.run(service.run_cycle())

    entry = journal.entries[0][1]
    assert result.decisions[0].status == DecisionStatus.EXECUTE
    assert entry["order_request_preview"]["submission_blocked_by_mode"] == RuntimeMode.SHADOW.value
    assert entry["risk"]["approved_notional"] == 125.0


def test_decision_runtime_blocks_stale_nofx_feature_before_strategy_eval() -> None:
    old_timestamp_ms = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    journal = MemoryJournal()
    service = DecisionRuntimeService(
        nofx=DummyNofx(timestamp_ms=old_timestamp_ms),
        decision_engine=DummyDecisionEngine(),
        reconciler=DummyReconciler(AccountState()),
        journal=journal,  # type: ignore[arg-type]
        app_config=make_app_config(),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.SHADOW),
    )

    result = asyncio.run(service.run_cycle())

    assert result.decisions[0].status == DecisionStatus.NO_TRADE
    assert result.decisions[0].regime == MarketRegime.DEFENSE
    assert "nofx feature stale" in result.decisions[0].rationale


def test_decision_runtime_reuses_cached_nofx_payloads_between_cycles() -> None:
    nofx = DummyNofx()
    service = DecisionRuntimeService(
        nofx=nofx,
        decision_engine=DummyDecisionEngine(),
        reconciler=DummyReconciler(AccountState()),
        journal=MemoryJournal(),  # type: ignore[arg-type]
        app_config=make_app_config(),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.SHADOW),
    )

    first = asyncio.run(service.run_cycle())
    second = asyncio.run(service.run_cycle())

    assert first.request_stats.api_requests == 3
    assert second.request_stats.api_requests == 0
    assert second.request_stats.cache_hits == 3
    assert nofx.coin_calls == 1
    assert nofx.funding_calls == 1
    assert nofx.heatmap_calls == 1
