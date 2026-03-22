from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Final

from cats_py.config.settings import AppConfig, RuntimeMode, RuntimeSettings, RiskConfig, SymbolConfig, load_all_settings
from cats_py.connectors.binance.rest import BinanceRestClient
from cats_py.connectors.nofx.client import NofxClient
from cats_py.domain.enums import SymbolTier
from cats_py.features.engine import FeatureEngine
from cats_py.risk.constitution import RiskPolicy, SymbolTierPolicy
from cats_py.risk.kernel import RiskKernel
from cats_py.regime.engine import RegimeEngine
from cats_py.services.decision_engine import DecisionEngine
from cats_py.services.meta_allocator import MetaAllocator
from cats_py.strategies.crowding_reversal import CrowdingReversalStrategy
from cats_py.strategies.trend_following import TrendFollowingStrategy

LIVE_MICRO_MAX_OPEN_POSITIONS: Final[int] = 1
LIVE_MICRO_MAX_SYMBOL_NOTIONAL_PCT: Final[float] = 5.0
LIVE_MICRO_GROSS_EXPOSURE_SOFT: Final[float] = 0.20
LIVE_MICRO_GROSS_EXPOSURE_HARD: Final[float] = 0.35
LIVE_MICRO_MAX_LEVERAGE: Final[float] = 2.0


@dataclass(slots=True, frozen=True)
class RuntimeModeSummary:
    env: str
    mode: RuntimeMode
    decision_loop_enabled: bool
    live_order_submission: bool
    paper_execution: bool
    allowed_symbol_tiers: tuple[str, ...]
    configured_symbol_counts: dict[str, int]
    core_loop_interval_seconds: int
    max_runtime_open_positions: int | None = None
    max_runtime_symbol_notional_pct: float | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "env": self.env,
            "mode": self.mode.value,
            "decision_loop_enabled": self.decision_loop_enabled,
            "live_order_submission": self.live_order_submission,
            "paper_execution": self.paper_execution,
            "allowed_symbol_tiers": list(self.allowed_symbol_tiers),
            "configured_symbol_counts": self.configured_symbol_counts,
            "core_loop_interval_seconds": self.core_loop_interval_seconds,
            "max_runtime_open_positions": self.max_runtime_open_positions,
            "max_runtime_symbol_notional_pct": self.max_runtime_symbol_notional_pct,
        }


@dataclass(slots=True)
class ServiceContainer:
    runtime: RuntimeSettings
    app_config: AppConfig
    risk_config: RiskConfig
    symbol_config: SymbolConfig
    mode_summary: RuntimeModeSummary
    nofx: NofxClient
    binance: BinanceRestClient
    decision_engine: DecisionEngine


def build_symbol_tier_policy(
    payload: dict[str, object] | None,
    *,
    enabled: bool = True,
    max_leverage: float = 1.0,
    max_symbol_notional_pct: float = 0.0,
) -> SymbolTierPolicy:
    values = {
        "enabled": enabled,
        "max_leverage": max_leverage,
        "max_symbol_notional_pct": max_symbol_notional_pct,
    }
    values.update(payload or {})
    return SymbolTierPolicy(**values)


def apply_runtime_risk_overrides(
    policy: RiskPolicy,
    tier_policies: dict[SymbolTier, SymbolTierPolicy],
    mode: RuntimeMode,
) -> tuple[RiskPolicy, dict[SymbolTier, SymbolTierPolicy]]:
    runtime_policy = RiskPolicy(**{field.name: getattr(policy, field.name) for field in fields(RiskPolicy)})
    runtime_tiers = {
        tier: SymbolTierPolicy(
            max_leverage=tier_policy.max_leverage,
            max_symbol_notional_pct=tier_policy.max_symbol_notional_pct,
            enabled=tier_policy.enabled,
        )
        for tier, tier_policy in tier_policies.items()
    }

    if mode != RuntimeMode.LIVE_MICRO:
        return runtime_policy, runtime_tiers

    runtime_policy.max_open_positions = min(runtime_policy.max_open_positions, LIVE_MICRO_MAX_OPEN_POSITIONS)
    runtime_policy.gross_exposure_soft = min(runtime_policy.gross_exposure_soft, LIVE_MICRO_GROSS_EXPOSURE_SOFT)
    runtime_policy.gross_exposure_hard = min(runtime_policy.gross_exposure_hard, LIVE_MICRO_GROSS_EXPOSURE_HARD)

    runtime_tiers[SymbolTier.CORE].max_symbol_notional_pct = min(
        runtime_tiers[SymbolTier.CORE].max_symbol_notional_pct,
        LIVE_MICRO_MAX_SYMBOL_NOTIONAL_PCT,
    )
    runtime_tiers[SymbolTier.CORE].max_leverage = min(
        runtime_tiers[SymbolTier.CORE].max_leverage,
        LIVE_MICRO_MAX_LEVERAGE,
    )
    runtime_tiers[SymbolTier.LIQUID_ALT].enabled = False
    runtime_tiers[SymbolTier.EXPERIMENTAL].enabled = False
    return runtime_policy, runtime_tiers


