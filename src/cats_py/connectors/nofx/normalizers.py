from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from cats_py.domain.models import FeatureVector


def _to_ratio(value: float | int | None, already_percent_literal: bool) -> float:
    if value is None:
        return 0.0
    result = float(value)
    return result / 100.0 if already_percent_literal else result


def normalize_timestamp(ts: int | float | None) -> datetime:
    if ts is None:
        return datetime.now(timezone.utc)
    ts_float = float(ts)
    if ts_float > 1_000_000_000_000:
        ts_float /= 1000.0
    return datetime.fromtimestamp(ts_float, tz=timezone.utc)


def ai300_level_to_score(level: str | None) -> float:
    mapping = {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.25}
    if level is None:
        return 0.0
    return mapping.get(level.upper(), 0.0)


def build_query_rank_map(query_rank_payload: dict[str, Any]) -> dict[str, int]:
    rankings = query_rank_payload.get("data", {}).get("rankings", [])
    result: dict[str, int] = {}
    for item in rankings:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        rank = item.get("rank")
        if isinstance(symbol, str) and isinstance(rank, int):
            key = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
            result[key] = rank
    return result


def build_ai300_level_map(ai300_payload: dict[str, Any]) -> dict[str, float]:
    coins = ai300_payload.get("data", {}).get("coins", [])
    result: dict[str, float] = {}
    for item in coins:
        if not isinstance(item, dict):
            continue
        symbol = item.get("symbol")
        if not isinstance(symbol, str):
            continue
        key = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
        result[key] = ai300_level_to_score(item.get("level"))
    return result


def normalize_coin_snapshot(
    symbol: str,
    coin_payload: dict[str, Any],
    funding_payload: dict[str, Any] | None = None,
    heatmap_payload: dict[str, Any] | None = None,
    query_rank: int | None = None,
    ai300_level_score: float = 0.0,
) -> FeatureVector:
    data = coin_payload.get("data", {})
    price_change = data.get("price_change", {})
    netflow = data.get("netflow", {})
    institution_future = netflow.get("institution", {}).get("future", {})
    personal_future = netflow.get("personal", {}).get("future", {})
    oi = data.get("oi", {})
    oi_binance = oi.get("binance", {}).get("delta", {}).get("1h", {})
    oi_bybit = oi.get("bybit", {}).get("delta", {}).get("1h", {})
    funding_data = (funding_payload or {}).get("data", {})
    heatmap_data = (heatmap_payload or {}).get("data", {}).get("heatmap", {})
    ai500 = data.get("ai500", {})

    ts = normalize_timestamp(
        funding_data.get("timestamp")
        or heatmap_data.get("timestamp")
        or data.get("timestamp")
        or datetime.now(timezone.utc).timestamp()
    )

    return FeatureVector(
        symbol=symbol,
        ts=ts,
        ai500_score=float(ai500.get("score", 0.0) or 0.0),
        ai300_level_score=ai300_level_score,
        price_change_15m=_to_ratio(price_change.get("15m"), already_percent_literal=False),
        price_change_1h=_to_ratio(price_change.get("1h"), already_percent_literal=False),
        price_change_4h=_to_ratio(price_change.get("4h"), already_percent_literal=False),
        inst_future_flow_15m=float(institution_future.get("15m", 0.0) or 0.0),
        inst_future_flow_1h=float(institution_future.get("1h", 0.0) or 0.0),
        inst_future_flow_4h=float(institution_future.get("4h", 0.0) or 0.0),
        retail_future_flow_1h=float(personal_future.get("1h", 0.0) or 0.0),
        oi_binance_1h=_to_ratio(oi_binance.get("oi_delta_percent"), already_percent_literal=True),
        oi_bybit_1h=_to_ratio(oi_bybit.get("oi_delta_percent"), already_percent_literal=True),
        funding_rate=_to_ratio(funding_data.get("funding_rate"), already_percent_literal=True),
        heatmap_delta=float(heatmap_data.get("delta", 0.0) or 0.0),
        query_rank=query_rank,
        stale_seconds=0.0,
        raw={
            "coin": coin_payload,
            "funding": funding_payload or {},
            "heatmap": heatmap_payload or {},
        },
    )
