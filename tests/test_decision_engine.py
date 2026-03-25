from datetime import datetime, timezone

from cats_py.domain.enums import MarketRegime, RiskDecisionStatus, Side, SymbolTier
from cats_py.domain.models import AccountSnapshot, FeatureVector, RiskDecision, SignalCandidate
from cats_py.features.engine import FeatureEngine
from cats_py.regime.engine import RegimeEngine
from cats_py.risk.constitution import RiskPolicy, SymbolTierPolicy
from cats_py.risk.kernel import RiskKernel
from cats_py.services.decision_engine import DecisionEngine
from cats_py.services.meta_allocator import MetaAllocator
from cats_py.strategies.base import Strategy
from cats_py.strategies.range_reversion import RangeReversionStrategy


class FirstRejectedStrategy(Strategy):
    name = "first"

    def generate(self, feature: FeatureVector) -> SignalCandidate | None:
        return SignalCandidate(
            symbol=feature.symbol,
            regime=MarketRegime.TREND,
            side=Side.BUY,
            conviction=0.9,
            expected_edge_bps=20,
            stop_distance_pct=0.01,
            rationale=["first"],
            strategy_name=self.name,
        )


class SecondApprovedStrategy(Strategy):
    name = "second"

    def generate(self, feature: FeatureVector) -> SignalCandidate | None:
        return SignalCandidate(
            symbol=feature.symbol,
            regime=MarketRegime.TREND,
            side=Side.SELL,
            conviction=0.7,
            expected_edge_bps=18,
            stop_distance_pct=0.01,
            rationale=["second"],
            strategy_name=self.name,
        )


class SelectiveRiskKernel(RiskKernel):
    def evaluate(self, signal: SignalCandidate, account: AccountSnapshot) -> RiskDecision:
        if signal.strategy_name == "first":
            return RiskDecision(status=RiskDecisionStatus.REJECTED, reason="first rejected")
        return RiskDecision(
            status=RiskDecisionStatus.APPROVED,
            reason="approved",
            symbol_tier=SymbolTier.CORE,
            approved_notional=1000,
            approved_leverage=1,
            risk_budget_bps=20,
        )


def test_decision_engine_continues_after_first_risk_rejection() -> None:
    engine = DecisionEngine(
        feature_engine=FeatureEngine(),
        regime_engine=RegimeEngine(),
        strategies=[FirstRejectedStrategy(), SecondApprovedStrategy()],
        risk_kernel=SelectiveRiskKernel(
            policy=RiskPolicy(),
            tier_policies={
                SymbolTier.CORE: SymbolTierPolicy(max_leverage=3, max_symbol_notional_pct=25),
                SymbolTier.LIQUID_ALT: SymbolTierPolicy(max_leverage=2, max_symbol_notional_pct=12),
                SymbolTier.EXPERIMENTAL: SymbolTierPolicy(max_leverage=1, max_symbol_notional_pct=0, enabled=False),
            },
            symbol_tiers={"BTCUSDT": SymbolTier.CORE},
        ),
        meta_allocator=MetaAllocator(),
    )

    feature = FeatureVector(
        symbol="BTCUSDT",
        ts=datetime.now(timezone.utc),
        ai500_score=80,
        price_change_15m=0.01,
        price_change_1h=0.02,
        price_change_4h=0.03,
        inst_future_flow_15m=10,
        inst_future_flow_1h=10,
        inst_future_flow_4h=10,
        oi_binance_1h=0.02,
        oi_bybit_1h=0.01,
        funding_rate=0.0,
        heatmap_delta=-10,
    )
    account = AccountSnapshot(
        equity=10_000,
        daily_drawdown_pct=-0.2,
        weekly_drawdown_pct=-0.3,
        gross_exposure=0.2,
        open_positions=1,
        user_stream_stale_seconds=0,
    )

    decision = engine.decide(feature, account)
    assert decision.status.value == "EXECUTE"
    assert decision.selected_strategy == "second"


class NeverSignalStrategy(Strategy):
    name = "never"

    def generate(self, feature: FeatureVector) -> SignalCandidate | None:
        return None

    def skip_reason(self, feature: FeatureVector) -> str:
        return "never: conditions not met"


def test_decision_engine_records_strategy_skip_reasons_when_no_candidate_exists() -> None:
    engine = DecisionEngine(
        feature_engine=FeatureEngine(),
        regime_engine=RegimeEngine(),
        strategies=[NeverSignalStrategy()],
        risk_kernel=SelectiveRiskKernel(
            policy=RiskPolicy(),
            tier_policies={
                SymbolTier.CORE: SymbolTierPolicy(max_leverage=3, max_symbol_notional_pct=25),
                SymbolTier.LIQUID_ALT: SymbolTierPolicy(max_leverage=2, max_symbol_notional_pct=12),
                SymbolTier.EXPERIMENTAL: SymbolTierPolicy(max_leverage=1, max_symbol_notional_pct=0, enabled=False),
            },
            symbol_tiers={"BTCUSDT": SymbolTier.CORE},
        ),
        meta_allocator=MetaAllocator(),
    )

    feature = FeatureVector(symbol="BTCUSDT", ts=datetime.now(timezone.utc))
    account = AccountSnapshot(
        equity=10_000,
        daily_drawdown_pct=-0.2,
        weekly_drawdown_pct=-0.3,
        gross_exposure=0.2,
        open_positions=1,
        user_stream_stale_seconds=0,
    )

    decision = engine.decide(feature, account)

    assert decision.status.value == "NO_TRADE"
    assert "never: conditions not met" in decision.rationale


def test_range_reversion_strategy_generates_candidate_in_range_conditions() -> None:
    strategy = RangeReversionStrategy()
    feature = FeatureVector(
        symbol="BTCUSDT",
        ts=datetime.now(timezone.utc),
        ai500_score=70,
        price_change_15m=-0.01,
        price_change_1h=0.003,
        price_change_4h=-0.002,
        inst_future_flow_15m=3,
        inst_future_flow_1h=1,
        inst_future_flow_4h=0,
        retail_future_flow_1h=0,
        oi_binance_1h=0.001,
        oi_bybit_1h=0.001,
        funding_rate=0.0005,
        heatmap_delta=250.0,
    )

    signal = strategy.generate(feature)

    assert signal is not None
    assert signal.regime == MarketRegime.RANGE
    assert signal.side == Side.BUY
    assert signal.strategy_name == "range_reversion"
