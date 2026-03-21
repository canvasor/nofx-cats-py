from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .enums import (
    DecisionStatus,
    MarketRegime,
    OrderLifecycleStatus,
    OrderType,
    PositionDirection,
    RiskDecisionStatus,
    Side,
    SymbolTier,
    TimeInForce,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class FeatureVector:
    symbol: str
    ts: datetime
    reference_price: float = 0.0
    ai500_score: float = 0.0
    ai300_level_score: float = 0.0
    price_change_15m: float = 0.0
    price_change_1h: float = 0.0
    price_change_4h: float = 0.0
    inst_future_flow_15m: float = 0.0
    inst_future_flow_1h: float = 0.0
    inst_future_flow_4h: float = 0.0
    retail_future_flow_1h: float = 0.0
    oi_binance_1h: float = 0.0
    oi_bybit_1h: float = 0.0
    funding_rate: float = 0.0
    heatmap_delta: float = 0.0
    query_rank: int | None = None
    stale_seconds: float = 0.0
    trend_score: float = 0.0
    flow_score: float = 0.0
    oi_score: float = 0.0
    crowding_score: float = 0.0
    source_freshness: float = 1.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SignalCandidate:
    symbol: str
    regime: MarketRegime
    side: Side
    conviction: float
    expected_edge_bps: float
    stop_distance_pct: float
    rationale: list[str]
    strategy_name: str = "unknown"
    action_score: float = 0.0
    cluster: str | None = None
    leverage_bracket_cap: float | None = None


@dataclass(slots=True)
class AccountSnapshot:
    equity: float
    daily_drawdown_pct: float
    weekly_drawdown_pct: float
    gross_exposure: float
    open_positions: int
    user_stream_stale_seconds: float = 0.0
    state_mismatch: bool = False
    reconcile_failures: int = 0
    kill_switch_active: bool = False
    symbol_gross_exposures: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class OrderRequest:
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal | None = None
    price: Decimal | None = None
    trigger_price: Decimal | None = None
    time_in_force: TimeInForce | None = None
    reduce_only: bool = False
    close_position: bool = False
    position_side: str = "BOTH"
    client_order_id: str | None = None
    working_type: str | None = None
    price_protect: bool = False
    self_trade_prevention_mode: str | None = None
    new_order_resp_type: str | None = None
    activate_price: Decimal | None = None
    callback_rate: Decimal | None = None


@dataclass(slots=True)
class OrderResponse:
    venue_order_id: str | None
    route: str
    status: str
    raw: dict[str, Any]


@dataclass(slots=True)
class RiskDecision:
    status: RiskDecisionStatus
    reason: str
    symbol_tier: SymbolTier | None = None
    approved_notional: float = 0.0
    approved_leverage: float = 0.0
    risk_budget_bps: float = 0.0


@dataclass(slots=True)
class TradeDecision:
    decision_id: str
    created_at: datetime
    status: DecisionStatus
    symbol: str
    regime: MarketRegime
    side: Side | None
    rationale: list[str]
    risk: RiskDecision | None = None
    action_score: float = 0.0
    selected_strategy: str | None = None
    order_request: OrderRequest | None = None

    @staticmethod
    def execute(
        decision_id: str,
        symbol: str,
        regime: MarketRegime,
        side: Side,
        rationale: list[str],
        risk: RiskDecision,
        *,
        action_score: float,
        selected_strategy: str | None,
        order_request: OrderRequest | None = None,
    ) -> "TradeDecision":
        return TradeDecision(
            decision_id=decision_id,
            created_at=utc_now(),
            status=DecisionStatus.EXECUTE,
            symbol=symbol,
            regime=regime,
            side=side,
            rationale=rationale,
            risk=risk,
            action_score=action_score,
            selected_strategy=selected_strategy,
            order_request=order_request,
        )

    @staticmethod
    def no_trade(
        decision_id: str,
        symbol: str,
        regime: MarketRegime,
        rationale: list[str],
        *,
        risk: RiskDecision | None = None,
        action_score: float = 0.0,
        selected_strategy: str | None = None,
    ) -> "TradeDecision":
        return TradeDecision(
            decision_id=decision_id,
            created_at=utc_now(),
            status=DecisionStatus.NO_TRADE,
            symbol=symbol,
            regime=regime,
            side=None,
            rationale=rationale,
            risk=risk,
            action_score=action_score,
            selected_strategy=selected_strategy,
        )


@dataclass(slots=True)
class OrderState:
    symbol: str
    status: OrderLifecycleStatus
    side: Side
    position_side: str = "BOTH"
    order_id: str | None = None
    client_order_id: str | None = None
    algo_order_id: str | None = None
    order_type: OrderType | None = None
    price: Decimal | None = None
    avg_price: Decimal | None = None
    orig_qty: Decimal | None = None
    executed_qty: Decimal = Decimal("0")
    reduce_only: bool = False
    close_position: bool = False
    is_algo: bool = False
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def identity(self) -> str:
        if self.algo_order_id:
            return f"algo:{self.algo_order_id}"
        if self.order_id:
            return f"order:{self.order_id}"
        if self.client_order_id:
            return f"client:{self.client_order_id}"
        raise ValueError("order state requires at least one identifier")

    @property
    def is_open(self) -> bool:
        return self.status in {
            OrderLifecycleStatus.NEW,
            OrderLifecycleStatus.PARTIALLY_FILLED,
            OrderLifecycleStatus.TRIGGERED,
        }


@dataclass(slots=True)
class BalanceState:
    asset: str
    wallet_balance: Decimal = Decimal("0")
    available_balance: Decimal = Decimal("0")
    cross_wallet_balance: Decimal = Decimal("0")
    updated_at: datetime = field(default_factory=utc_now)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PositionState:
    symbol: str
    position_side: str = "BOTH"
    direction: PositionDirection = PositionDirection.FLAT
    quantity: Decimal = Decimal("0")
    entry_price: Decimal = Decimal("0")
    mark_price: Decimal = Decimal("0")
    notional: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    leverage: int = 1
    margin_type: str = "cross"
    isolated_wallet: Decimal = Decimal("0")
    updated_at: datetime = field(default_factory=utc_now)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> tuple[str, str]:
        return (self.symbol, self.position_side)

    @property
    def is_open(self) -> bool:
        return self.quantity != 0

    @property
    def gross_notional(self) -> Decimal:
        if self.notional != 0:
            return abs(self.notional)
        reference_price = self.mark_price or self.entry_price
        return abs(self.quantity * reference_price)


@dataclass(slots=True)
class AccountState:
    balances: dict[str, BalanceState] = field(default_factory=dict)
    positions: dict[tuple[str, str], PositionState] = field(default_factory=dict)
    orders: dict[str, OrderState] = field(default_factory=dict)
    last_user_stream_event_at: datetime | None = None
    last_reconciled_at: datetime | None = None
    state_mismatch_count: int = 0
    reconcile_failure_count: int = 0
    last_mismatch_reason: str | None = None
    last_reconcile_error: str | None = None
    kill_switch_active: bool = False
    last_kill_switch_reason: str | None = None

    def record_user_stream_event(self, event_time: datetime | None = None) -> None:
        self.last_user_stream_event_at = event_time or utc_now()

    def mark_reconciled(self, reconciled_at: datetime | None = None) -> None:
        self.last_reconciled_at = reconciled_at or utc_now()

    def record_state_mismatch(self, reason: str, *, threshold: int = 2) -> None:
        self.state_mismatch_count += 1
        self.last_mismatch_reason = reason
        if self.state_mismatch_count >= threshold:
            self.activate_kill_switch(reason)

    def clear_state_mismatch(self) -> None:
        self.state_mismatch_count = 0
        self.last_mismatch_reason = None

    def record_reconcile_failure(self, reason: str, *, threshold: int = 2) -> None:
        self.reconcile_failure_count += 1
        self.last_reconcile_error = reason
        if self.reconcile_failure_count >= threshold:
            self.activate_kill_switch(reason)

    def clear_reconcile_failure(self) -> None:
        self.reconcile_failure_count = 0
        self.last_reconcile_error = None

    def activate_kill_switch(self, reason: str) -> None:
        self.kill_switch_active = True
        self.last_kill_switch_reason = reason

    def upsert_balance(self, balance: BalanceState) -> None:
        self.balances[balance.asset] = balance

    def upsert_position(self, position: PositionState) -> None:
        self.positions[position.key] = position

    def upsert_order(self, order: OrderState) -> None:
        self.orders[order.identity] = order

    def replace_balances(self, balances: list[BalanceState]) -> None:
        self.balances = {balance.asset: balance for balance in balances}

    def replace_positions(self, positions: list[PositionState]) -> None:
        self.positions = {position.key: position for position in positions}

    def replace_orders(self, orders: list[OrderState]) -> None:
        self.orders = {order.identity: order for order in orders}

    def total_wallet_balance(self) -> Decimal:
        return sum((balance.wallet_balance for balance in self.balances.values()), start=Decimal("0"))

    def total_unrealized_pnl(self) -> Decimal:
        return sum(
            (position.unrealized_pnl for position in self.positions.values() if position.is_open),
            start=Decimal("0"),
        )

    def total_equity(self) -> Decimal:
        return self.total_wallet_balance() + self.total_unrealized_pnl()

    def gross_notional(self) -> Decimal:
        return sum(
            (position.gross_notional for position in self.positions.values() if position.is_open),
            start=Decimal("0"),
        )

    def open_position_count(self) -> int:
        return sum(1 for position in self.positions.values() if position.is_open)

    def symbol_gross_exposures(self) -> dict[str, float]:
        equity = self.total_equity()
        if equity <= 0:
            return {}

        symbol_notionals: dict[str, Decimal] = {}
        for position in self.positions.values():
            if not position.is_open:
                continue
            symbol_notionals[position.symbol] = symbol_notionals.get(position.symbol, Decimal("0")) + position.gross_notional

        return {
            symbol: float(notional / equity)
            for symbol, notional in symbol_notionals.items()
        }

    def user_stream_stale_seconds(self, now: datetime | None = None) -> float:
        if self.last_user_stream_event_at is None:
            return 0.0
        reference_time = now or utc_now()
        return max((reference_time - self.last_user_stream_event_at).total_seconds(), 0.0)

    def to_snapshot(
        self,
        *,
        daily_drawdown_pct: float = 0.0,
        weekly_drawdown_pct: float = 0.0,
        now: datetime | None = None,
    ) -> AccountSnapshot:
        equity = self.total_equity()
        gross_notional = self.gross_notional()
        gross_exposure = 0.0
        if equity > 0:
            gross_exposure = float(gross_notional / equity)

        return AccountSnapshot(
            equity=float(equity),
            daily_drawdown_pct=daily_drawdown_pct,
            weekly_drawdown_pct=weekly_drawdown_pct,
            gross_exposure=gross_exposure,
            open_positions=self.open_position_count(),
            user_stream_stale_seconds=self.user_stream_stale_seconds(now=now),
            state_mismatch=self.state_mismatch_count > 0,
            reconcile_failures=self.reconcile_failure_count,
            kill_switch_active=self.kill_switch_active,
            symbol_gross_exposures=self.symbol_gross_exposures(),
        )
