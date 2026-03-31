from datetime import datetime, timezone
from decimal import Decimal

from cats_py.domain.enums import MarketRegime, PositionDirection, RiskDecisionStatus, Side, SymbolTier
from cats_py.domain.models import FeatureVector, RiskDecision, TradeDecision
from cats_py.services.paper_execution import PaperExecutionService


class MemoryJournal:
    def __init__(self) -> None:
        self.entries: list[tuple[str, object]] = []

    def record(self, stream: str, payload) -> None:
        self.entries.append((stream, payload))


def make_feature(symbol: str, price: float) -> FeatureVector:
    return FeatureVector(symbol=symbol, ts=datetime.now(timezone.utc), reference_price=price)


def make_execute_decision(symbol: str, side: Side, *, notional: float) -> TradeDecision:
    return TradeDecision.execute(
        decision_id=f"test-{symbol}",
        symbol=symbol,
        regime=MarketRegime.TREND,
        side=side,
        rationale=["test"],
        risk=RiskDecision(
            status=RiskDecisionStatus.APPROVED,
            reason="approved",
            symbol_tier=SymbolTier.CORE,
            approved_notional=notional,
            approved_leverage=1.0,
            risk_budget_bps=25.0,
        ),
        action_score=10.0,
        selected_strategy="trend_following",
    )


def test_open_position_records_metadata() -> None:
    paper = PaperExecutionService(
        journal=MemoryJournal(),
        starting_balance=10000.0,
        slippage_bps=0.0,
        taker_fee_bps=0.0,
    )
    ts = datetime.now(timezone.utc)
    paper.apply_decision(
        make_execute_decision("BTCUSDT", Side.BUY, notional=500.0),
        make_feature("BTCUSDT", 50000.0),
        cycle_id="c1",
        ts=ts,
    )

    assert "BTCUSDT" in paper.position_metadata
    meta = paper.position_metadata["BTCUSDT"]
    assert meta.entry_time == ts
    assert meta.peak_price == 50000.0
    assert meta.strategy_name == "trend_following"


def test_close_position_removes_metadata() -> None:
    paper = PaperExecutionService(
        journal=MemoryJournal(),
        starting_balance=10000.0,
        slippage_bps=0.0,
        taker_fee_bps=0.0,
    )
    ts = datetime.now(timezone.utc)
    paper.apply_decision(
        make_execute_decision("BTCUSDT", Side.BUY, notional=500.0),
        make_feature("BTCUSDT", 50000.0),
        cycle_id="c1",
        ts=ts,
    )
    paper.apply_decision(
        make_execute_decision("BTCUSDT", Side.SELL, notional=500.0),
        make_feature("BTCUSDT", 50000.0),
        cycle_id="c2",
        ts=ts,
    )

    assert "BTCUSDT" not in paper.position_metadata


def test_mark_to_market_updates_peak_price_for_long() -> None:
    paper = PaperExecutionService(
        journal=MemoryJournal(),
        starting_balance=10000.0,
        slippage_bps=0.0,
        taker_fee_bps=0.0,
        funding_interval_hours=8.0,
    )
    ts = datetime.now(timezone.utc)
    paper.apply_decision(
        make_execute_decision("BTCUSDT", Side.BUY, notional=500.0),
        make_feature("BTCUSDT", 50000.0),
        cycle_id="c1",
        ts=ts,
    )
    assert paper.position_metadata["BTCUSDT"].peak_price == 50000.0

    paper.mark_to_market(
        {"BTCUSDT": make_feature("BTCUSDT", 52000.0)},
        cycle_id="c2",
        ts=ts,
    )
    assert paper.position_metadata["BTCUSDT"].peak_price == 52000.0

    paper.mark_to_market(
        {"BTCUSDT": make_feature("BTCUSDT", 51000.0)},
        cycle_id="c3",
        ts=ts,
    )
    assert paper.position_metadata["BTCUSDT"].peak_price == 52000.0


def test_mark_to_market_updates_peak_price_for_short() -> None:
    paper = PaperExecutionService(
        journal=MemoryJournal(),
        starting_balance=10000.0,
        slippage_bps=0.0,
        taker_fee_bps=0.0,
        funding_interval_hours=8.0,
    )
    ts = datetime.now(timezone.utc)
    paper.apply_decision(
        make_execute_decision("BTCUSDT", Side.SELL, notional=500.0),
        make_feature("BTCUSDT", 50000.0),
        cycle_id="c1",
        ts=ts,
    )
    assert paper.position_metadata["BTCUSDT"].peak_price == 50000.0

    paper.mark_to_market(
        {"BTCUSDT": make_feature("BTCUSDT", 48000.0)},
        cycle_id="c2",
        ts=ts,
    )
    assert paper.position_metadata["BTCUSDT"].peak_price == 48000.0

    paper.mark_to_market(
        {"BTCUSDT": make_feature("BTCUSDT", 49000.0)},
        cycle_id="c3",
        ts=ts,
    )
    assert paper.position_metadata["BTCUSDT"].peak_price == 48000.0
