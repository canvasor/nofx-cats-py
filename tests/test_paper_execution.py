import asyncio
from datetime import datetime, timedelta, timezone

from cats_py.app.bootstrap import RuntimeModeSummary
from cats_py.config.settings import AppConfig, RuntimeMode, SymbolConfig
from cats_py.domain.enums import MarketRegime, RiskDecisionStatus, Side, SymbolTier
from cats_py.domain.models import FeatureVector, RiskDecision, TradeDecision
from cats_py.services.decision_runtime import DecisionRuntimeService
from cats_py.services.paper_execution import PaperExecutionService


class DummyNofx:
    async def coin(self, symbol: str) -> dict[str, object]:
        return {
            "data": {
                "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
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
        return {"data": {"funding_rate": 0.2, "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)}}

    async def heatmap_future(self, symbol: str) -> dict[str, object]:
        return {"data": {"heatmap": {"delta": 1000, "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)}}}


class DummyReconciler:
    def __init__(self, account_state) -> None:
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


def make_execute_decision(symbol: str, side: Side, *, notional: float) -> TradeDecision:
    return TradeDecision.execute(
        decision_id=f"decision-{symbol.lower()}-{side.value.lower()}",
        symbol=symbol,
        regime=MarketRegime.TREND,
        side=side,
        rationale=["paper test"],
        risk=RiskDecision(
            status=RiskDecisionStatus.APPROVED,
            reason="approved",
            symbol_tier=SymbolTier.CORE,
            approved_notional=notional,
            approved_leverage=1.0,
            risk_budget_bps=25.0,
        ),
        action_score=10.0,
        selected_strategy="paper",
    )


def make_feature(symbol: str, price: float) -> FeatureVector:
    return FeatureVector(
        symbol=symbol,
        ts=datetime.now(timezone.utc),
        reference_price=price,
    )


def make_mode_summary(mode: RuntimeMode) -> RuntimeModeSummary:
    return RuntimeModeSummary(
        env="test",
        mode=mode,
        decision_loop_enabled=True,
        live_order_submission=mode == RuntimeMode.LIVE_MICRO,
        paper_execution=mode == RuntimeMode.PAPER,
        allowed_symbol_tiers=("core",) if mode == RuntimeMode.LIVE_MICRO else ("core", "liquid_alt", "experimental"),
        configured_symbol_counts={"core": 1, "liquid_alt": 0, "experimental": 0},
        core_loop_interval_seconds=1,
    )


def test_paper_execution_opens_and_marks_position_to_market() -> None:
    journal = MemoryJournal()
    paper = PaperExecutionService(
        journal=journal,
        starting_balance=1000.0,
        slippage_bps=0.0,
        taker_fee_bps=0.0,
        funding_interval_hours=8.0,
    )
    feature = make_feature("BTCUSDT", 100.0)
    decision = make_execute_decision("BTCUSDT", Side.BUY, notional=200.0)

    paper.apply_decision(decision, feature, cycle_id="cycle-1", ts=feature.ts)
    paper.mark_to_market({"BTCUSDT": make_feature("BTCUSDT", 110.0)}, cycle_id="cycle-2", ts=feature.ts)

    account_state = paper.account_state(now=feature.ts)
    position = account_state.positions[("BTCUSDT", "BOTH")]
    assert float(position.quantity) == 2.0
    assert float(position.unrealized_pnl) == 20.0
    assert account_state.to_snapshot(now=feature.ts).equity == 1020.0
    assert journal.entries[0][0] == "paper_fill_log"
    assert journal.entries[-1][0] == "paper_pnl_log"


def test_paper_execution_realizes_pnl_when_position_closes() -> None:
    journal = MemoryJournal()
    paper = PaperExecutionService(
        journal=journal,
        starting_balance=1000.0,
        slippage_bps=0.0,
        taker_fee_bps=0.0,
        funding_interval_hours=8.0,
    )
    opened_at = datetime.now(timezone.utc)

    paper.apply_decision(
        make_execute_decision("BTCUSDT", Side.BUY, notional=200.0),
        make_feature("BTCUSDT", 100.0),
        cycle_id="cycle-open",
        ts=opened_at,
    )
    paper.apply_decision(
        make_execute_decision("BTCUSDT", Side.SELL, notional=300.0),
        make_feature("BTCUSDT", 150.0),
        cycle_id="cycle-close",
        ts=opened_at,
    )

    account_state = paper.account_state(now=opened_at)
    position = account_state.positions[("BTCUSDT", "BOTH")]
    balance = account_state.balances["USDT"]
    assert float(position.quantity) == 0.0
    assert float(position.unrealized_pnl) == 0.0
    assert float(balance.wallet_balance) == 1100.0


def test_paper_execution_tracks_fee_funding_and_turnover() -> None:
    journal = MemoryJournal()
    opened_at = datetime.now(timezone.utc)
    settled_at = opened_at + timedelta(hours=1)
    paper = PaperExecutionService(
        journal=journal,
        starting_balance=1000.0,
        slippage_bps=0.0,
        taker_fee_bps=10.0,
        funding_interval_hours=0.0,
    )

    paper.apply_decision(
        make_execute_decision("BTCUSDT", Side.BUY, notional=200.0),
        make_feature("BTCUSDT", 100.0),
        cycle_id="cycle-open",
        ts=opened_at,
    )
    funding_feature = make_feature("BTCUSDT", 100.0)
    funding_feature.funding_rate = 0.01
    paper.mark_to_market({"BTCUSDT": funding_feature}, cycle_id="cycle-funding", ts=settled_at)

    balance = paper.account_state(now=settled_at).balances["USDT"]
    latest_pnl = journal.entries[-1][1]
    assert float(balance.wallet_balance) == 997.8
    assert latest_pnl["fees_paid"] == 0.2
    assert latest_pnl["funding_pnl"] == -2.0
    assert latest_pnl["turnover_notional"] == 200.0


class ExecuteAllDecisionEngine:
    def decide(self, feature, account_snapshot) -> TradeDecision:
        return make_execute_decision(feature.symbol, Side.BUY, notional=100.0)


def test_decision_runtime_uses_paper_execution_state_in_paper_mode() -> None:
    journal = MemoryJournal()
    paper = PaperExecutionService(
        journal=journal,
        starting_balance=1000.0,
        slippage_bps=0.0,
        taker_fee_bps=0.0,
        funding_interval_hours=8.0,
    )
    reconciler = DummyReconciler(account_state=paper.account_state())
    service = DecisionRuntimeService(
        nofx=DummyNofx(),
        decision_engine=ExecuteAllDecisionEngine(),  # type: ignore[arg-type]
        reconciler=reconciler,  # type: ignore[arg-type]
        journal=journal,  # type: ignore[arg-type]
        app_config=AppConfig(
            mode=RuntimeMode.PAPER,
            paper_starting_balance=1000.0,
            paper_fill_slippage_bps=0.0,
            paper_taker_fee_bps=0.0,
            paper_funding_interval_hours=8.0,
        ),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(RuntimeMode.PAPER),
        paper_execution=paper,
    )

    result = asyncio.run(service.run_cycle())

    assert reconciler.calls == 0
    assert result.account_state.open_position_count() == 1
    streams = [entry[0] for entry in journal.entries]
    assert "paper_decision_log" in streams
    assert "paper_fill_log" in streams
    assert "paper_pnl_log" in streams
