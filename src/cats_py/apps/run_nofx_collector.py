from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from cats_py.app.bootstrap import bootstrap
from cats_py.connectors.nofx.normalizers import (
    build_ai300_level_map,
    build_query_rank_map,
    normalize_coin_snapshot,
)
from cats_py.infra.storage import JsonlStorage, json_ready
from cats_py.services.universe import UniverseBuilder


async def main() -> None:
    services = bootstrap()
    nofx = services["nofx"]
    storage = JsonlStorage(base_dir="data")

    assert hasattr(nofx, "ai500_list")
    assert hasattr(nofx, "ai300_list")
    assert hasattr(nofx, "query_rank")

    ai500 = await nofx.ai500_list(limit=20)
    ai300 = await nofx.ai300_list(limit=20)
    query_rank = await nofx.query_rank(limit=20)

    storage.append_snapshot("nofx_ai500", ai500, source="nofx", endpoint="/api/ai500/list", params={"limit": 20})
    storage.append_snapshot("nofx_ai300", ai300, source="nofx", endpoint="/api/ai300/list", params={"limit": 20})
    storage.append_snapshot(
        "nofx_query_rank",
        query_rank,
        source="nofx",
        endpoint="/api/query-rank/list",
        params={"limit": 20},
    )

    query_rank_map = build_query_rank_map(query_rank)
    ai300_level_map = build_ai300_level_map(ai300)
    universe = UniverseBuilder().build(ai500, ai300)
    print("[collector] universe:", universe)

    for symbol in universe[:10]:
        base_symbol = symbol.replace("USDT", "")
        fetched_at = datetime.now(timezone.utc)
        coin = await nofx.coin(symbol)
        funding = await nofx.funding_rate(base_symbol)
        heatmap = await nofx.heatmap_future(base_symbol)

        storage.append_snapshot(
            "nofx_coin_raw",
            coin,
            source="nofx",
            endpoint=f"/api/coin/{symbol}",
            params={},
            fetched_at=fetched_at,
            tags={"symbol": symbol},
        )
        storage.append_snapshot(
            "nofx_funding_raw",
            funding,
            source="nofx",
            endpoint=f"/api/funding-rate/{base_symbol}",
            params={},
            fetched_at=fetched_at,
            tags={"symbol": symbol},
        )
        storage.append_snapshot(
            "nofx_heatmap_raw",
            heatmap,
            source="nofx",
            endpoint=f"/api/heatmap/future/{base_symbol}",
            params={},
            fetched_at=fetched_at,
            tags={"symbol": symbol},
        )

        normalized = normalize_coin_snapshot(
            symbol,
            coin,
            funding,
            heatmap,
            query_rank=query_rank_map.get(symbol),
            ai300_level_score=ai300_level_map.get(symbol, 0.0),
        )
        storage.append(
            "nofx_normalized",
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "payload": json_ready(normalized),
            },
        )
        print(f"[collector] normalized {symbol}")

    await nofx.close()


if __name__ == "__main__":
    asyncio.run(main())
