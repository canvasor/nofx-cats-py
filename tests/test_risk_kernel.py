from cats_py.domain.enums import MarketRegime, Side, SymbolTier, RiskDecisionStatus
from cats_py.domain.models import AccountSnapshot, SignalCandidate
from cats_py.risk.constitution import RiskPolicy, SymbolTierPolicy
from cats_py.risk.kernel import RiskKernel


def make_kernel() -> RiskKernel:
    return RiskKernel(
        policy=RiskPolicy(cluster_caps={"majors": 0.60}),
        tier_policies={
            SymbolTier.CORE: SymbolTierPolicy(max_leverage=3, max_symbol_notional_pct=25),
            SymbolTier.LIQUID_ALT: SymbolTierPolicy(max_leverage=2, max_symbol_notional_pct=12),
            SymbolTier.EXPERIMENTAL: SymbolTierPolicy(max_leverage=1, max_symbol_notional_pct=0, enabled=False),
        },
        symbol_tiers={"BTCUSDT": SymbolTier.CORE},
        symbol_clusters={"BTCUSDT": "majors", "ETHUSDT": "majors"},
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


def test_risk_kernel_halts_on_account_state_mismatch() -> None:
    kernel = make_kernel()
    signal = make_signal()
    account = AccountSnapshot(
        equity=10_000,
        daily_drawdown_pct=-0.1,
        weekly_drawdown_pct=-0.5,
        gross_exposure=0.1,
        open_positions=1,
        user_stream_stale_seconds=0,
        state_mismatch=True,
    )

    result = kernel.evaluate(signal, account)
    assert result.status == RiskDecisionStatus.HALTED
    assert result.reason == "account state mismatch"


def test_risk_kernel_halts_on_state_kill_switch() -> None:
    kernel = make_kernel()
    signal = make_signal()
    account = AccountSnapshot(
        equity=10_000,
        daily_drawdown_pct=-0.1,
        weekly_drawdown_pct=-0.5,
        gross_exposure=0.1,
        open_positions=1,
        user_stream_stale_seconds=0,
        kill_switch_active=True,
    )

    result = kernel.evaluate(signal, account)
    assert result.status == RiskDecisionStatus.HALTED
    assert result.reason == "state kill switch active"


def test_risk_kernel_rejects_symbol_concentration_cap() -> None:
    kernel = make_kernel()
    signal = make_signal()
    account = AccountSnapshot(
        equity=10_000,
        daily_drawdown_pct=-0.1,
        weekly_drawdown_pct=-0.5,
        gross_exposure=0.5,
        open_positions=1,
        user_stream_stale_seconds=0,
        symbol_gross_exposures={"BTCUSDT": 0.36},
    )

    result = kernel.evaluate(signal, account)
    assert result.status == RiskDecisionStatus.REJECTED
    assert result.reason == "symbol concentration cap reached"


def test_risk_kernel_rejects_cluster_cap() -> None:
    kernel = make_kernel()
    signal = make_signal()
    account = AccountSnapshot(
        equity=10_000,
        daily_drawdown_pct=-0.1,
        weekly_drawdown_pct=-0.5,
        gross_exposure=0.55,
        open_positions=2,
        user_stream_stale_seconds=0,
        symbol_gross_exposures={"BTCUSDT": 0.20, "ETHUSDT": 0.45},
    )

    result = kernel.evaluate(signal, account)
    assert result.status == RiskDecisionStatus.REJECTED
    assert result.reason == "cluster cap reached"


def test_risk_kernel_limits_size_by_leverage_bracket_cap() -> None:
    kernel = make_kernel()
    signal = make_signal()
    signal.leverage_bracket_cap = 400.0
    account = AccountSnapshot(
        equity=10_000,
        daily_drawdown_pct=-0.1,
        weekly_drawdown_pct=-0.5,
        gross_exposure=0.1,
        open_positions=1,
        user_stream_stale_seconds=0,
        symbol_gross_exposures={"ETHUSDT": 0.05},
    )

    result = kernel.evaluate(signal, account)
    assert result.status == RiskDecisionStatus.APPROVED
    assert result.approved_notional == 320.0
