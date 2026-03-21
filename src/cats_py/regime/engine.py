from __future__ import annotations

from cats_py.domain.enums import MarketRegime
from cats_py.domain.models import FeatureVector


class RegimeEngine:
    """规则化 regime engine。v2 增强了 crowding / defense 检测。"""

    def detect(self, feature: FeatureVector) -> MarketRegime:
        if feature.stale_seconds > 45:
            return MarketRegime.DEFENSE

        if feature.crowding_score > 0.03:
            return MarketRegime.CROWDING

        if abs(feature.trend_score) > 0.05 and abs(feature.oi_score) > 0.005:
            return MarketRegime.TREND

        if abs(feature.heatmap_delta) > 0 and abs(feature.trend_score) <= 0.05:
            return MarketRegime.RANGE

        return MarketRegime.UNKNOWN
