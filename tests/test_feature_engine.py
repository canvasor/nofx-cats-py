from datetime import datetime, timedelta, timezone

from cats_py.domain.models import FeatureVector
from cats_py.features.engine import FeatureEngine


def make_feature(**overrides) -> FeatureVector:
    defaults = dict(
        symbol="BTCUSDT",
        ts=datetime.now(timezone.utc),
        reference_price=50000.0,
        price_change_15m=0.01,
        price_change_1h=0.02,
        price_change_4h=0.03,
        inst_future_flow_15m=1.0,
        inst_future_flow_1h=2.0,
        inst_future_flow_4h=3.0,
        oi_binance_1h=0.05,
        oi_bybit_1h=0.02,
        funding_rate=0.001,
        query_rank=None,
    )
    defaults.update(overrides)
    return FeatureVector(**defaults)


def test_trend_score_is_sum_of_price_changes() -> None:
    engine = FeatureEngine()
    feature = make_feature(price_change_15m=0.01, price_change_1h=0.02, price_change_4h=0.03)

    result = engine.enrich(feature)

    assert abs(result.trend_score - 0.06) < 1e-9


def test_flow_score_is_sum_of_inst_flows() -> None:
    engine = FeatureEngine()
    feature = make_feature(inst_future_flow_15m=1.0, inst_future_flow_1h=2.0, inst_future_flow_4h=3.0)

    result = engine.enrich(feature)

    assert abs(result.flow_score - 6.0) < 1e-9


def test_oi_score_is_sum_of_binance_and_bybit() -> None:
    engine = FeatureEngine()
    feature = make_feature(oi_binance_1h=0.05, oi_bybit_1h=0.02)

    result = engine.enrich(feature)

    assert abs(result.oi_score - 0.07) < 1e-9


def test_crowding_score_includes_query_heat_when_hot() -> None:
    engine = FeatureEngine()
    feature = make_feature(funding_rate=0.001, query_rank=3)

    result = engine.enrich(feature)

    assert abs(result.crowding_score - 0.011) < 1e-9


def test_crowding_score_no_query_heat_when_not_hot() -> None:
    engine = FeatureEngine()
    feature = make_feature(funding_rate=0.001, query_rank=10)

    result = engine.enrich(feature)

    assert abs(result.crowding_score - 0.001) < 1e-9


def test_crowding_score_no_query_heat_when_rank_none() -> None:
    engine = FeatureEngine()
    feature = make_feature(funding_rate=0.002, query_rank=None)

    result = engine.enrich(feature)

    assert abs(result.crowding_score - 0.002) < 1e-9


def test_source_freshness_linear_decay() -> None:
    engine = FeatureEngine()
    feature = make_feature(ts=datetime.now(timezone.utc) - timedelta(seconds=22.5))

    result = engine.enrich(feature)

    assert 0.4 < result.source_freshness < 0.6


def test_source_freshness_capped_at_zero() -> None:
    engine = FeatureEngine()
    feature = make_feature(ts=datetime.now(timezone.utc) - timedelta(seconds=100))

    result = engine.enrich(feature)

    assert result.source_freshness == 0.0
