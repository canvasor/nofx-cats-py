from __future__ import annotations

from urllib.parse import quote

from .ws_base import BinanceWebSocketBase


class BinanceMarketStream(BinanceWebSocketBase):
    def __init__(self, base_url: str, streams: list[str]) -> None:
        stream_query = "/".join(quote(stream) for stream in streams)
        url = f"{base_url.rstrip('/')}/stream?streams={stream_query}"
        super().__init__(url)
