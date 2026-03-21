from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class InMemoryEventBus:
    """适合 Python v1 的最小事件总线。"""

    def __init__(self) -> None:
        self._topics: dict[str, list[asyncio.Queue[Any]]] = defaultdict(list)

    def subscribe(self, topic: str) -> asyncio.Queue[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._topics[topic].append(queue)
        return queue

    async def publish(self, topic: str, payload: Any) -> None:
        for queue in self._topics[topic]:
            await queue.put(payload)
