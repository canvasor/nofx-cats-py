from cats_py.domain.enums import MarketRegime, Side, SymbolTier, RiskDecisionStatus
from cats_py.domain.models import AccountSnapshot, SignalCandidate
from cats_py.risk.constitution import RiskPolicy, SymbolTierPolicy
from cats_py.risk.kernel import RiskKernel


def make_kernel() -> RiskKernel:
    return RiskKernel(
        policy=RiskPolicy(),
        tier_policies={
            SymbolTier.CORE: SymbolTierPolicy(max_leverage=3, max_symbol_notional_pct=25),
            SymbolTier.LIQUID_ALT: SymbolTierPolicy(max_leverage=2, max_symbol_notional_pct=12),
            SymbolTier.EXPERIMENTAL: SymbolTierPolicy(max_leverage=1, max_symbol_notional_pct=0, enabled=False),
        },
        symbol_tiers={"BTCUSDT": SymbolTier.CORE},
    )


def make_signal() -> SignalCandidate:
    return SignalCandidate(
        symbol="BTCUSDT",
        regime=MarketRegime.TREND,
        side=Side.BUY,
        conviction=0.8,
        expected_edge_bps=12,
        stop_distance_pct=0.01,
        rationale=["demo"],
        strategy_name="trend_following",
    )


def test_risk_kernel_rejects_stale_user_stream() -> None:
    kernel = make_kernel()
    signal = make_signal()
    account = AccountSnapshot(
        equity=10_000,
        daily_drawdown_pct=-0.1,
        weekly_drawdown_pct=-0.5,
        gross_exposure=0.1,
        open_positions=1,
        user_stream_stale_seconds=120,
    )
    result = kernel.evaluate(signal, account)
    assert result.status == RiskDecisionStatus.HALTED


def test_risk_kernel_uses_remaining_gross_headroom() -> None:
    kernel = make_kernel()
    signal = make_signal()
    account = AccountSnapshot(
        equity=10_000,
        daily_drawdown_pct=-0.1,
        weekly_drawdown_pct=-0.5,
        gross_exposure=1.20,
        open_positions=1,
        user_stream_stale_seconds=0,
    )
    result = kernel.evaluate(signal, account)
    assert result.status == RiskDecisionStatus.APPROVED
    assert round(result.approved_notional, 2) == 500.00
