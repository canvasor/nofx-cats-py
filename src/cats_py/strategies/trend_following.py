from __future__ import annotations

from cats_py.domain.enums import MarketRegime, Side
from cats_py.domain.models import FeatureVector, SignalCandidate
from cats_py.strategies.base import Strategy


class TrendFollowingStrategy(Strategy):
    name = "trend_following"

    def generate(self, feature: FeatureVector) -> SignalCandidate | None:
        ai_gate = max(feature.ai500_score / 100.0, feature.ai300_level_score)
        if ai_gate < 0.70:
            return None

        if feature.crowding_score > 0.02:
            return None

        if feature.trend_score > 0 and feature.flow_score > 0 and feature.oi_score > 0:
            return SignalCandidate(
                symbol=feature.symbol,
                regime=MarketRegime.TREND,
                side=Side.BUY,
                conviction=min(1.0, 0.45 + abs(feature.trend_score) * 5 + ai_gate * 0.15),
                expected_edge_bps=18.0,
                stop_distance_pct=max(0.008, abs(feature.price_change_15m) * 2),
                rationale=[
                    "AI score gate active",
                    "price trend aligned across 15m/1h/4h",
                    "institutional futures flow positive",
                    "Binance and Bybit OI expansion aligned",
                    "crowding not yet extreme",
                ],
                strategy_name=self.name,
            )

        if feature.trend_score < 0 and feature.flow_score < 0 and feature.oi_score > 0:
            return SignalCandidate(
                symbol=feature.symbol,
                regime=MarketRegime.TREND,
                side=Side.SELL,
                conviction=min(1.0, 0.45 + abs(feature.trend_score) * 5 + ai_gate * 0.15),
                expected_edge_bps=18.0,
                stop_distance_pct=max(0.008, abs(feature.price_change_15m) * 2),
                rationale=[
                    "AI score gate active",
                    "negative trend aligned across multiple windows",
                    "institutional futures flow negative",
                    "OI remains elevated, downside continuation risk present",
                    "crowding not yet extreme",
                ],
                strategy_name=self.name,
            )

        return None
