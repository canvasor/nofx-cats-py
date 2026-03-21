from datetime import datetime, timedelta, timezone
from decimal import Decimal

from cats_py.domain.enums import OrderLifecycleStatus, PositionDirection, Side
from cats_py.domain.models import AccountState, BalanceState, OrderState, PositionState


def test_order_state_identity_and_open_flag() -> None:
    order = OrderState(
        symbol="BTCUSDT",
        status=OrderLifecycleStatus.PARTIALLY_FILLED,
        side=Side.BUY,
        order_id="12345",
        client_order_id="client-1",
        executed_qty=Decimal("0.001"),
    )

    assert order.identity == "order:12345"
    assert order.is_open is True


def test_account_state_builds_risk_snapshot_from_balances_and_positions() -> None:
    account = AccountState()
    account.upsert_balance(
        BalanceState(
            asset="USDT",
            wallet_balance=Decimal("1000"),
            available_balance=Decimal("850"),
        )
    )
    account.upsert_position(
        PositionState(
            symbol="BTCUSDT",
            position_side="BOTH",
            direction=PositionDirection.LONG,
            quantity=Decimal("0.010"),
            mark_price=Decimal("50000"),
            notional=Decimal("500"),
            unrealized_pnl=Decimal("50"),
        )
    )
    account.record_user_stream_event(datetime.now(timezone.utc) - timedelta(seconds=12))

    snapshot = account.to_snapshot(daily_drawdown_pct=-0.4, weekly_drawdown_pct=-1.1)

    assert snapshot.equity == 1050.0
    assert round(snapshot.gross_exposure, 4) == round(500.0 / 1050.0, 4)
    assert round(snapshot.symbol_gross_exposures["BTCUSDT"], 4) == round(500.0 / 1050.0, 4)
    assert snapshot.open_positions == 1
    assert snapshot.user_stream_stale_seconds >= 12.0


def test_account_state_ignores_flat_positions_in_exposure() -> None:
    account = AccountState()
    account.upsert_balance(BalanceState(asset="USDT", wallet_balance=Decimal("500")))
    account.upsert_position(
        PositionState(
            symbol="ETHUSDT",
            position_side="BOTH",
            direction=PositionDirection.FLAT,
            quantity=Decimal("0"),
            mark_price=Decimal("2500"),
            notional=Decimal("0"),
        )
    )

    snapshot = account.to_snapshot()

    assert snapshot.equity == 500.0
    assert snapshot.gross_exposure == 0.0
    assert snapshot.symbol_gross_exposures == {}
    assert snapshot.open_positions == 0
