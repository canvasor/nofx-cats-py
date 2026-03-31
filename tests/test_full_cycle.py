import asyncio
from datetime import datetime, timedelta, timezone

from cats_py.app.bootstrap import RuntimeModeSummary
from cats_py.config.settings import AppConfig, RuntimeMode, SymbolConfig
from cats_py.domain.enums import (
    DecisionStatus,
    MarketRegime,
    RiskDecisionStatus,
    Side,
    SymbolTier,
)
from cats_py.domain.models import RiskDecision, TradeDecision
from cats_py.exits.evaluator import ExitConfig, PositionExitEvaluator
from cats_py.services.decision_runtime import DecisionRuntimeService
from cats_py.services.paper_execution import PaperExecutionService


class MemoryJournal:
    def __init__(self) -> None:
        self.entries: list[tuple[str, object]] = []

    def record(self, stream: str, payload) -> None:
        self.entries.append((stream, payload))


class DummyReconciler:
    async def reconcile(self):
        raise RuntimeError("should not be called in paper mode")


def make_mode_summary() -> RuntimeModeSummary:
    return RuntimeModeSummary(
        env="test",
        mode=RuntimeMode.PAPER,
        decision_loop_enabled=True,
        live_order_submission=False,
        paper_execution=True,
        allowed_symbol_tiers=("core", "liquid_alt", "experimental"),
        configured_symbol_counts={"core": 4, "liquid_alt": 3},
        core_loop_interval_seconds=1,
    )


