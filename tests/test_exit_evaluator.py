from datetime import datetime, timedelta, timezone
from decimal import Decimal
from decimal import Decimal

from cats_py.domain.enums import MarketRegime, PositionDirection, Side
from cats_py.domain.models import AccountState, FeatureVector, PositionState
from cats_py.exits.evaluator import ExitConfig, PositionEntryMeta, PositionExitEvaluator


def make_feature(symbol: str, *, price: float = 100.0, trend: float = 0.0, flow: float = 0.0) -> FeatureVector:
    return FeatureVector(
        symbol=symbol,
        ts=datetime.now(timezone.utc),
        reference_price=price,
        trend_score=trend,
        flow_score=flow,
    )


def make_position(symbol: str, *, qty: float, entry: float, mark: float, leverage: int = 1) -> PositionState:
    direction = PositionDirection.LONG if qty > 0 else PositionDirection.SHORT
    q = Decimal(str(qty))
    e = Decimal(str(entry))
    m = Decimal(str(mark))
    return PositionState(
        symbol=symbol,
        direction=direction,
        quantity=q,
        entry_price=e,
        mark_price=m,
        notional=q * m,
        unrealized_pnl=(m - e) * q,
        leverage=leverage,
    )


def test_stop_loss_triggers_when_pnl_exceeds_threshold() -> None:
    evaluator = PositionExitEvaluator(ExitConfig(stop_loss_pct=0.015))
    state = AccountState()
    pos = make_position("BTCUSDT", qty=1.0, entry=100.0, mark=98.0)
    state.upsert_position(pos)
    features = {"BTCUSDT": make_feature("BTCUSDT", price=98.0)}
    now = datetime.now(timezone.utc)

    exits = evaluator.evaluate(state, features, {}, now)

    assert len(exits) == 1
    assert exits[0].selected_strategy == "exit_stop_loss"
    assert exits[0].side == Side.SELL


def test_stop_loss_does_not_trigger_within_threshold() -> None:
    evaluator = PositionExitEvaluator(ExitConfig(stop_loss_pct=0.015))
    state = AccountState()
    pos = make_position("BTCUSDT", qty=1.0, entry=100.0, mark=99.0)
    state.upsert_position(pos)
    features = {"BTCUSDT": make_feature("BTCUSDT", price=99.0)}
    now = datetime.now(timezone.utc)

    exits = evaluator.evaluate(state, features, {}, now)

    assert len(exits) == 0


def test_take_profit_triggers() -> None:
    evaluator = PositionExitEvaluator(ExitConfig(take_profit_pct=0.02))
    state = AccountState()
    pos = make_position("ETHUSDT", qty=2.0, entry=100.0, mark=103.0)
    state.upsert_position(pos)
    features = {"ETHUSDT": make_feature("ETHUSDT", price=103.0)}
    now = datetime.now(timezone.utc)

    exits = evaluator.evaluate(state, features, {}, now)

    assert len(exits) == 1
    assert exits[0].selected_strategy == "exit_take_profit"


def test_max_hold_time_triggers() -> None:
    evaluator = PositionExitEvaluator(ExitConfig(max_hold_hours=4.0))
    state = AccountState()
    pos = make_position("SOLUSDT", qty=1.0, entry=100.0, mark=100.5)
    state.upsert_position(pos)
    features = {"SOLUSDT": make_feature("SOLUSDT", price=100.5)}
    now = datetime.now(timezone.utc)
    meta = {"SOLUSDT": PositionEntryMeta(
        entry_time=now - timedelta(hours=5),
        peak_price=101.0,
        strategy_name="trend_following",
    )}

    exits = evaluator.evaluate(state, features, meta, now)

    assert len(exits) == 1
    assert exits[0].selected_strategy == "exit_max_hold_time"


def test_trailing_stop_triggers_on_long_retrace() -> None:
    evaluator = PositionExitEvaluator(ExitConfig(trailing_stop_pct=0.01))
    state = AccountState()
    pos = make_position("BTCUSDT", qty=1.0, entry=100.0, mark=100.5)
    state.upsert_position(pos)
    features = {"BTCUSDT": make_feature("BTCUSDT", price=100.5)}
    now = datetime.now(timezone.utc)
    meta = {"BTCUSDT": PositionEntryMeta(
        entry_time=now - timedelta(hours=1),
        peak_price=102.0,
        strategy_name="trend_following",
    )}

    exits = evaluator.evaluate(state, features, meta, now)

    assert len(exits) == 1
    assert exits[0].selected_strategy == "exit_trailing_stop"


