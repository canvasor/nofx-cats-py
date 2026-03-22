from pathlib import Path

import pytest

from cats_py.app.bootstrap import (
    LIVE_MICRO_MAX_OPEN_POSITIONS,
    LIVE_MICRO_MAX_SYMBOL_NOTIONAL_PCT,
    apply_runtime_risk_overrides,
    build_symbol_tier_policy,
    build_runtime_mode_summary,
)
from cats_py.config.settings import AppConfig, RuntimeMode, RuntimeSettings, SymbolConfig
from cats_py.domain.enums import SymbolTier
from cats_py.risk.constitution import RiskPolicy, SymbolTierPolicy


def make_runtime(mode: RuntimeMode, **overrides: object) -> RuntimeSettings:
    values: dict[str, object] = {
        "env": "test",
        "mode": mode,
        "log_level": "INFO",
        "nofx_api_key": "nofx-key",
        "binance_api_key": "binance-key",
        "binance_api_secret": "binance-secret",
        "nofx_base_url": "https://nofx.example.com",
        "binance_rest_base_url": "https://binance.example.com",
        "binance_ws_public_url": "wss://binance.example.com/public",
        "binance_ws_market_url": "wss://binance.example.com/market",
        "binance_ws_private_url": "wss://binance.example.com/private",
        "app_config_path": Path("configs/app.yaml"),
        "risk_config_path": Path("configs/risk.yaml"),
        "symbols_config_path": Path("configs/symbols.yaml"),
    }
    values.update(overrides)
    return RuntimeSettings.model_construct(**values)


def test_runtime_mode_summary_for_shadow_disables_live_orders() -> None:
    runtime = make_runtime(RuntimeMode.SHADOW)
    app_config = AppConfig(mode=RuntimeMode.SHADOW)
    symbols = SymbolConfig(core=["BTCUSDT"], liquid_alt=["ETHUSDT"], experimental=["DOGEUSDT"])

    summary = build_runtime_mode_summary(runtime, app_config, symbols)

    assert summary.mode == RuntimeMode.SHADOW
    assert summary.live_order_submission is False
    assert summary.paper_execution is False
    assert summary.allowed_symbol_tiers == ("core", "liquid_alt", "experimental")


def test_runtime_mode_summary_rejects_mode_mismatch() -> None:
    runtime = make_runtime(RuntimeMode.SHADOW)
    app_config = AppConfig(mode=RuntimeMode.PAPER)

    with pytest.raises(ValueError, match="runtime mode mismatch"):
        build_runtime_mode_summary(runtime, app_config, SymbolConfig(core=["BTCUSDT"]))


def test_runtime_mode_summary_blocks_live_mode() -> None:
    runtime = make_runtime(RuntimeMode.LIVE)
    app_config = AppConfig(mode=RuntimeMode.LIVE)

    with pytest.raises(ValueError, match="live mode is disabled"):
        build_runtime_mode_summary(runtime, app_config, SymbolConfig(core=["BTCUSDT"]))


def test_runtime_mode_summary_requires_credentials_for_live_micro() -> None:
    runtime = make_runtime(
        RuntimeMode.LIVE_MICRO,
        nofx_api_key="",
        binance_api_key="",
        binance_api_secret="",
    )
    app_config = AppConfig(mode=RuntimeMode.LIVE_MICRO)

    with pytest.raises(ValueError, match="live_micro requires configured credentials"):
        build_runtime_mode_summary(runtime, app_config, SymbolConfig(core=["BTCUSDT"]))


def test_runtime_mode_summary_limits_live_micro_to_core_and_runtime_caps() -> None:
    runtime = make_runtime(RuntimeMode.LIVE_MICRO)
    app_config = AppConfig(mode=RuntimeMode.LIVE_MICRO)

    summary = build_runtime_mode_summary(runtime, app_config, SymbolConfig(core=["BTCUSDT"], liquid_alt=["ETHUSDT"]))

    assert summary.allowed_symbol_tiers == ("core",)
    assert summary.max_runtime_open_positions == LIVE_MICRO_MAX_OPEN_POSITIONS
    assert summary.max_runtime_symbol_notional_pct == LIVE_MICRO_MAX_SYMBOL_NOTIONAL_PCT


def test_apply_runtime_risk_overrides_tightens_live_micro_caps() -> None:
    policy = RiskPolicy(gross_exposure_soft=1.0, gross_exposure_hard=2.0, max_open_positions=4)
    tiers = {
        SymbolTier.CORE: SymbolTierPolicy(max_leverage=5, max_symbol_notional_pct=20),
        SymbolTier.LIQUID_ALT: SymbolTierPolicy(max_leverage=3, max_symbol_notional_pct=10),
        SymbolTier.EXPERIMENTAL: SymbolTierPolicy(max_leverage=2, max_symbol_notional_pct=5, enabled=True),
    }

    runtime_policy, runtime_tiers = apply_runtime_risk_overrides(policy, tiers, RuntimeMode.LIVE_MICRO)

    assert runtime_policy.max_open_positions == LIVE_MICRO_MAX_OPEN_POSITIONS
    assert runtime_tiers[SymbolTier.CORE].max_symbol_notional_pct == LIVE_MICRO_MAX_SYMBOL_NOTIONAL_PCT
    assert runtime_tiers[SymbolTier.LIQUID_ALT].enabled is False
    assert runtime_tiers[SymbolTier.EXPERIMENTAL].enabled is False


def test_build_symbol_tier_policy_backfills_missing_experimental_defaults() -> None:
    policy = build_symbol_tier_policy({"enabled": False}, enabled=False, max_leverage=1.0, max_symbol_notional_pct=0.0)

    assert policy.enabled is False
    assert policy.max_leverage == 1.0
    assert policy.max_symbol_notional_pct == 0.0