def build_runtime_mode_summary(
    runtime: RuntimeSettings,
    app_config: AppConfig,
    symbol_config: SymbolConfig,
) -> RuntimeModeSummary:
    if runtime.mode != app_config.mode:
        raise ValueError(
            "runtime mode mismatch: CATS_MODE must match configs/app.yaml mode "
            f"({runtime.mode.value} != {app_config.mode.value})"
        )

    if runtime.mode == RuntimeMode.LIVE:
        raise ValueError("live mode is disabled in this scaffold; use live_micro after completing safeguards")

    configured_symbol_counts = {
        SymbolTier.CORE.value: len(symbol_config.core),
        SymbolTier.LIQUID_ALT.value: len(symbol_config.liquid_alt),
        SymbolTier.EXPERIMENTAL.value: len(symbol_config.experimental),
    }

    if runtime.mode == RuntimeMode.LIVE_MICRO:
        missing_credentials = [
            name
            for name, value in {
                "NOFX_API_KEY": runtime.nofx_api_key,
                "BINANCE_API_KEY": runtime.binance_api_key,
                "BINANCE_API_SECRET": runtime.binance_api_secret,
            }.items()
            if not value or value == "replace_me"
        ]
        if missing_credentials:
            missing = ", ".join(missing_credentials)
            raise ValueError(f"live_micro requires configured credentials: {missing}")
        if not symbol_config.core:
            raise ValueError("live_micro requires at least one core symbol in configs/symbols.yaml")

    if runtime.mode == RuntimeMode.SHADOW:
        live_order_submission = False
        paper_execution = False
        allowed_symbol_tiers = (
            SymbolTier.CORE.value,
            SymbolTier.LIQUID_ALT.value,
            SymbolTier.EXPERIMENTAL.value,
        )
    elif runtime.mode == RuntimeMode.PAPER:
        live_order_submission = False
        paper_execution = True
        allowed_symbol_tiers = (
            SymbolTier.CORE.value,
            SymbolTier.LIQUID_ALT.value,
            SymbolTier.EXPERIMENTAL.value,
        )
    else:
        live_order_submission = True
        paper_execution = False
        allowed_symbol_tiers = (SymbolTier.CORE.value,)

    max_runtime_open_positions = None
    max_runtime_symbol_notional_pct = None
    if runtime.mode == RuntimeMode.LIVE_MICRO:
        max_runtime_open_positions = LIVE_MICRO_MAX_OPEN_POSITIONS
        max_runtime_symbol_notional_pct = LIVE_MICRO_MAX_SYMBOL_NOTIONAL_PCT

    return RuntimeModeSummary(
        env=runtime.env,
        mode=runtime.mode,
        decision_loop_enabled=True,
        live_order_submission=live_order_submission,
        paper_execution=paper_execution,
        allowed_symbol_tiers=allowed_symbol_tiers,
        configured_symbol_counts=configured_symbol_counts,
        core_loop_interval_seconds=app_config.core_loop_interval_seconds,
        max_runtime_open_positions=max_runtime_open_positions,
        max_runtime_symbol_notional_pct=max_runtime_symbol_notional_pct,
    )


def bootstrap() -> ServiceContainer:
    runtime, app_config, risk_config, symbol_config = load_all_settings()
    mode_summary = build_runtime_mode_summary(runtime, app_config, symbol_config)

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
        SymbolTier.CORE: build_symbol_tier_policy(
            risk_config.tiers.get("core", {}),
            enabled=True,
            max_leverage=1.0,
            max_symbol_notional_pct=0.0,
        ),
        SymbolTier.LIQUID_ALT: build_symbol_tier_policy(
            risk_config.tiers.get("liquid_alt", {}),
            enabled=True,
            max_leverage=1.0,
            max_symbol_notional_pct=0.0,
        ),
        SymbolTier.EXPERIMENTAL: build_symbol_tier_policy(
            risk_config.tiers.get("experimental", {}),
            enabled=False,
            max_leverage=1.0,
            max_symbol_notional_pct=0.0,
        ),
    }
    risk, tier_policies = apply_runtime_risk_overrides(risk, tier_policies, runtime.mode)
    symbol_tiers = {symbol: SymbolTier.CORE for symbol in symbol_config.core}
    symbol_tiers.update({symbol: SymbolTier.LIQUID_ALT for symbol in symbol_config.liquid_alt})
    symbol_tiers.update({symbol: SymbolTier.EXPERIMENTAL for symbol in symbol_config.experimental})
    symbol_clusters = {symbol: SymbolTier.CORE.value for symbol in symbol_config.core}
    symbol_clusters.update({symbol: SymbolTier.LIQUID_ALT.value for symbol in symbol_config.liquid_alt})
    symbol_clusters.update({symbol: SymbolTier.EXPERIMENTAL.value for symbol in symbol_config.experimental})

    decision_engine = DecisionEngine(
        feature_engine=FeatureEngine(),
        regime_engine=RegimeEngine(),
        strategies=[TrendFollowingStrategy(), CrowdingReversalStrategy()],
        risk_kernel=RiskKernel(
            policy=risk,
            tier_policies=tier_policies,
            symbol_tiers=symbol_tiers,
            symbol_clusters=symbol_clusters,
        ),
        meta_allocator=MetaAllocator(),
    )

    return ServiceContainer(
        runtime=runtime,
        app_config=app_config,
        risk_config=risk_config,
        symbol_config=symbol_config,
        mode_summary=mode_summary,
        nofx=nofx,
        binance=binance,
        decision_engine=decision_engine,
    )
