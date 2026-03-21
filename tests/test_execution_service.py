import asyncio
from decimal import Decimal

from cats_py.domain.enums import OrderLifecycleStatus, PositionDirection, Side
from cats_py.domain.models import AccountState, OrderResponse, OrderState, PositionState
from cats_py.execution.guardian import ProtectionAlert
from cats_py.execution.service import ExecutionService


class DummyGuardian:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.stopped: list[str] = []
        self.handled_orders: list[str] = []
        self.alerts: list[ProtectionAlert] = []

    def start_auto_cancel(self, symbol: str, account_state: AccountState | None = None) -> bool:
        self.started.append(symbol)
        return True

    async def stop_auto_cancel(self, symbol: str) -> bool:
        self.stopped.append(symbol)
        return True

    def handle_protection_order_update(
        self,
        account_state: AccountState,
        order: OrderState | None,
    ) -> ProtectionAlert | None:
        if order is None:
            return None
        self.handled_orders.append(order.identity)
        return None

    def find_unprotected_positions(self, account_state: AccountState) -> list[ProtectionAlert]:
        return list(self.alerts)


class DummyProtection:
    def __init__(self, response: OrderResponse | None = None) -> None:
        self.calls: list[str] = []
        self.response = response

    async def ensure_disaster_stop(
        self,
        *,
        filled_order: OrderState,
        account_state: AccountState,
        stop_distance_pct=None,
    ) -> OrderResponse | None:
        self.calls.append(filled_order.identity)
        return self.response


def test_execution_service_starts_heartbeat_after_protection_submission() -> None:
    guardian = DummyGuardian()
    protection = DummyProtection(
        OrderResponse(venue_order_id="algo-1", route="algo", status="NEW", raw={"ok": True})
    )
    service = ExecutionService(guardian, protection)
    account_state = AccountState()
    account_state.upsert_position(
        PositionState(
            symbol="BTCUSDT",
            position_side="BOTH",
            direction=PositionDirection.LONG,
            quantity=Decimal("0.010"),
            entry_price=Decimal("50000"),
        )
    )
    order = OrderState(
        symbol="BTCUSDT",
        position_side="BOTH",
        status=OrderLifecycleStatus.FILLED,
        side=Side.BUY,
        order_id="123",
    )

    result = asyncio.run(service.handle_order_update(account_state=account_state, order=order))

    assert protection.calls == ["order:123"]
    assert result.placed_protection is not None
    assert result.heartbeat_started == ["BTCUSDT"]
    assert result.heartbeat_stopped == []


def test_execution_service_stops_heartbeat_when_symbol_has_no_open_position() -> None:
    guardian = DummyGuardian()
    protection = DummyProtection(None)
    service = ExecutionService(guardian, protection)
    account_state = AccountState()
    order = OrderState(
        symbol="ETHUSDT",
        position_side="BOTH",
        status=OrderLifecycleStatus.FILLED,
        side=Side.SELL,
        order_id="200",
        reduce_only=True,
    )

    result = asyncio.run(service.handle_order_update(account_state=account_state, order=order))

    assert result.heartbeat_stopped == ["ETHUSDT"]
    assert guardian.stopped == ["ETHUSDT"]


def test_execution_service_collects_guardian_alerts() -> None:
    guardian = DummyGuardian()
    guardian.alerts.append(
        ProtectionAlert(
            symbol="SOLUSDT",
            position_side="BOTH",
            reason="missing active protective stop for SOLUSDT:BOTH",
            severity="critical",
        )
    )
    protection = DummyProtection(None)
    service = ExecutionService(guardian, protection)
    account_state = AccountState()
    account_state.upsert_position(
        PositionState(
            symbol="SOLUSDT",
            position_side="BOTH",
            direction=PositionDirection.LONG,
            quantity=Decimal("5"),
            entry_price=Decimal("100"),
        )
    )
    order = OrderState(
        symbol="SOLUSDT",
        position_side="BOTH",
        status=OrderLifecycleStatus.FILLED,
        side=Side.BUY,
        order_id="300",
        is_algo=True,
        close_position=True,
        algo_order_id="algo-9",
    )

    result = asyncio.run(service.handle_order_update(account_state=account_state, order=order))

    assert len(result.protection_alerts) == 1
    assert result.protection_alerts[0].symbol == "SOLUSDT"
