from __future__ import annotations

from urllib.parse import urlencode

from .ws_base import BinanceWebSocketBase


class BinancePrivateStream(BinanceWebSocketBase):
    def __init__(self, base_url: str, listen_key: str, events: list[str]) -> None:
        query: list[tuple[str, str]] = [("listenKey", listen_key)]
        query.extend(("events", event) for event in events)
        url = f"{base_url.rstrip('/')}/stream?{urlencode(query)}"
        super().__init__(url)
