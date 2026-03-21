from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import websockets


class BinanceWebSocketBase:
    def __init__(self, url: str) -> None:
        self.url = url

    async def messages(self) -> AsyncIterator[dict[str, Any]]:
        while True:
            try:
                async with websockets.connect(self.url, ping_interval=120, ping_timeout=30) as ws:
                    async for raw in ws:
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        payload = json.loads(raw)
                        if isinstance(payload, dict):
                            yield payload
            except Exception as exc:  # noqa: BLE001
                print(f"[ws reconnect] {self.url} -> {exc}")
                await asyncio.sleep(2)
