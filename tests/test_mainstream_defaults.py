"""测试 NOFX normalizers 的 AI 默认分数逻辑"""
import pytest
from cats_py.connectors.nofx.normalizers import (
    normalize_coin_snapshot,
    MAINSTREAM_AI_DEFAULTS,
)


def test_mainstream_defaults_applied_when_ai500_is_zero():
    """当 AI500 分数为 0 时，应该使用默认值"""
    mock_coin = {"data": {"ai500": {"score": 0.0}}}

    feature = normalize_coin_snapshot("BTCUSDT", mock_coin)

    assert feature.ai500_score == 75.0
    assert feature.symbol == "BTCUSDT"


def test_mainstream_defaults_not_applied_when_ai500_exists():
    """当 AI500 有分数时，不应该使用默认值"""
    mock_coin = {"data": {"ai500": {"score": 85.0}}}

    feature = normalize_coin_snapshot("BTCUSDT", mock_coin)

    assert feature.ai500_score == 85.0


def test_non_mainstream_symbols_get_zero_score():
    """非主流币种应该保持 0 分"""
    mock_coin = {"data": {"ai500": {"score": 0.0}}}

    feature = normalize_coin_snapshot("PEPEUSDT", mock_coin)

    assert feature.ai500_score == 0.0


def test_all_mainstream_symbols_have_defaults():
    """所有主流币种都应该有默认值"""
    expected_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'LINKUSDT']

    for symbol in expected_symbols:
        assert symbol in MAINSTREAM_AI_DEFAULTS
        assert MAINSTREAM_AI_DEFAULTS[symbol] >= 55.0


def test_ai_gate_calculation_with_defaults():
    """测试 AI Gate 计算逻辑"""
    mock_coin = {"data": {"ai500": {"score": 0.0}}}

    feature = normalize_coin_snapshot("BTCUSDT", mock_coin)
    ai_gate = max(feature.ai500_score / 100.0, feature.ai300_level_score)

    assert ai_gate >= 0.70  # 趋势策略阈值


def test_xrp_doge_link_have_defaults():
    """XRP/DOGE/LINK 应该有默认 AI 分数"""
    mock_coin = {"data": {"ai500": {"score": 0.0}}}

    for symbol in ("XRPUSDT", "DOGEUSDT", "LINKUSDT"):
        feature = normalize_coin_snapshot(symbol, mock_coin)
        assert feature.ai500_score > 0, f"{symbol} should have default AI score"


def test_doge_ai_gate_passes_range_reversion_threshold():
    """DOGE 的 ai_gate 应该 >= 0.55 (range_reversion 阈值)"""
    mock_coin = {"data": {"ai500": {"score": 0.0}}}

    feature = normalize_coin_snapshot("DOGEUSDT", mock_coin)
    ai_gate = max(feature.ai500_score / 100.0, feature.ai300_level_score)

    assert ai_gate >= 0.55
