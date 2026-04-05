import asyncio
from datetime import datetime, timedelta, timezone

from cats_py.app.bootstrap import RuntimeModeSummary
from cats_py.config.settings import AppConfig, RuntimeMode, SymbolConfig
from cats_py.domain.enums import DecisionStatus, MarketRegime, RiskDecisionStatus, Side, SymbolTier
from cats_py.domain.models import AccountState, BalanceState, FeatureVector, RiskDecision, TradeDecision
from cats_py.services.decision_runtime import CachedPayload, DecisionRuntimeService
from cats_py.services.paper_execution import PaperExecutionService


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

    async def query_rank(self, *, limit: int = 20) -> dict[str, object]:
        return {"data": {"rankings": []}}

    async def ai300_list(self, *, limit: int | None = None) -> dict[str, object]:
        return {"data": {"coins": []}}


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
    shadow_entries = [(s, p) for s, p in journal.entries if s == "shadow_decision_log"]
    assert len(shadow_entries) >= 1
    assert shadow_entries[0][1]["symbol_source"] == "core"
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

    shadow_entries = [(s, p) for s, p in journal.entries if s == "shadow_decision_log"]
    entry = shadow_entries[0][1]
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
    assert result.decisions[0].rationale == ["test"]
    shadow_entries = [(s, p) for s, p in journal.entries if s == "shadow_decision_log"]
    entry = shadow_entries[0][1]
    assert entry["source_lag_seconds"] > 60
    assert entry["feature_stale_seconds"] < 5


def test_decision_runtime_blocks_when_cached_fetch_is_stale() -> None:
    recent_timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    journal = MemoryJournal()
    app_config = make_app_config()
    app_config.nofx_stale_kill_seconds = 45
    app_config.nofx["collectors"] = {
        "coin_interval_seconds": 3600,
        "funding_interval_seconds": 3600,
        "heatmap_interval_seconds": 3600,
    }
    nofx = DummyNofx(timestamp_ms=recent_timestamp_ms)
    service = DecisionRuntimeService(
        nofx=nofx,
        decision_engine=DummyDecisionEngine(),
        reconciler=DummyReconciler(AccountState()),
        journal=journal,  # type: ignore[arg-type]
        app_config=app_config,
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.SHADOW),
    )
    stale_fetch = datetime.now(timezone.utc) - timedelta(seconds=90)
    service.response_cache[("coin", "BTCUSDT")] = CachedPayload(
        payload=asyncio.run(nofx.coin("BTCUSDT")),
        fetched_at=stale_fetch,
    )
    service.response_cache[("funding_rate", "BTC")] = CachedPayload(
        payload=asyncio.run(nofx.funding_rate("BTC")),
        fetched_at=stale_fetch,
    )
    service.response_cache[("heatmap_future", "BTC")] = CachedPayload(
        payload=asyncio.run(nofx.heatmap_future("BTC")),
        fetched_at=stale_fetch,
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

    assert first.request_stats.api_requests == 5  # 3 per-symbol + 2 global (query_rank, ai300)
    assert second.request_stats.api_requests == 0
    assert second.request_stats.cache_hits == 5
    assert nofx.coin_calls == 1
    assert nofx.funding_calls == 1
    assert nofx.heatmap_calls == 1


def test_response_cache_evicts_oldest_when_full() -> None:
    service = DecisionRuntimeService(
        nofx=DummyNofx(),
        decision_engine=DummyDecisionEngine(),
        reconciler=DummyReconciler(AccountState()),
        journal=MemoryJournal(),  # type: ignore[arg-type]
        app_config=make_app_config(),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.SHADOW),
    )
    service._cache_max_size = 3

    # Fill cache with 3 entries
    from cats_py.services.decision_runtime import CachedPayload
    base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service.response_cache[("a", "1")] = CachedPayload(payload={}, fetched_at=base_time)
    service.response_cache[("b", "2")] = CachedPayload(payload={}, fetched_at=base_time + timedelta(seconds=1))
    service.response_cache[("c", "3")] = CachedPayload(payload={}, fetched_at=base_time + timedelta(seconds=2))
    assert len(service.response_cache) == 3

    # Run a cycle which adds new entries — oldest should be evicted
    asyncio.run(service.run_cycle())

    assert len(service.response_cache) <= 5  # bounded, not unbounded
    assert ("a", "1") not in service.response_cache  # oldest evicted first


