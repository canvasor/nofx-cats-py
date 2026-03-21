from __future__ import annotations

from cats_py.config.settings import load_all_settings
from cats_py.connectors.binance.rest import BinanceRestClient
from cats_py.connectors.nofx.client import NofxClient
from cats_py.features.engine import FeatureEngine
from cats_py.regime.engine import RegimeEngine
from cats_py.risk.constitution import RiskPolicy, SymbolTierPolicy
from cats_py.risk.kernel import RiskKernel
from cats_py.services.decision_engine import DecisionEngine
from cats_py.services.meta_allocator import MetaAllocator
from cats_py.strategies.crowding_reversal import CrowdingReversalStrategy
from cats_py.strategies.trend_following import TrendFollowingStrategy
from cats_py.domain.enums import SymbolTier


def bootstrap() -> dict[str, object]:
    runtime, _, risk_config, symbol_config = load_all_settings()

    nofx = NofxClient(
        api_key=runtime.nofx_api_key,
        base_url=runtime.nofx_base_url,
        auth_mode=runtime.nofx_auth_mode,
    )
    binance = BinanceRestClient(
        api_key=runtime.binance_api_key,
        api_secret=runtime.binance_api_secret,
        base_url=runtime.binance_rest_base_url,
    )

    risk = RiskPolicy(**risk_config.risk)
    tier_policies = {
        SymbolTier.CORE: SymbolTierPolicy(**risk_config.tiers.get("core", {})),
        SymbolTier.LIQUID_ALT: SymbolTierPolicy(**risk_config.tiers.get("liquid_alt", {})),
        SymbolTier.EXPERIMENTAL: SymbolTierPolicy(**risk_config.tiers.get("experimental", {"enabled": False})),
    }
    symbol_tiers = {symbol: SymbolTier.CORE for symbol in symbol_config.core}
    symbol_tiers.update({symbol: SymbolTier.LIQUID_ALT for symbol in symbol_config.liquid_alt})
    symbol_tiers.update({symbol: SymbolTier.EXPERIMENTAL for symbol in symbol_config.experimental})

    decision_engine = DecisionEngine(
        feature_engine=FeatureEngine(),
        regime_engine=RegimeEngine(),
        strategies=[TrendFollowingStrategy(), CrowdingReversalStrategy()],
        risk_kernel=RiskKernel(
            policy=risk,
            tier_policies=tier_policies,
            symbol_tiers=symbol_tiers,
        ),
        meta_allocator=MetaAllocator(),
    )

    return {
        "runtime": runtime,
        "nofx": nofx,
        "binance": binance,
        "decision_engine": decision_engine,
    }
