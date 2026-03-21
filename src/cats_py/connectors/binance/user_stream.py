from __future__ import annotations

import asyncio
from contextlib import suppress

from cats_py.connectors.binance.rest import BinanceRestClient


class UserStreamSession:
    """Start and keep alive a USDⓈ-M listenKey for long-running consumers."""

    def __init__(self, client: BinanceRestClient, keepalive_interval_seconds: int = 50 * 60) -> None:
        self.client = client
        self.keepalive_interval_seconds = keepalive_interval_seconds
        self.listen_key: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> str:
        response = await self.client.start_user_stream()
        listen_key = response["data"]["listenKey"]
        if not isinstance(listen_key, str) or not listen_key:
            raise ValueError("listenKey missing in start_user_stream response")
        self.listen_key = listen_key
        self._running = True
        self._task = asyncio.create_task(self._keepalive_loop(), name="binance-listenkey-keepalive")
        return listen_key

    async def _keepalive_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.keepalive_interval_seconds)
            await self.client.keepalive_user_stream()

    async def close(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