def _make_paper_runtime(
    journal: MemoryJournal,
    decision_engine=None,
    symbols: list[str] | None = None,
) -> tuple[DecisionRuntimeService, PaperExecutionService]:
    """Helper to build a paper-mode runtime + paper execution service."""
    paper = PaperExecutionService(
        journal=journal,
        starting_balance=10_000.0,
        slippage_bps=0.0,
        taker_fee_bps=0.0,
        funding_interval_hours=8.0,
    )
    engine = decision_engine or DummyDecisionEngine()
    syms = symbols or ["BTCUSDT"]
    service = DecisionRuntimeService(
        nofx=DummyNofx(),
        decision_engine=engine,
        reconciler=DummyReconciler(AccountState()),
        journal=journal,  # type: ignore[arg-type]
        app_config=AppConfig(
            mode=RuntimeMode.PAPER,
            core_loop_interval_seconds=1,
            nofx_stale_kill_seconds=45,
            paper_starting_balance=10_000.0,
            paper_fill_slippage_bps=0.0,
            paper_taker_fee_bps=0.0,
            paper_funding_interval_hours=8.0,
        ),
        symbol_config=SymbolConfig(core=syms, liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.PAPER),
        paper_execution=paper,
    )
    return service, paper


def test_decision_runtime_skips_symbol_in_exit_cooldown() -> None:
    journal = MemoryJournal()
    service, paper = _make_paper_runtime(journal)

    # Simulate an exit 10 minutes ago
    from datetime import datetime, timezone
    paper.last_exit_time["BTCUSDT"] = datetime.now(timezone.utc) - timedelta(minutes=10)

    result = asyncio.run(service.run_cycle())

    btc_decision = [d for d in result.decisions if d.symbol == "BTCUSDT"][0]
    assert btc_decision.status == DecisionStatus.NO_TRADE
    assert "exit cooldown active" in btc_decision.rationale


def test_decision_runtime_skips_symbol_with_open_position() -> None:
    journal = MemoryJournal()
    service, paper = _make_paper_runtime(journal, decision_engine=ExecuteDecisionEngine())

    # Run first cycle to open a position
    asyncio.run(service.run_cycle())
    assert paper.state.open_position_count() == 1

    # Run second cycle — should block due to existing position
    result = asyncio.run(service.run_cycle())

    btc_decision = [d for d in result.decisions if d.symbol == "BTCUSDT"][0]
    assert btc_decision.status == DecisionStatus.NO_TRADE
    assert "position already open" in btc_decision.rationale


def test_reject_reason_populated_for_no_trade() -> None:
    journal = MemoryJournal()
    service = DecisionRuntimeService(
        nofx=DummyNofx(),
        decision_engine=DummyDecisionEngine(),
        reconciler=DummyReconciler(AccountState()),
        journal=journal,  # type: ignore[arg-type]
        app_config=make_app_config(),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.SHADOW),
    )

    asyncio.run(service.run_cycle())

    shadow_entries = [(s, p) for s, p in journal.entries if s == "shadow_decision_log"]
    entry = shadow_entries[0][1]
    assert entry["decision_status"] == "NO_TRADE"
    assert entry["reject_reason"] == "test"


def test_reject_reason_empty_for_execute() -> None:
    journal = MemoryJournal()
    account_state = AccountState()
    account_state.upsert_balance(BalanceState(asset="USDT", wallet_balance=1000))  # type: ignore[arg-type]
    account_state.record_user_stream_event(datetime.now(timezone.utc))
    service = DecisionRuntimeService(
        nofx=DummyNofx(),
        decision_engine=ExecuteDecisionEngine(),  # type: ignore[arg-type]
        reconciler=DummyReconciler(account_state),  # type: ignore[arg-type]
        journal=journal,  # type: ignore[arg-type]
        app_config=make_app_config(),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.SHADOW),
    )

    asyncio.run(service.run_cycle())

    shadow_entries = [(s, p) for s, p in journal.entries if s == "shadow_decision_log"]
    entry = shadow_entries[0][1]
    assert entry["decision_status"] == "EXECUTE"
    assert entry["reject_reason"] == ""


def test_global_data_diagnostic_logged() -> None:
    journal = MemoryJournal()

    class RankingNofx(DummyNofx):
        async def query_rank(self, *, limit: int = 20) -> dict[str, object]:
            return {
                "data": {
                    "rankings": [
                        {"symbol": "BTCUSDT", "rank": 1},
                        {"symbol": "ETHUSDT", "rank": 2},
                    ]
                }
            }

    service = DecisionRuntimeService(
        nofx=RankingNofx(),
        decision_engine=DummyDecisionEngine(),
        reconciler=DummyReconciler(AccountState()),
        journal=journal,  # type: ignore[arg-type]
        app_config=make_app_config(),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.SHADOW),
    )

    asyncio.run(service.run_cycle())

    streams = [entry[0] for entry in journal.entries]
    assert "global_data_diagnostic" in streams
    diag = next(e[1] for e in journal.entries if e[0] == "global_data_diagnostic")
    assert "BTCUSDT" in diag["configured_symbols"]


