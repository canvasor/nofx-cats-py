from __future__ import annotations

import asyncio
from decimal import Decimal

from cats_py.connectors.binance.rest import BinanceRestClient
from cats_py.domain.enums import Side
from cats_py.domain.models import OrderResponse
from cats_py.execution.order_router import OrderRouter


class PositionGuardian:
    """维护交易所侧 auto-cancel 心跳，并可挂出灾难止损。"""

    def __init__(
        self,
        binance: BinanceRestClient,
        router: OrderRouter | None = None,
        heartbeat_seconds: int = 30,
        countdown_ms: int = 120000,
    ) -> None:
        self.binance = binance
        self.router = router
        self.heartbeat_seconds = heartbeat_seconds
        self.countdown_ms = countdown_ms
        self._running = True

    async def maintain_auto_cancel(self, symbol: str) -> None:
        while self._running:
            await self.binance.countdown_cancel_all(symbol=symbol, countdown_ms=self.countdown_ms)
            await asyncio.sleep(self.heartbeat_seconds)

    async def place_disaster_stop(
        self,
        *,
        symbol: str,
        exit_side: Side,
        trigger_price: Decimal,
        position_side: str = "BOTH",
        client_order_id: str | None = None,
    ) -> OrderResponse:
        if self.router is None:
            raise RuntimeError("PositionGuardian requires an OrderRouter to place disaster stops")
        request = OrderRouter.build_disaster_stop_request(
            symbol=symbol,
            exit_side=exit_side,
            trigger_price=trigger_price,
            position_side=position_side,
            client_order_id=client_order_id,
        )
        return await self.router.place(request)

    def stop(self) -> None:
        self._running = False
