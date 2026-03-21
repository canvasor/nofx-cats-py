from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from cats_py.app.bootstrap import bootstrap
from cats_py.connectors.nofx.normalizers import normalize_coin_snapshot
from cats_py.domain.models import AccountSnapshot
from cats_py.infra.storage import JsonlStorage
from cats_py.journal.recorder import JournalRecorder


async def main() -> None:
    services = bootstrap()
    nofx = services["nofx"]
    decision_engine = services["decision_engine"]
    storage = JsonlStorage(base_dir="data")
    journal = JournalRecorder(storage)

    symbol = "BTCUSDT"
    coin = await nofx.coin(symbol)
    funding = await nofx.funding_rate("BTC")
    heatmap = await nofx.heatmap_future("BTC")
    feature = normalize_coin_snapshot(symbol, coin, funding, heatmap)

    account = AccountSnapshot(
        equity=10_000.0,
        daily_drawdown_pct=-0.3,
        weekly_drawdown_pct=-1.2,
        gross_exposure=0.25,
        open_positions=1,
        user_stream_stale_seconds=0.0,
    )

    decision = decision_engine.decide(feature, account)
    journal.record(
        "decision_log",
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
        },
    )
    print("[decision]", decision)

    await nofx.close()


if __name__ == "__main__":
    asyncio.run(main())
