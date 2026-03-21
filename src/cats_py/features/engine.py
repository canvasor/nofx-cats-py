from __future__ import annotations

from datetime import datetime, timezone

from cats_py.domain.models import FeatureVector


class FeatureEngine:
    def enrich(self, feature: FeatureVector) -> FeatureVector:
        now = datetime.now(timezone.utc)
        feature.stale_seconds = max((now - feature.ts).total_seconds(), 0.0)
        feature.trend_score = feature.price_change_15m + feature.price_change_1h + feature.price_change_4h
        feature.flow_score = feature.inst_future_flow_15m + feature.inst_future_flow_1h + feature.inst_future_flow_4h
        feature.oi_score = feature.oi_binance_1h + feature.oi_bybit_1h
        query_heat = 0.01 if (feature.query_rank or 999) <= 5 else 0.0
        feature.crowding_score = abs(feature.funding_rate) + query_heat
        feature.source_freshness = max(0.0, 1.0 - min(feature.stale_seconds, 45.0) / 45.0)
        return feature
