from __future__ import annotations

from cats_py.domain.enums import MarketRegime, Side
from cats_py.domain.models import FeatureVector, SignalCandidate
from cats_py.strategies.base import Strategy


class RangeReversionStrategy(Strategy):
    name = "range_reversion"

    def generate(self, feature: FeatureVector) -> SignalCandidate | None:
        ai_gate = max(feature.ai500_score / 100.0, feature.ai300_level_score)
        if ai_gate < 0.55:
            return None
        if abs(feature.price_change_15m) < 0.004:
            return None
        if abs(feature.trend_score) > 0.05:
            return None
        if abs(feature.funding_rate) > 0.0025:
            return None

        if feature.price_change_15m > 0 and feature.heatmap_delta < 0 and feature.flow_score <= 0:
            return SignalCandidate(
                symbol=feature.symbol,
                regime=MarketRegime.RANGE,
                side=Side.SELL,
                conviction=min(0.9, 0.45 + abs(feature.price_change_15m) * 8 + ai_gate * 0.10),
                expected_edge_bps=12.0,
                stop_distance_pct=max(0.006, abs(feature.price_change_15m) * 1.25),
                rationale=[
                    "short-term upside stretch is fading",
                    "heatmap turned offer-heavy inside a range regime",
                    "institutional futures flow is no longer supportive",
                    "crowding remains contained for a mean-reversion setup",
                ],
                strategy_name=self.name,
            )

        if feature.price_change_15m < 0 and feature.heatmap_delta > 0 and feature.flow_score >= 0:
            return SignalCandidate(
                symbol=feature.symbol,
                regime=MarketRegime.RANGE,
                side=Side.BUY,
                conviction=min(0.9, 0.45 + abs(feature.price_change_15m) * 8 + ai_gate * 0.10),
                expected_edge_bps=12.0,
                stop_distance_pct=max(0.006, abs(feature.price_change_15m) * 1.25),
                rationale=[
                    "short-term downside stretch is fading",
                    "heatmap turned bid-heavy inside a range regime",
                    "institutional futures flow stopped deteriorating",
                    "crowding remains contained for a mean-reversion setup",
                ],
                strategy_name=self.name,
            )

        return None

    def skip_reason(self, feature: FeatureVector) -> str:
        ai_gate = max(feature.ai500_score / 100.0, feature.ai300_level_score)
        if ai_gate < 0.55:
            return "range_reversion: ai gate below threshold"
        if abs(feature.price_change_15m) < 0.004:
            return "range_reversion: short-term extension is too small"
        if abs(feature.trend_score) > 0.05:
            return "range_reversion: market is trending, not ranging"
        if abs(feature.funding_rate) > 0.0025:
            return "range_reversion: crowding is too elevated for mean reversion"
        if feature.heatmap_delta == 0:
            return "range_reversion: heatmap shows no contra move"
        return "range_reversion: flow and heatmap do not confirm reversal"
