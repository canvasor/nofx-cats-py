from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .enums import (
    DecisionStatus,
    MarketRegime,
    OrderType,
    RiskDecisionStatus,
    Side,
    SymbolTier,
    TimeInForce,
)


@dataclass(slots=True)
class FeatureVector:
    symbol: str
    ts: datetime
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


@dataclass(slots=True)
class AccountSnapshot:
    equity: float
    daily_drawdown_pct: float
    weekly_drawdown_pct: float
    gross_exposure: float
    open_positions: int
    user_stream_stale_seconds: float = 0.0


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
            created_at=datetime.now(timezone.utc),
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
            created_at=datetime.now(timezone.utc),
            status=DecisionStatus.NO_TRADE,
            symbol=symbol,
            regime=regime,
            side=None,
            rationale=rationale,
            risk=risk,
            action_score=action_score,
            selected_strategy=selected_strategy,
        )