def test_trailing_stop_triggers_on_short_retrace() -> None:
    evaluator = PositionExitEvaluator(ExitConfig(trailing_stop_pct=0.01))
    state = AccountState()
    pos = make_position("BTCUSDT", qty=-1.0, entry=100.0, mark=99.0)
    state.upsert_position(pos)
    features = {"BTCUSDT": make_feature("BTCUSDT", price=99.0)}
    now = datetime.now(timezone.utc)
    meta = {"BTCUSDT": PositionEntryMeta(
        entry_time=now - timedelta(hours=1),
        peak_price=97.0,
        strategy_name="trend_following",
    )}

    exits = evaluator.evaluate(state, features, meta, now)

    assert len(exits) == 1
    assert exits[0].selected_strategy == "exit_trailing_stop"
    assert exits[0].side == Side.BUY


def test_signal_reversal_triggers_for_long() -> None:
    evaluator = PositionExitEvaluator()
    state = AccountState()
    pos = make_position("BTCUSDT", qty=1.0, entry=100.0, mark=99.5)
    state.upsert_position(pos)
    features = {"BTCUSDT": make_feature("BTCUSDT", price=99.5, trend=-0.05, flow=-0.01)}
    now = datetime.now(timezone.utc)

    exits = evaluator.evaluate(state, features, {}, now)

    assert len(exits) == 1
    assert exits[0].selected_strategy == "exit_signal_reversal"


def test_exit_reduces_open_position_count() -> None:
    evaluator = PositionExitEvaluator(ExitConfig(stop_loss_pct=0.01))
    state = AccountState()
    pos1 = make_position("BTCUSDT", qty=1.0, entry=100.0, mark=88.0)
    pos2 = make_position("ETHUSDT", qty=1.0, entry=100.0, mark=100.0)
    state.upsert_position(pos1)
    state.upsert_position(pos2)
    features = {
        "BTCUSDT": make_feature("BTCUSDT", price=88.0),
        "ETHUSDT": make_feature("ETHUSDT", price=100.0),
    }
    now = datetime.now(timezone.utc)

    exits = evaluator.evaluate(state, features, {}, now)

    assert len(exits) == 1
    assert exits[0].symbol == "BTCUSDT"


def test_default_trailing_stop_does_not_trigger_at_old_1pct_threshold() -> None:
    """With new 2.5% default, a 1.5% retrace should NOT trigger trailing stop."""
    evaluator = PositionExitEvaluator()  # uses default ExitConfig with 0.025
    state = AccountState()
    pos = make_position("BTCUSDT", qty=1.0, entry=100.0, mark=100.5)
    state.upsert_position(pos)
    features = {"BTCUSDT": make_feature("BTCUSDT", price=100.5)}
    now = datetime.now(timezone.utc)
    meta = {"BTCUSDT": PositionEntryMeta(
        entry_time=now - timedelta(hours=1),
        peak_price=102.0,  # 1.47% retrace from 102 to 100.5
        strategy_name="trend_following",
    )}

    exits = evaluator.evaluate(state, features, meta, now)

    assert len(exits) == 0


def test_default_trailing_stop_triggers_at_new_2_5pct_threshold() -> None:
    """With new 2.5% default, a 3% retrace should trigger trailing stop."""
    evaluator = PositionExitEvaluator(ExitConfig(stop_loss_pct=1.0))  # disable stop loss
    state = AccountState()
    pos = make_position("BTCUSDT", qty=1.0, entry=100.0, mark=97.0)
    state.upsert_position(pos)
    features = {"BTCUSDT": make_feature("BTCUSDT", price=97.0)}
    now = datetime.now(timezone.utc)
    meta = {"BTCUSDT": PositionEntryMeta(
        entry_time=now - timedelta(hours=1),
        peak_price=100.0,  # 3% retrace from 100 to 97
        strategy_name="trend_following",
    )}

    exits = evaluator.evaluate(state, features, meta, now)

    assert len(exits) == 1
    assert exits[0].selected_strategy == "exit_trailing_stop"


def test_exception_in_one_position_does_not_block_others() -> None:
    evaluator = PositionExitEvaluator(ExitConfig(stop_loss_pct=0.01))
    state = AccountState()

    # Normal position that should trigger stop loss
    pos_good = make_position("ETHUSDT", qty=1.0, entry=100.0, mark=88.0)
    state.upsert_position(pos_good)

    # Corrupt position with zero entry price → division by zero in pnl_ratio
    pos_bad = make_position("BTCUSDT", qty=1.0, entry=0.0, mark=100.0)
    pos_bad.entry_price = Decimal("0")  # force zero to bypass make_position
    pos_bad.unrealized_pnl = Decimal("100")
    state.upsert_position(pos_bad)

    features = {
        "BTCUSDT": make_feature("BTCUSDT", price=100.0),
        "ETHUSDT": make_feature("ETHUSDT", price=88.0),
    }
    now = datetime.now(timezone.utc)

    exits = evaluator.evaluate(state, features, {}, now)

    # ETHUSDT should still get its exit even though BTCUSDT errored
    eth_exits = [e for e in exits if e.symbol == "ETHUSDT"]
    assert len(eth_exits) == 1
