import asyncio
from decimal import Decimal

from cats_py.domain.enums import OrderLifecycleStatus, PositionDirection, Side
from cats_py.domain.models import AccountState, OrderResponse, OrderState, PositionState
from cats_py.execution.protection import ProtectionOrchestrator


class DummyGuardian:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def place_disaster_stop(
        self,
        *,
        symbol: str,
        exit_side: Side,
        trigger_price: Decimal,
        position_side: str = "BOTH",
        client_order_id: str | None = None,
    ) -> OrderResponse:
        payload = {
            "symbol": symbol,
            "exit_side": exit_side,
            "trigger_price": trigger_price,
            "position_side": position_side,
            "client_order_id": client_order_id,
        }
        self.calls.append(payload)
        return OrderResponse(venue_order_id="algo-1", route="algo", status="NEW", raw=payload)


def test_protection_orchestrator_places_stop_for_filled_long_entry() -> None:
    guardian = DummyGuardian()
    orchestrator = ProtectionOrchestrator(guardian, default_stop_distance_pct=Decimal("0.02"))
    account_state = AccountState()
    account_state.upsert_position(
        PositionState(
            symbol="BTCUSDT",
            position_side="BOTH",
            direction=PositionDirection.LONG,
            quantity=Decimal("0.010"),
            entry_price=Decimal("50000"),
            mark_price=Decimal("50100"),
            notional=Decimal("500"),
        )
    )
    filled_order = OrderState(
        symbol="BTCUSDT",
        position_side="BOTH",
        status=OrderLifecycleStatus.FILLED,
        side=Side.BUY,
        order_id="123",
        client_order_id="entry-1",
        executed_qty=Decimal("0.010"),
    )

    response = asyncio.run(
        orchestrator.ensure_disaster_stop(filled_order=filled_order, account_state=account_state)
    )

    assert response is not None
    assert guardian.calls[0]["symbol"] == "BTCUSDT"
    assert guardian.calls[0]["exit_side"] == Side.SELL
    assert guardian.calls[0]["trigger_price"] == Decimal("49000.00")


def test_protection_orchestrator_skips_when_protection_already_exists() -> None:
    guardian = DummyGuardian()
    orchestrator = ProtectionOrchestrator(guardian)
    account_state = AccountState()
    account_state.upsert_position(
        PositionState(
            symbol="ETHUSDT",
            position_side="BOTH",
            direction=PositionDirection.SHORT,
            quantity=Decimal("-2"),
            entry_price=Decimal("3000"),
            mark_price=Decimal("2990"),
            notional=Decimal("-6000"),
        )
    )
    account_state.upsert_order(
        OrderState(
            symbol="ETHUSDT",
            position_side="BOTH",
            status=OrderLifecycleStatus.NEW,
            side=Side.BUY,
            algo_order_id="algo-1",
            client_order_id="guardian-stop-ethusdt-both",
            close_position=True,
            is_algo=True,
        )
    )
    filled_order = OrderState(
        symbol="ETHUSDT",
        position_side="BOTH",
        status=OrderLifecycleStatus.FILLED,
        side=Side.SELL,
        order_id="200",
        client_order_id="entry-2",
    )

    response = asyncio.run(
        orchestrator.ensure_disaster_stop(filled_order=filled_order, account_state=account_state)
    )

    assert response is None
    assert guardian.calls == []


def test_protection_orchestrator_skips_reduce_only_and_non_fills() -> None:
    guardian = DummyGuardian()
    orchestrator = ProtectionOrchestrator(guardian)
    account_state = AccountState()
    account_state.upsert_position(
        PositionState(
            symbol="SOLUSDT",
            position_side="BOTH",
            direction=PositionDirection.LONG,
            quantity=Decimal("10"),
            entry_price=Decimal("100"),
            mark_price=Decimal("101"),
        )
    )

    reduce_only_order = OrderState(
        symbol="SOLUSDT",
        position_side="BOTH",
        status=OrderLifecycleStatus.FILLED,
        side=Side.SELL,
        order_id="300",
        reduce_only=True,
    )
    partial_order = OrderState(
        symbol="SOLUSDT",
        position_side="BOTH",
        status=OrderLifecycleStatus.PARTIALLY_FILLED,
        side=Side.BUY,
        order_id="301",
    )

    assert (
        asyncio.run(
            orchestrator.ensure_disaster_stop(filled_order=reduce_only_order, account_state=account_state)
        )
        is None
    )
    assert (
        asyncio.run(
            orchestrator.ensure_disaster_stop(filled_order=partial_order, account_state=account_state)
        )
        is None
    )
    assert guardian.calls == []
