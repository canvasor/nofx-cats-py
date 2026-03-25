from __future__ import annotations

from cats_py.domain.enums import MarketRegime, Side
from cats_py.domain.models import FeatureVector, SignalCandidate
from cats_py.strategies.base import Strategy


class CrowdingReversalStrategy(Strategy):
    name = "crowding_reversal"

    def generate(self, feature: FeatureVector) -> SignalCandidate | None:
        hot = (feature.query_rank or 999) <= 5
        long_crowded = feature.funding_rate >= 0.0015 and hot
        short_crowded = feature.funding_rate <= -0.0015 and hot

        if long_crowded and feature.heatmap_delta <= 0 and feature.price_change_15m <= 0:
            return SignalCandidate(
                symbol=feature.symbol,
                regime=MarketRegime.CROWDING,
                side=Side.SELL,
                conviction=min(0.95, 0.45 + abs(feature.funding_rate) * 100 + 0.1),
                expected_edge_bps=16.0,
                stop_distance_pct=max(0.007, abs(feature.price_change_15m) * 1.5),
                rationale=[
                    "positive funding indicates crowded longs",
                    "community heat remains elevated",
                    "heatmap delta is no longer bid-dominant",
                    "short-term price impulse has stalled",
                ],
                strategy_name=self.name,
            )

        if short_crowded and feature.heatmap_delta >= 0 and feature.price_change_15m >= 0:
            return SignalCandidate(
                symbol=feature.symbol,
                regime=MarketRegime.CROWDING,
                side=Side.BUY,
                conviction=min(0.95, 0.45 + abs(feature.funding_rate) * 100 + 0.1),
                expected_edge_bps=16.0,
                stop_distance_pct=max(0.007, abs(feature.price_change_15m) * 1.5),
                rationale=[
                    "negative funding indicates crowded shorts",
                    "community heat remains elevated",
                    "heatmap delta turned bid-dominant",
                    "short-term price impulse is recovering",
                ],
                strategy_name=self.name,
            )

        return None

    def skip_reason(self, feature: FeatureVector) -> str:
        hot = (feature.query_rank or 999) <= 5
        if not hot:
            return "crowding_reversal: symbol is not hot enough"
        if abs(feature.funding_rate) < 0.0015:
            return "crowding_reversal: funding is not extreme enough"
        if feature.heatmap_delta == 0:
            return "crowding_reversal: heatmap shows no reversal bias"
        if feature.price_change_15m == 0:
            return "crowding_reversal: short-term price impulse is flat"
        return "crowding_reversal: reversal confirmation is incomplete"
