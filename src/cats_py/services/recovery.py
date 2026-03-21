from __future__ import annotations

import logging

from cats_py.services.reconciliation import AccountReconciler


class UserStreamRecoveryCoordinator:
    def __init__(self, reconciler: AccountReconciler, logger: logging.Logger) -> None:
        self.reconciler = reconciler
        self.logger = logger

    async def on_private_stream_connect(self, connection_count: int) -> None:
        account_state = await self.reconciler.reconcile()
        self.logger.info(
            "user_stream_state_rebuilt",
            extra={
                "connection_count": connection_count,
                "reason": "initial_connect" if connection_count == 1 else "reconnect",
                "open_positions": account_state.open_position_count(),
                "tracked_orders": len(account_state.orders),
            },
        )

    async def on_private_stream_disconnect(self, connection_count: int, reason: str) -> None:
        self.logger.warning(
            "user_stream_disconnected",
            extra={"connection_count": connection_count, "reason": reason},
        )
