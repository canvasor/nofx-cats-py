import asyncio
from decimal import Decimal

from cats_py.domain.models import AccountState, BalanceState
from cats_py.domain.enums import OrderLifecycleStatus, PositionDirection
from cats_py.services.reconciliation import AccountReconciler


class DummyBinanceAccountReader:
    async def get_account_info(self) -> dict[str, object]:
        return {
            "data": {
                "assets": [
                    {
                        "asset": "USDT",
                        "walletBalance": "1000.0",
                        "availableBalance": "800.0",
                        "crossWalletBalance": "800.0",
                    }
                ],
                "positions": [
                    {
                        "symbol": "BTCUSDT",
                        "positionSide": "BOTH",
                        "positionAmt": "0.010",
                        "entryPrice": "50000",
                        "unrealizedProfit": "20",
                        "leverage": "3",
                        "marginType": "cross",
                        "isolatedWallet": "0",
                    }
                ],
            }
        }

    async def get_position_risk(self, symbol: str | None = None) -> dict[str, object]:
        return {
            "data": [
                {
                    "symbol": "BTCUSDT",
                    "positionSide": "BOTH",
                    "markPrice": "51000",
                    "notional": "510",
                }
            ]
        }

    async def get_open_orders(self, symbol: str | None = None) -> dict[str, object]:
        return {
            "data": [
                {
                    "symbol": "BTCUSDT",
                    "orderId": 123,
                    "clientOrderId": "open-1",
                    "status": "NEW",
                    "side": "BUY",
                    "positionSide": "BOTH",
                    "type": "LIMIT",
                    "price": "49500",
                    "avgPrice": "0",
                    "origQty": "0.010",
                    "executedQty": "0.000",
                    "reduceOnly": False,
                    "closePosition": False,
                    "time": 1_770_000_000_000,
                    "updateTime": 1_770_000_000_500,
                }
            ]
        }


def test_account_reconciler_replaces_state_from_full_snapshots() -> None:
    reconciler = AccountReconciler(DummyBinanceAccountReader())

    state = asyncio.run(reconciler.reconcile())

    assert state.balances["USDT"].wallet_balance == Decimal("1000.0")
    position = state.positions[("BTCUSDT", "BOTH")]
    assert position.direction == PositionDirection.LONG
    assert position.mark_price == Decimal("51000")
    assert position.notional == Decimal("510")
    assert state.orders["order:123"].status == OrderLifecycleStatus.NEW
    assert state.last_reconciled_at is not None


def test_account_reconciler_snapshot_matches_reconciled_state() -> None:
    reconciler = AccountReconciler(DummyBinanceAccountReader())

    state = asyncio.run(reconciler.reconcile())
    snapshot = state.to_snapshot()

    assert snapshot.equity == 1020.0
    assert round(snapshot.gross_exposure, 2) == 0.5
    assert snapshot.open_positions == 1


def test_account_reconciler_marks_mismatch_when_incremental_state_diverges() -> None:
    account_state = AccountState()
    account_state.upsert_balance(
        BalanceState(
            asset="USDT",
            wallet_balance=Decimal("999.0"),
            available_balance=Decimal("799.0"),
            cross_wallet_balance=Decimal("799.0"),
        )
    )
    reconciler = AccountReconciler(DummyBinanceAccountReader(), account_state=account_state)

    state = asyncio.run(reconciler.reconcile())

    assert state.state_mismatch_count == 1
    assert state.last_mismatch_reason is not None


class FailingBinanceAccountReader:
    async def get_account_info(self) -> dict[str, object]:
        raise RuntimeError("account endpoint unavailable")

    async def get_position_risk(self, symbol: str | None = None) -> dict[str, object]:
        return {"data": []}

    async def get_open_orders(self, symbol: str | None = None) -> dict[str, object]:
        return {"data": []}


def test_account_reconciler_records_failures_and_kill_switch() -> None:
    reconciler = AccountReconciler(FailingBinanceAccountReader(), account_state=AccountState())

    for _ in range(2):
        try:
            asyncio.run(reconciler.reconcile())
        except RuntimeError:
            pass

    assert reconciler.account_state.reconcile_failure_count == 2
    assert reconciler.account_state.kill_switch_active is True
