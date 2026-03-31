from datetime import datetime, timezone

from cats_py.domain.enums import MarketRegime
from cats_py.domain.models import FeatureVector
from cats_py.regime.engine import RegimeEngine


def make_feature(**overrides) -> FeatureVector:
    defaults = dict(
        symbol="BTCUSDT",
        ts=datetime.now(timezone.utc),
        reference_price=50000.0,
        stale_seconds=0.0,
        crowding_score=0.0,
        trend_score=0.0,
        oi_score=0.0,
        heatmap_delta=0.0,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


def test_defense_when_stale() -> None:
    engine = RegimeEngine()
    feature = make_feature(stale_seconds=60.0)

    assert engine.detect(feature) == MarketRegime.DEFENSE


def test_crowding_when_score_high() -> None:
    engine = RegimeEngine()
    feature = make_feature(crowding_score=0.04)

    assert engine.detect(feature) == MarketRegime.CROWDING


def test_trend_when_trend_and_oi_strong() -> None:
    engine = RegimeEngine()
    feature = make_feature(trend_score=0.08, oi_score=0.01)

    assert engine.detect(feature) == MarketRegime.TREND


def test_range_when_heatmap_present_and_trend_weak() -> None:
    engine = RegimeEngine()
    feature = make_feature(heatmap_delta=100.0, trend_score=0.01)

    assert engine.detect(feature) == MarketRegime.RANGE


def test_unknown_when_nothing_matches() -> None:
    engine = RegimeEngine()
    feature = make_feature(stale_seconds=5.0, crowding_score=0.01, trend_score=0.01, heatmap_delta=0.0)

    assert engine.detect(feature) == MarketRegime.UNKNOWN


def test_defense_takes_priority_over_crowding() -> None:
    engine = RegimeEngine()
    feature = make_feature(stale_seconds=60.0, crowding_score=0.05)

    assert engine.detect(feature) == MarketRegime.DEFENSE


def test_crowding_takes_priority_over_trend() -> None:
    engine = RegimeEngine()
    feature = make_feature(crowding_score=0.04, trend_score=0.08, oi_score=0.01)

    assert engine.detect(feature) == MarketRegime.CROWDING