def test_decision_runtime_blocks_new_entries_during_drawdown() -> None:
    """When drawdown exceeds soft limit and positions are open, block new entries."""

    class SelectiveExecuteEngine:
        """Only opens BTCUSDT, returns NO_TRADE for others."""
        def decide(self, feature, account_snapshot) -> TradeDecision:
            if feature.symbol == "BTCUSDT":
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
            return TradeDecision.no_trade(
                decision_id=f"decision-{feature.symbol.lower()}",
                symbol=feature.symbol,
                regime=MarketRegime.TREND,
                rationale=["test skip"],
            )

    journal = MemoryJournal()
    service, paper = _make_paper_runtime(
        journal,
        decision_engine=SelectiveExecuteEngine(),
        symbols=["BTCUSDT", "ETHUSDT"],
    )

    # Cycle 1: opens BTCUSDT only, ETHUSDT gets NO_TRADE from engine
    asyncio.run(service.run_cycle())
    assert paper.state.open_position_count() == 1

    # Simulate drawdown: push high watermark up so drawdown exceeds -1.5%
    paper.session_high_equity = paper.state.total_equity() * 2

    # Cycle 2: BTCUSDT blocked by already-open, ETHUSDT should be blocked by drawdown
    result = asyncio.run(service.run_cycle())

    eth_decisions = [d for d in result.decisions if d.symbol == "ETHUSDT"]
    assert len(eth_decisions) == 1
    assert eth_decisions[0].status == DecisionStatus.NO_TRADE
    assert "drawdown soft limit reached" in eth_decisions[0].rationale


def test_exit_journal_entry_includes_exit_specific_fields() -> None:
    """Exit journal entries should include exit_reason, hold_hours, and realized_pnl_delta."""
    from cats_py.exits.evaluator import ExitConfig, PositionExitEvaluator

    class CrashPriceNofx(DummyNofx):
        """Returns very low price to trigger stop loss."""
        def __init__(self) -> None:
            super().__init__()
            self.crash = False

        async def coin(self, symbol: str) -> dict[str, object]:
            data = await super().coin(symbol)
            if self.crash:
                data["data"]["price"] = 100  # type: ignore[index]
            return data

    nofx = CrashPriceNofx()
    journal = MemoryJournal()
    paper = PaperExecutionService(
        journal=journal,
        starting_balance=10_000.0,
        slippage_bps=0.0,
        taker_fee_bps=0.0,
        funding_interval_hours=8.0,
    )
    service = DecisionRuntimeService(
        nofx=nofx,
        decision_engine=ExecuteDecisionEngine(),
        reconciler=DummyReconciler(AccountState()),
        journal=journal,  # type: ignore[arg-type]
        app_config=AppConfig(
            mode=RuntimeMode.PAPER,
            core_loop_interval_seconds=1,
            nofx_stale_kill_seconds=45,
            paper_starting_balance=10_000.0,
            paper_fill_slippage_bps=0.0,
            paper_taker_fee_bps=0.0,
            paper_funding_interval_hours=8.0,
        ),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.PAPER),
        paper_execution=paper,
        exit_evaluator=PositionExitEvaluator(ExitConfig(
            stop_loss_pct=0.001,  # very tight to trigger easily
            max_hold_hours=999,
        )),
    )

    # Cycle 1: open position at price=50000
    asyncio.run(service.run_cycle())
    assert paper.state.open_position_count() == 1

    # Cycle 2: crash price to trigger stop loss
    nofx.crash = True
    nofx.timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    service.response_cache.clear()
    asyncio.run(service.run_cycle())

    exit_entries = [(s, p) for s, p in journal.entries if s == "exit_decision_log"]
    assert len(exit_entries) >= 1
    exit_entry = exit_entries[0][1]
    assert "exit_reason" in exit_entry
    assert exit_entry["exit_reason"] == "exit_stop_loss"
    assert "hold_hours" in exit_entry
    assert isinstance(exit_entry["hold_hours"], float)
    assert "realized_pnl_delta" in exit_entry
