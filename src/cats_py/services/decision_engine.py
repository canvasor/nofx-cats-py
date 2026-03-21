from __future__ import annotations

import uuid

from cats_py.domain.enums import MarketRegime, RiskDecisionStatus
from cats_py.domain.models import AccountSnapshot, FeatureVector, TradeDecision
from cats_py.features.engine import FeatureEngine
from cats_py.regime.engine import RegimeEngine
from cats_py.risk.kernel import RiskKernel
from cats_py.services.meta_allocator import MetaAllocator
from cats_py.strategies.base import Strategy


class DecisionEngine:
    def __init__(
        self,
        feature_engine: FeatureEngine,
        regime_engine: RegimeEngine,
        strategies: list[Strategy],
        risk_kernel: RiskKernel,
        meta_allocator: MetaAllocator,
    ) -> None:
        self.feature_engine = feature_engine
        self.regime_engine = regime_engine
        self.strategies = strategies
        self.risk_kernel = risk_kernel
        self.meta_allocator = meta_allocator

    def decide(self, feature: FeatureVector, account: AccountSnapshot) -> TradeDecision:
        enriched = self.feature_engine.enrich(feature)
        regime = self.regime_engine.detect(enriched)
        decision_id = str(uuid.uuid4())

        if regime == MarketRegime.DEFENSE:
            return TradeDecision.no_trade(
                decision_id=decision_id,
                symbol=enriched.symbol,
                regime=regime,
                rationale=["regime switched to DEFENSE", "new entries are disabled until freshness recovers"],
            )

        candidates = []
        for strategy in self.strategies:
            signal = strategy.generate(enriched)
            if signal is None:
                continue
            signal.regime = regime
            signal.action_score = self.meta_allocator.score(signal, enriched, regime)
            candidates.append(signal)

        if not candidates:
            return TradeDecision.no_trade(
                decision_id=decision_id,
                symbol=enriched.symbol,
                regime=regime,
                rationale=["no strategy produced a valid candidate", "NO_TRADE scored higher than any action"],
            )

        rejected_reasons: list[str] = []
        for signal in sorted(candidates, key=lambda item: item.action_score, reverse=True):
            if signal.action_score <= 0:
                rejected_reasons.append(f"{signal.strategy_name}: action_score <= 0")
                continue

            risk = self.risk_kernel.evaluate(signal, account)
            if risk.status != RiskDecisionStatus.APPROVED:
                rejected_reasons.append(f"{signal.strategy_name}: risk rejected ({risk.reason})")
                continue

            return TradeDecision.execute(
                decision_id=decision_id,
                symbol=signal.symbol,
                regime=signal.regime,
                side=signal.side,
                rationale=signal.rationale,
                risk=risk,
                action_score=signal.action_score,
                selected_strategy=signal.strategy_name,
            )

        rationale = rejected_reasons or ["all candidate actions were dominated by NO_TRADE"]
        return TradeDecision.no_trade(
            decision_id=decision_id,
            symbol=enriched.symbol,
            regime=regime,
            rationale=rationale,
        )
