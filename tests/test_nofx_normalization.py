from cats_py.connectors.nofx.normalizers import normalize_coin_snapshot


def test_nofx_percent_literals_become_ratio() -> None:
    feature = normalize_coin_snapshot(
        symbol="BTCUSDT",
        coin_payload={
            "data": {
                "price": 42000,
                "price_change": {"15m": 0.01, "1h": 0.02, "4h": 0.03},
                "netflow": {
                    "institution": {"future": {"15m": 1.0, "1h": 2.0, "4h": 3.0}},
                    "personal": {"future": {"1h": -1.0}},
                },
                "oi": {
                    "binance": {"delta": {"1h": {"oi_delta_percent": 5.0}}},
                    "bybit": {"delta": {"1h": {"oi_delta_percent": 2.0}}},
                },
                "ai500": {"score": 77.0},
            }
        },
        funding_payload={"data": {"funding_rate": 0.5, "timestamp": 1_770_000_000_000}},
        heatmap_payload={"data": {"heatmap": {"delta": 12345}}},
    )
    assert feature.reference_price == 42000
    assert feature.oi_binance_1h == 0.05
    assert feature.oi_bybit_1h == 0.02
    assert feature.funding_rate == 0.005