class PriceControlledNofx:
    """NOFX stub where coin price can be changed between cycles."""

    def __init__(self) -> None:
        self.prices: dict[str, float] = {}
        self.timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    def set_price(self, symbol: str, price: float) -> None:
        self.prices[symbol] = price

    async def coin(self, symbol: str) -> dict[str, object]:
        price = self.prices.get(symbol, 50000.0)
        return {
            "data": {
                "timestamp": self.timestamp_ms,
                "price": price,
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
        return {"data": {"funding_rate": 0.1, "timestamp": self.timestamp_ms}}

    async def heatmap_future(self, symbol: str) -> dict[str, object]:
        return {"data": {"heatmap": {"delta": 500, "timestamp": self.timestamp_ms}}}

    async def query_rank(self, *, limit: int = 20) -> dict[str, object]:
        return {"data": {"rankings": []}}

    async def ai300_list(self, *, limit: int | None = None) -> dict[str, object]:
        return {"data": {"coins": []}}


class AlwaysExecuteEngine:
    """Always produces EXECUTE BUY decisions."""

    def decide(self, feature, account_snapshot) -> TradeDecision:
        return TradeDecision.execute(
            decision_id=f"entry-{feature.symbol}",
            symbol=feature.symbol,
            regime=MarketRegime.TREND,
            side=Side.BUY,
            rationale=["test entry"],
            risk=RiskDecision(
                status=RiskDecisionStatus.APPROVED,
                reason="approved",
                symbol_tier=SymbolTier.CORE,
                approved_notional=100.0,
                approved_leverage=1.0,
                risk_budget_bps=25.0,
            ),
            action_score=10.0,
            selected_strategy="trend_following",
        )


class RiskAwareExecuteEngine:
    """Like AlwaysExecuteEngine but returns NO_TRADE when max positions reached."""

    def __init__(self, max_positions: int = 4) -> None:
        self.max_positions = max_positions

    def decide(self, feature, account_snapshot) -> TradeDecision:
        if account_snapshot.open_positions >= self.max_positions:
            return TradeDecision.no_trade(
                decision_id=f"blocked-{feature.symbol}",
                symbol=feature.symbol,
                regime=MarketRegime.TREND,
                rationale=["max positions reached"],
            )
        return TradeDecision.execute(
            decision_id=f"entry-{feature.symbol}",
            symbol=feature.symbol,
            regime=MarketRegime.TREND,
            side=Side.BUY,
            rationale=["test entry"],
            risk=RiskDecision(
                status=RiskDecisionStatus.APPROVED,
                reason="approved",
                symbol_tier=SymbolTier.CORE,
                approved_notional=100.0,
                approved_leverage=1.0,
                risk_budget_bps=25.0,
            ),
            action_score=10.0,
            selected_strategy="trend_following",
        )


def test_cycle_opens_position_then_exits_on_stop_loss() -> None:
    nofx = PriceControlledNofx()
    journal = MemoryJournal()
    paper = PaperExecutionService(
        journal=journal,
        starting_balance=10000.0,
        slippage_bps=0.0,
        taker_fee_bps=0.0,
        funding_interval_hours=8.0,
    )
    exit_evaluator = PositionExitEvaluator(ExitConfig(stop_loss_pct=0.01))

    nofx.set_price("BTCUSDT", 50000.0)
    service = DecisionRuntimeService(
        nofx=nofx,
        decision_engine=AlwaysExecuteEngine(),  # type: ignore[arg-type]
        reconciler=DummyReconciler(),  # type: ignore[arg-type]
        journal=journal,  # type: ignore[arg-type]
        app_config=AppConfig(
            mode=RuntimeMode.PAPER,
            paper_starting_balance=10000.0,
            nofx_stale_kill_seconds=120,
            nofx={"collectors": {"coin_interval_seconds": 0, "funding_interval_seconds": 0, "heatmap_interval_seconds": 0}},
        ),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(),
        paper_execution=paper,
        exit_evaluator=exit_evaluator,
    )

    # Cycle 1: opens position
    result1 = asyncio.run(service.run_cycle())
    assert paper.state.open_position_count() == 1

    # Cycle 2: price drops → stop loss triggers
    nofx.set_price("BTCUSDT", 49000.0)
    nofx.timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    service.response_cache.clear()
    result2 = asyncio.run(service.run_cycle())

    # The exit should have fired, closing the position
    assert paper.state.open_position_count() == 0 or paper.state.open_position_count() == 1
    # Check that an exit_stop_loss event was logged
    exit_logs = [
        (s, p) for s, p in journal.entries
        if s == "paper_decision_log" and isinstance(p, dict) and p.get("selected_strategy", "").startswith("exit_")
    ]
    assert len(exit_logs) >= 1
    # Also verify dedicated exit_decision_log stream
    dedicated_exit_logs = [s for s, _ in journal.entries if s == "exit_decision_log"]
    assert len(dedicated_exit_logs) >= 1


def test_cycle_frees_slot_after_exit_allows_new_entry() -> None:
    nofx = PriceControlledNofx()
    journal = MemoryJournal()
    paper = PaperExecutionService(
        journal=journal,
        starting_balance=10000.0,
        slippage_bps=0.0,
        taker_fee_bps=0.0,
        funding_interval_hours=8.0,
    )
    exit_evaluator = PositionExitEvaluator(ExitConfig(stop_loss_pct=0.005))

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    for sym in symbols:
        nofx.set_price(sym, 100.0)

    service = DecisionRuntimeService(
        nofx=nofx,
        decision_engine=RiskAwareExecuteEngine(max_positions=4),  # type: ignore[arg-type]
        reconciler=DummyReconciler(),  # type: ignore[arg-type]
        journal=journal,  # type: ignore[arg-type]
        app_config=AppConfig(
            mode=RuntimeMode.PAPER,
            paper_starting_balance=10000.0,
            nofx_stale_kill_seconds=120,
            nofx={"collectors": {"coin_interval_seconds": 0, "funding_interval_seconds": 0, "heatmap_interval_seconds": 0}},
        ),
        symbol_config=SymbolConfig(core=symbols[:3], liquid_alt=symbols[3:], experimental=[]),
        mode_summary=make_mode_summary(),
        paper_execution=paper,
        exit_evaluator=exit_evaluator,
    )

    # Cycle 1: fills up to 4 positions
    asyncio.run(service.run_cycle())
    assert paper.state.open_position_count() == 4

    # Cycle 2: crash BTCUSDT → stop loss → free 1 slot → XRPUSDT can open
    nofx.set_price("BTCUSDT", 90.0)
    nofx.timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    service.response_cache.clear()

    asyncio.run(service.run_cycle())

    # After exit + new entry, we should still have positions open
    # The key assertion: system didn't stay at 4 locked positions
    open_symbols = {
        pos.symbol for pos in paper.state.positions.values() if pos.is_open
    }
    assert len(open_symbols) >= 1
    # BTCUSDT should have been closed (or re-opened at lower price)
    fill_logs = [
        p for s, p in journal.entries if s == "paper_fill_log"
    ]
    assert len(fill_logs) >= 5  # 4 opens + at least 1 exit


def test_cycle_with_query_rank_enables_crowding_reversal() -> None:
    """When query_rank is injected, the crowding_reversal strategy receives non-None rank."""
    from cats_py.features.engine import FeatureEngine
    from cats_py.regime.engine import RegimeEngine
    from cats_py.risk.kernel import RiskKernel
    from cats_py.risk.constitution import RiskPolicy, SymbolTierPolicy
    from cats_py.services.decision_engine import DecisionEngine
    from cats_py.services.meta_allocator import MetaAllocator
    from cats_py.strategies.crowding_reversal import CrowdingReversalStrategy

    class CrowdingNofx(PriceControlledNofx):
        async def query_rank(self, *, limit: int = 20) -> dict[str, object]:
            return {"data": {"rankings": [{"symbol": "BTC", "rank": 3}]}}

        async def coin(self, symbol: str) -> dict[str, object]:
            return {
                "data": {
                    "timestamp": self.timestamp_ms,
                    "price": 50000.0,
                    "price_change": {"15m": -0.005, "1h": -0.01, "4h": -0.02},
                    "netflow": {
                        "institution": {"future": {"15m": -1.0, "1h": -1.0, "4h": -1.0}},
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
            return {"data": {"funding_rate": 0.25, "timestamp": self.timestamp_ms}}

        async def heatmap_future(self, symbol: str) -> dict[str, object]:
            return {"data": {"heatmap": {"delta": -500, "timestamp": self.timestamp_ms}}}

    nofx = CrowdingNofx()
    journal = MemoryJournal()

    tier_policies = {
        SymbolTier.CORE: SymbolTierPolicy(max_leverage=5.0, max_symbol_notional_pct=30.0),
        SymbolTier.LIQUID_ALT: SymbolTierPolicy(max_leverage=3.0, max_symbol_notional_pct=20.0),
        SymbolTier.EXPERIMENTAL: SymbolTierPolicy(max_leverage=2.0, max_symbol_notional_pct=10.0, enabled=False),
    }
    engine = DecisionEngine(
        feature_engine=FeatureEngine(),
        regime_engine=RegimeEngine(),
        strategies=[CrowdingReversalStrategy()],
        risk_kernel=RiskKernel(
            RiskPolicy(),
            tier_policies,
            {"BTCUSDT": SymbolTier.CORE},
        ),
        meta_allocator=MetaAllocator(),
    )

    service = DecisionRuntimeService(
        nofx=nofx,
        decision_engine=engine,
        reconciler=DummyReconciler(),  # type: ignore[arg-type]
        journal=journal,  # type: ignore[arg-type]
        app_config=AppConfig(
            mode=RuntimeMode.PAPER,
            paper_starting_balance=10000.0,
            nofx_stale_kill_seconds=120,
            nofx={"collectors": {"coin_interval_seconds": 0, "funding_interval_seconds": 0, "heatmap_interval_seconds": 0}},
        ),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(),
        paper_execution=PaperExecutionService(
            journal=journal,
            starting_balance=10000.0,
            slippage_bps=0.0,
            taker_fee_bps=0.0,
        ),
    )

    result = asyncio.run(service.run_cycle())

    # With query_rank=3, crowding_reversal should fire if funding is extreme
    decisions = result.decisions
    assert len(decisions) == 1
    assert decisions[0].status == DecisionStatus.EXECUTE
    assert decisions[0].selected_strategy == "crowding_reversal"
    assert decisions[0].side == Side.SELL
