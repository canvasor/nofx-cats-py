from datetime import datetime, timezone

from cats_py.domain.enums import MarketRegime, Side
from cats_py.domain.models import FeatureVector
from cats_py.strategies.trend_following import TrendFollowingStrategy
from cats_py.strategies.range_reversion import RangeReversionStrategy
from cats_py.strategies.crowding_reversal import CrowdingReversalStrategy


def make_feature(**overrides) -> FeatureVector:
    defaults = dict(
        symbol="BTCUSDT",
        ts=datetime.now(timezone.utc),
        reference_price=50000.0,
        ai500_score=75.0,
        ai300_level_score=0.0,
        price_change_15m=0.0,
        price_change_1h=0.0,
        price_change_4h=0.0,
        inst_future_flow_15m=0.0,
        inst_future_flow_1h=0.0,
        inst_future_flow_4h=0.0,
        oi_binance_1h=0.0,
        oi_bybit_1h=0.0,
        funding_rate=0.0,
        heatmap_delta=0.0,
        query_rank=None,
        trend_score=0.0,
        flow_score=0.0,
        oi_score=0.0,
        crowding_score=0.0,
        source_freshness=1.0,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


# ── TrendFollowingStrategy ──────────────────────────────────────


class TestTrendFollowing:
    def test_buy_signal(self) -> None:
        strategy = TrendFollowingStrategy()
        feature = make_feature(
            trend_score=0.1,
            flow_score=0.05,
            oi_score=0.01,
            crowding_score=0.005,
        )
        signal = strategy.generate(feature)
        assert signal is not None
        assert signal.side == Side.BUY
        assert signal.strategy_name == "trend_following"
        assert signal.regime == MarketRegime.TREND

    def test_sell_signal(self) -> None:
        strategy = TrendFollowingStrategy()
        feature = make_feature(
            trend_score=-0.1,
            flow_score=-0.05,
            oi_score=0.01,
            crowding_score=0.005,
        )
        signal = strategy.generate(feature)
        assert signal is not None
        assert signal.side == Side.SELL

    def test_rejected_ai_gate_below_threshold(self) -> None:
        strategy = TrendFollowingStrategy()
        feature = make_feature(
            ai500_score=50.0,
            trend_score=0.1,
            flow_score=0.05,
            oi_score=0.01,
        )
        signal = strategy.generate(feature)
        assert signal is None

    def test_rejected_crowding_too_high(self) -> None:
        strategy = TrendFollowingStrategy()
        feature = make_feature(
            trend_score=0.1,
            flow_score=0.05,
            oi_score=0.01,
            crowding_score=0.025,
        )
        signal = strategy.generate(feature)
        assert signal is None

    def test_rejected_oi_not_expanding(self) -> None:
        strategy = TrendFollowingStrategy()
        feature = make_feature(
            trend_score=0.1,
            flow_score=0.05,
            oi_score=-0.01,
        )
        signal = strategy.generate(feature)
        assert signal is None

    def test_rejected_trend_and_flow_not_aligned(self) -> None:
        strategy = TrendFollowingStrategy()
        feature = make_feature(
            trend_score=0.1,
            flow_score=-0.05,
            oi_score=0.01,
        )
        signal = strategy.generate(feature)
        assert signal is None


# ── RangeReversionStrategy ───────────────────────────────────────


class TestRangeReversion:
    def test_sell_signal(self) -> None:
        strategy = RangeReversionStrategy()
        feature = make_feature(
            price_change_15m=0.005,
            heatmap_delta=-100.0,
            flow_score=-0.01,
            trend_score=0.01,
            funding_rate=0.001,
        )
        signal = strategy.generate(feature)
        assert signal is not None
        assert signal.side == Side.SELL
        assert signal.strategy_name == "range_reversion"

    def test_buy_signal(self) -> None:
        strategy = RangeReversionStrategy()
        feature = make_feature(
            price_change_15m=-0.005,
            heatmap_delta=100.0,
            flow_score=0.01,
            trend_score=-0.01,
            funding_rate=0.001,
        )
        signal = strategy.generate(feature)
        assert signal is not None
        assert signal.side == Side.BUY

    def test_rejected_ai_gate_below_threshold(self) -> None:
        strategy = RangeReversionStrategy()
        feature = make_feature(
            ai500_score=40.0,
            price_change_15m=0.005,
            heatmap_delta=-100.0,
            flow_score=-0.01,
        )
        signal = strategy.generate(feature)
        assert signal is None

    def test_rejected_extension_too_small(self) -> None:
        strategy = RangeReversionStrategy()
        feature = make_feature(
            price_change_15m=0.002,
            heatmap_delta=-100.0,
            flow_score=-0.01,
        )
        signal = strategy.generate(feature)
        assert signal is None

    def test_rejected_trending_market(self) -> None:
        strategy = RangeReversionStrategy()
        feature = make_feature(
            price_change_15m=0.005,
            heatmap_delta=-100.0,
            flow_score=-0.01,
            trend_score=0.08,
        )
        signal = strategy.generate(feature)
        assert signal is None

    def test_rejected_funding_extreme(self) -> None:
        strategy = RangeReversionStrategy()
        feature = make_feature(
            price_change_15m=0.005,
            heatmap_delta=-100.0,
            flow_score=-0.01,
            trend_score=0.01,
            funding_rate=0.003,
        )
        signal = strategy.generate(feature)
        assert signal is None


# ── CrowdingReversalStrategy ────────────────────────────────────


class TestCrowdingReversal:
    def test_sell_on_long_crowding(self) -> None:
        strategy = CrowdingReversalStrategy()
        feature = make_feature(
            query_rank=3,
            funding_rate=0.002,
            heatmap_delta=-100.0,
            price_change_15m=-0.001,
        )
        signal = strategy.generate(feature)
        assert signal is not None
        assert signal.side == Side.SELL
        assert signal.strategy_name == "crowding_reversal"

    def test_buy_on_short_crowding(self) -> None:
        strategy = CrowdingReversalStrategy()
        feature = make_feature(
            query_rank=2,
            funding_rate=-0.002,
            heatmap_delta=100.0,
            price_change_15m=0.001,
        )
        signal = strategy.generate(feature)
        assert signal is not None
        assert signal.side == Side.BUY

    def test_rejected_not_hot(self) -> None:
        strategy = CrowdingReversalStrategy()
        feature = make_feature(
            query_rank=None,
            funding_rate=0.002,
            heatmap_delta=-100.0,
            price_change_15m=-0.001,
        )
        signal = strategy.generate(feature)
        assert signal is None

    def test_rejected_funding_not_extreme(self) -> None:
        strategy = CrowdingReversalStrategy()
        feature = make_feature(
            query_rank=3,
            funding_rate=0.0005,
            heatmap_delta=-100.0,
            price_change_15m=-0.001,
        )
        signal = strategy.generate(feature)
        assert signal is None
