from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from collections.abc import AsyncIterator
from typing import Any

import websockets


ConnectHook = Callable[[int], Awaitable[None] | None]
DisconnectHook = Callable[[int, str], Awaitable[None] | None]


class BinanceWebSocketBase:
    def __init__(self, url: str) -> None:
        self.url = url
        self.logger = logging.getLogger("cats_py.connectors.binance.ws")

    async def messages(
        self,
        *,
        on_connect: ConnectHook | None = None,
        on_disconnect: DisconnectHook | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        connection_count = 0
        while True:
            try:
                async with websockets.connect(self.url, ping_interval=120, ping_timeout=30) as ws:
                    connection_count += 1
                    await self._run_connect_hook(on_connect, connection_count)
                    async for raw in ws:
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        payload = json.loads(raw)
                        if isinstance(payload, dict):
                            yield payload
            except Exception as exc:  # noqa: BLE001
                await self._run_disconnect_hook(on_disconnect, connection_count, str(exc))
                self.logger.warning("ws_reconnect", extra={"url": self.url, "reason": str(exc)})
                await asyncio.sleep(2)

    async def _run_connect_hook(self, hook: ConnectHook | None, connection_count: int) -> None:
        if hook is None:
            return
        try:
            result = hook(connection_count)
            if result is not None:
                await result
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "ws_connect_hook_failed",
                extra={"url": self.url, "connection_count": connection_count, "reason": str(exc)},
            )

    async def _run_disconnect_hook(
        self,
        hook: DisconnectHook | None,
        connection_count: int,
        reason: str,
    ) -> None:
        if hook is None:
            return
        try:
            result = hook(connection_count, reason)
            if result is not None:
                await result
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(
                "ws_disconnect_hook_failed",
                extra={"url": self.url, "connection_count": connection_count, "reason": str(exc)},
            )
