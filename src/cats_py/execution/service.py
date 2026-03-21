from __future__ import annotations

from dataclasses import dataclass, field

from cats_py.domain.models import AccountState, OrderResponse, OrderState
from cats_py.execution.guardian import PositionGuardian, ProtectionAlert
from cats_py.execution.protection import ProtectionOrchestrator


@dataclass(slots=True)
class ExecutionCycleResult:
    placed_protection: OrderResponse | None = None
    protection_alerts: list[ProtectionAlert] = field(default_factory=list)
    heartbeat_started: list[str] = field(default_factory=list)
    heartbeat_stopped: list[str] = field(default_factory=list)


class ExecutionService:
    """Coordinate entry fills, protective stops, and auto-cancel heartbeats."""

    def __init__(self, guardian: PositionGuardian, protection: ProtectionOrchestrator) -> None:
        self.guardian = guardian
        self.protection = protection

    async def handle_order_update(
        self,
        *,
        account_state: AccountState,
        order: OrderState,
    ) -> ExecutionCycleResult:
        result = ExecutionCycleResult()

        if not order.is_algo:
            result.placed_protection = await self.protection.ensure_disaster_stop(
                filled_order=order,
                account_state=account_state,
            )

        if result.placed_protection is not None:
            started = self.guardian.start_auto_cancel(order.symbol, account_state=account_state)
            if started:
                result.heartbeat_started.append(order.symbol)

        protection_alert = self.guardian.handle_protection_order_update(account_state, order)
        if protection_alert is not None:
            result.protection_alerts.append(protection_alert)

        result.protection_alerts.extend(self.guardian.find_unprotected_positions(account_state))

        if not self._has_open_symbol_position(account_state, order.symbol):
            stopped = await self.guardian.stop_auto_cancel(order.symbol)
            if stopped:
                result.heartbeat_stopped.append(order.symbol)

        return result

    @staticmethod
    def _has_open_symbol_position(account_state: AccountState, symbol: str) -> bool:
        for position in account_state.positions.values():
            if position.symbol == symbol and position.is_open:
                return True
        return False
