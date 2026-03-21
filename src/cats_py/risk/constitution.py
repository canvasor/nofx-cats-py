from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SymbolTierPolicy:
    max_leverage: float
    max_symbol_notional_pct: float
    enabled: bool = True


@dataclass(slots=True)
class RiskPolicy:
    trade_risk_bps_default: float = 35
    trade_risk_bps_max: float = 75
    daily_drawdown_soft_pct: float = -1.5
    daily_drawdown_hard_pct: float = -3.0
    weekly_drawdown_hard_pct: float = -6.0
    gross_exposure_soft: float = 1.25
    gross_exposure_hard: float = 3.0
    max_open_positions: int = 4
    min_liq_buffer_pct: float = 18.0
    max_slippage_bps_over_model: float = 12.0
    symbol_concentration_cap: float = 0.35
    leverage_bracket_buffer: float = 0.8
    cluster_caps: dict[str, float] = field(
        default_factory=lambda: {
            "core": 0.80,
            "liquid_alt": 0.45,
            "experimental": 0.15,
        }
    )
