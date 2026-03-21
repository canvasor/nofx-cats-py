from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from cats_py.domain.enums import OrderLifecycleStatus, PositionDirection, Side
from cats_py.domain.models import AccountState, OrderResponse, OrderState, PositionState
from cats_py.execution.guardian import PositionGuardian


@dataclass(slots=True, frozen=True)
class ProtectionPlan:
    symbol: str
    position_side: str
    exit_side: Side
    trigger_price: Decimal
    client_order_id: str


class ProtectionOrchestrator:
    """Attach a disaster stop after a new entry is filled, unless one already exists."""

    def __init__(self, guardian: PositionGuardian, default_stop_distance_pct: Decimal = Decimal("0.02")) -> None:
        self.guardian = guardian
        self.default_stop_distance_pct = default_stop_distance_pct

    async def ensure_disaster_stop(
        self,
        *,
        filled_order: OrderState,
        account_state: AccountState,
        stop_distance_pct: Decimal | None = None,
    ) -> OrderResponse | None:
        plan = self.build_plan(
            filled_order=filled_order,
            account_state=account_state,
            stop_distance_pct=stop_distance_pct,
        )
        if plan is None:
            return None

        return await self.guardian.place_disaster_stop(
            symbol=plan.symbol,
            exit_side=plan.exit_side,
            trigger_price=plan.trigger_price,
            position_side=plan.position_side,
            client_order_id=plan.client_order_id,
        )

    def build_plan(
        self,
        *,
        filled_order: OrderState,
        account_state: AccountState,
        stop_distance_pct: Decimal | None = None,
    ) -> ProtectionPlan | None:
        if not self._is_new_entry_fill(filled_order):
            return None

        position = account_state.positions.get((filled_order.symbol, filled_order.position_side))
        if position is None or not position.is_open:
            return None

        if self._has_existing_protection(account_state, position):
            return None

        trigger_price = self._build_trigger_price(position, stop_distance_pct or self.default_stop_distance_pct)
        if trigger_price <= 0:
            return None

        return ProtectionPlan(
            symbol=position.symbol,
            position_side=position.position_side,
            exit_side=self._exit_side(position),
            trigger_price=trigger_price,
            client_order_id=f"guardian-stop-{position.symbol.lower()}-{position.position_side.lower()}",
        )

    def _is_new_entry_fill(self, order: OrderState) -> bool:
        return (
            order.status == OrderLifecycleStatus.FILLED
            and not order.reduce_only
            and not order.close_position
            and not order.is_algo
        )

    def _has_existing_protection(self, account_state: AccountState, position: PositionState) -> bool:
        for order in account_state.orders.values():
            if (
                order.symbol == position.symbol
                and order.position_side == position.position_side
                and order.is_algo
                and order.close_position
                and order.status in {OrderLifecycleStatus.NEW, OrderLifecycleStatus.PARTIALLY_FILLED}
            ):
                return True
        return False

    def _build_trigger_price(self, position: PositionState, stop_distance_pct: Decimal) -> Decimal:
        reference_price = position.entry_price or position.mark_price
        if reference_price <= 0:
            return Decimal("0")

        if position.direction == PositionDirection.LONG:
            return reference_price * (Decimal("1") - stop_distance_pct)
        if position.direction == PositionDirection.SHORT:
            return reference_price * (Decimal("1") + stop_distance_pct)
        return Decimal("0")

    def _exit_side(self, position: PositionState) -> Side:
        if position.direction == PositionDirection.SHORT:
            return Side.BUY
        return Side.SELL
