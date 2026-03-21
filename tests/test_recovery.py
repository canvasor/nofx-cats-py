import asyncio
import logging
from decimal import Decimal

from cats_py.domain.models import AccountState
from cats_py.services.reconciliation import AccountReconciler
from cats_py.services.recovery import UserStreamRecoveryCoordinator


class DummyReader:
    async def get_account_info(self) -> dict[str, object]:
        return {
            "data": {
                "assets": [
                    {
                        "asset": "USDT",
                        "walletBalance": "1000.0",
                        "availableBalance": "900.0",
                        "crossWalletBalance": "900.0",
                    }
                ],
                "positions": [],
            }
        }

    async def get_position_risk(self, symbol: str | None = None) -> dict[str, object]:
        return {"data": []}

    async def get_open_orders(self, symbol: str | None = None) -> dict[str, object]:
        return {"data": []}


def test_user_stream_recovery_coordinator_rebuilds_state_on_connect(caplog) -> None:
    logger = logging.getLogger("test.recovery")
    reconciler = AccountReconciler(DummyReader(), account_state=AccountState())
    coordinator = UserStreamRecoveryCoordinator(reconciler, logger)

    with caplog.at_level(logging.INFO):
        asyncio.run(coordinator.on_private_stream_connect(2))

    balance = reconciler.account_state.balances["USDT"]
    assert balance.wallet_balance == Decimal("1000.0")
    assert balance.available_balance == Decimal("900.0")
    assert balance.cross_wallet_balance == Decimal("900.0")
    assert any("user_stream_state_rebuilt" in message for message in caplog.messages)


def test_user_stream_recovery_coordinator_logs_disconnect(caplog) -> None:
    logger = logging.getLogger("test.recovery")
    reconciler = AccountReconciler(DummyReader(), account_state=AccountState())
    coordinator = UserStreamRecoveryCoordinator(reconciler, logger)

    with caplog.at_level(logging.WARNING):
        asyncio.run(coordinator.on_private_stream_disconnect(3, "connection reset"))

    assert any("user_stream_disconnected" in message for message in caplog.messages)
