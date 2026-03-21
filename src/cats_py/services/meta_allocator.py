from __future__ import annotations

from cats_py.domain.enums import MarketRegime, Side
from cats_py.domain.models import FeatureVector, SignalCandidate


class MetaAllocator:
    """Rule-based scorer used in v2 to rank candidate actions before risk approval."""

    def score(self, signal: SignalCandidate, feature: FeatureVector, regime: MarketRegime) -> float:
        base = signal.expected_edge_bps * max(signal.conviction, 0.1)
        stale_penalty = min(feature.stale_seconds, 45.0) * 0.20
        heatmap_alignment = 0.0
        if signal.side == Side.BUY and feature.heatmap_delta > 0:
            heatmap_alignment = 3.0
        elif signal.side == Side.SELL and feature.heatmap_delta < 0:
            heatmap_alignment = 3.0
        elif feature.heatmap_delta != 0:
            heatmap_alignment = -1.5

        hot_bonus = 1.5 if (feature.query_rank or 999) <= 5 else 0.0
        if signal.strategy_name == "trend_following":
            regime_bonus = 4.0 if regime == MarketRegime.TREND else -2.0
            crowding_adjustment = -abs(feature.funding_rate) * 2000
        elif signal.strategy_name == "crowding_reversal":
            regime_bonus = 4.0 if regime == MarketRegime.CROWDING else -1.0
            crowding_adjustment = abs(feature.funding_rate) * 1500 + hot_bonus
        else:
            regime_bonus = 0.0
            crowding_adjustment = 0.0

        score = base + heatmap_alignment + regime_bonus + crowding_adjustment - stale_penalty
        return round(score, 4)
