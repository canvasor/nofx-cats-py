from __future__ import annotations

from cats_py.domain.enums import RiskDecisionStatus, SymbolTier
from cats_py.domain.models import AccountSnapshot, RiskDecision, SignalCandidate
from cats_py.risk.constitution import RiskPolicy, SymbolTierPolicy


class RiskKernel:
    def __init__(
        self,
        policy: RiskPolicy,
        tier_policies: dict[SymbolTier, SymbolTierPolicy],
        symbol_tiers: dict[str, SymbolTier],
    ) -> None:
        self.policy = policy
        self.tier_policies = tier_policies
        self.symbol_tiers = symbol_tiers

    def evaluate(self, signal: SignalCandidate, account: AccountSnapshot) -> RiskDecision:
        if account.user_stream_stale_seconds > 90:
            return RiskDecision(status=RiskDecisionStatus.HALTED, reason="user stream stale")

        if account.daily_drawdown_pct <= self.policy.daily_drawdown_hard_pct:
            return RiskDecision(status=RiskDecisionStatus.HALTED, reason="daily hard drawdown reached")

        if account.weekly_drawdown_pct <= self.policy.weekly_drawdown_hard_pct:
            return RiskDecision(status=RiskDecisionStatus.HALTED, reason="weekly hard drawdown reached")

        if account.gross_exposure >= self.policy.gross_exposure_hard:
            return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="gross exposure hard cap")

        if account.open_positions >= self.policy.max_open_positions:
            return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="max open positions reached")

        tier = self.symbol_tiers.get(signal.symbol, SymbolTier.EXPERIMENTAL)
        tier_policy = self.tier_policies[tier]
        if not tier_policy.enabled:
            return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="symbol tier disabled")

        trade_risk_budget = min(
            self.policy.trade_risk_bps_default * signal.conviction,
            self.policy.trade_risk_bps_max,
        )

        if account.daily_drawdown_pct <= self.policy.daily_drawdown_soft_pct:
            trade_risk_budget *= 0.5

        remaining_gross = max(self.policy.gross_exposure_soft - account.gross_exposure, 0.0)
        if remaining_gross <= 0:
            return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="gross exposure soft headroom exhausted")

        approved_notional = min(
            account.equity * remaining_gross,
            account.equity * (trade_risk_budget / 10000.0) / max(signal.stop_distance_pct, 1e-6),
            account.equity * (tier_policy.max_symbol_notional_pct / 100.0),
        )
        if approved_notional <= 0:
            return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="approved notional <= 0")

        approved_leverage = min(max(approved_notional / max(account.equity, 1e-6), 1.0), tier_policy.max_leverage)

        return RiskDecision(
            status=RiskDecisionStatus.APPROVED,
            reason="approved",
            symbol_tier=tier,
            approved_notional=approved_notional,
            approved_leverage=approved_leverage,
            risk_budget_bps=trade_risk_budget,
        )
