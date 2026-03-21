from __future__ import annotations

import asyncio

from cats_py.app.bootstrap import bootstrap
from cats_py.connectors.binance.user_stream import UserStreamSession
from cats_py.connectors.binance.ws_market import BinanceMarketStream
from cats_py.connectors.binance.ws_private import BinancePrivateStream
from cats_py.connectors.binance.ws_public import BinancePublicStream
from cats_py.infra.storage import JsonlStorage


async def consume(name: str, stream, storage: JsonlStorage) -> None:
    count = 0
    async for message in stream.messages():
        storage.append(f"binance_{name}", message)
        print(f"[{name}] {message}")
        count += 1
        if count >= 3:
            break


async def main() -> None:
    services = bootstrap()
    runtime = services["runtime"]
    binance = services["binance"]
    storage = JsonlStorage(base_dir="data")

    user_session = UserStreamSession(binance)
    listen_key = await user_session.start()

    public_stream = BinancePublicStream(
        runtime.binance_ws_public_url,
        streams=["btcusdt@depth", "ethusdt@bookTicker"],
    )
    market_stream = BinanceMarketStream(
        runtime.binance_ws_market_url,
        streams=["btcusdt@markPrice", "btcusdt@kline_1m"],
    )
    private_stream = BinancePrivateStream(
        runtime.binance_ws_private_url,
        listen_key=listen_key,
        events=["ORDER_TRADE_UPDATE", "ACCOUNT_UPDATE", "ALGO_UPDATE"],
    )

    try:
        await asyncio.gather(
            consume("public", public_stream, storage),
            consume("market", market_stream, storage),
            consume("private", private_stream, storage),
        )
    finally:
        await user_session.close()
        await binance.close()


if __name__ == "__main__":
    asyncio.run(main())
