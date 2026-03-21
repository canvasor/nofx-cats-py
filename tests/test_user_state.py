from decimal import Decimal

from cats_py.domain.enums import OrderLifecycleStatus, PositionDirection
from cats_py.services.user_state import BinanceUserEventHandler


def test_account_update_populates_balances_and_positions() -> None:
    handler = BinanceUserEventHandler()

    state = handler.apply(
        {
            "e": "ACCOUNT_UPDATE",
            "E": 1_770_000_000_000,
            "a": {
                "B": [
                    {"a": "USDT", "wb": "1000.0", "cw": "820.0"},
                ],
                "P": [
                    {
                        "s": "BTCUSDT",
                        "ps": "BOTH",
                        "pa": "0.010",
                        "ep": "50000",
                        "up": "25",
                        "mt": "cross",
                    }
                ],
            },
        }
    )

    assert state.balances["USDT"].wallet_balance == Decimal("1000.0")
    assert state.positions[("BTCUSDT", "BOTH")].direction == PositionDirection.LONG
    assert state.positions[("BTCUSDT", "BOTH")].unrealized_pnl == Decimal("25")


def test_order_trade_update_populates_order_state() -> None:
    handler = BinanceUserEventHandler()

    state = handler.apply(
        {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1_770_000_000_000,
            "o": {
                "s": "BTCUSDT",
                "i": 123456,
                "c": "order-1",
                "X": "PARTIALLY_FILLED",
                "S": "BUY",
                "o": "LIMIT",
                "p": "50000",
                "q": "0.010",
                "z": "0.005",
                "ps": "BOTH",
            },
        }
    )

    order = state.orders["order:123456"]
    assert order.status == OrderLifecycleStatus.PARTIALLY_FILLED
    assert order.executed_qty == Decimal("0.005")
    assert order.is_open is True


def test_algo_update_populates_algo_order_state() -> None:
    handler = BinanceUserEventHandler()

    state = handler.apply(
        {
            "e": "ALGO_UPDATE",
            "E": 1_770_000_000_000,
            "ao": {
                "s": "ETHUSDT",
                "ai": 999,
                "c": "algo-1",
                "status": "TRIGGERED",
                "side": "SELL",
                "type": "STOP_MARKET",
                "cp": True,
            },
        }
    )

    order = state.orders["algo:999"]
    assert order.status == OrderLifecycleStatus.TRIGGERED
    assert order.is_algo is True
    assert order.close_position is True
