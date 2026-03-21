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
        symbol_clusters: dict[str, str] | None = None,
    ) -> None:
        self.policy = policy
        self.tier_policies = tier_policies
        self.symbol_tiers = symbol_tiers
        self.symbol_clusters = symbol_clusters or {}

    def evaluate(self, signal: SignalCandidate, account: AccountSnapshot) -> RiskDecision:
        if account.kill_switch_active:
            return RiskDecision(status=RiskDecisionStatus.HALTED, reason="state kill switch active")

        if account.state_mismatch:
            return RiskDecision(status=RiskDecisionStatus.HALTED, reason="account state mismatch")

        if account.reconcile_failures > 0:
            return RiskDecision(status=RiskDecisionStatus.HALTED, reason="account reconciliation failed")

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

        current_symbol_exposure = account.symbol_gross_exposures.get(signal.symbol, 0.0)
        if current_symbol_exposure >= self.policy.symbol_concentration_cap:
            return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="symbol concentration cap reached")

        cluster_name = signal.cluster or self.symbol_clusters.get(signal.symbol, tier.value)
        cluster_cap = self.policy.cluster_caps.get(cluster_name)
        current_cluster_exposure = self._cluster_exposure(account, cluster_name)
        if cluster_cap is not None and current_cluster_exposure >= cluster_cap:
            return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="cluster cap reached")

        trade_risk_budget = min(
            self.policy.trade_risk_bps_default * signal.conviction,
            self.policy.trade_risk_bps_max,
        )

        if account.daily_drawdown_pct <= self.policy.daily_drawdown_soft_pct:
            trade_risk_budget *= 0.5

        remaining_gross = max(self.policy.gross_exposure_soft - account.gross_exposure, 0.0)
        if remaining_gross <= 0:
            return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="gross exposure soft headroom exhausted")

        remaining_symbol = max(self.policy.symbol_concentration_cap - current_symbol_exposure, 0.0)
        if remaining_symbol <= 0:
            return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="symbol concentration cap reached")

        remaining_cluster = None
        if cluster_cap is not None:
            remaining_cluster = max(cluster_cap - current_cluster_exposure, 0.0)
            if remaining_cluster <= 0:
                return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="cluster cap reached")

        leverage_bracket_notional_cap = None
        if signal.leverage_bracket_cap is not None:
            leverage_bracket_notional_cap = signal.leverage_bracket_cap * self.policy.leverage_bracket_buffer
            if leverage_bracket_notional_cap <= 0:
                return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="leverage bracket cap unavailable")

        notional_caps = [
            account.equity * remaining_gross,
            account.equity * (trade_risk_budget / 10000.0) / max(signal.stop_distance_pct, 1e-6),
            account.equity * (tier_policy.max_symbol_notional_pct / 100.0),
            account.equity * remaining_symbol,
        ]
        if remaining_cluster is not None:
            notional_caps.append(account.equity * remaining_cluster)
        if leverage_bracket_notional_cap is not None:
            notional_caps.append(leverage_bracket_notional_cap)

        approved_notional = min(notional_caps)
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

    def _cluster_exposure(self, account: AccountSnapshot, cluster_name: str) -> float:
        total = 0.0
        for symbol, exposure in account.symbol_gross_exposures.items():
            symbol_cluster = self.symbol_clusters.get(symbol, self.symbol_tiers.get(symbol, SymbolTier.EXPERIMENTAL).value)
            if symbol_cluster == cluster_name:
                total += exposure
        return total
