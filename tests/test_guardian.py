import asyncio
from decimal import Decimal

from cats_py.domain.enums import OrderLifecycleStatus, PositionDirection, Side
from cats_py.domain.models import AccountState, OrderState, PositionState
from cats_py.execution.guardian import PositionGuardian


class DummyBinance:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def countdown_cancel_all(self, symbol: str, countdown_ms: int) -> dict[str, object]:
        self.calls.append((symbol, countdown_ms))
        return {"symbol": symbol, "countdown_ms": countdown_ms}


class FlakyBinance:
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    async def countdown_cancel_all(self, symbol: str, countdown_ms: int) -> dict[str, object]:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("heartbeat failed")
        return {"symbol": symbol, "countdown_ms": countdown_ms}


def test_guardian_detects_unprotected_open_position() -> None:
    guardian = PositionGuardian(DummyBinance())
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

    alerts = guardian.find_unprotected_positions(account_state)

    assert len(alerts) == 1
    assert alerts[0].symbol == "BTCUSDT"
    assert account_state.kill_switch_active is True


def test_guardian_ignores_position_with_active_protection() -> None:
    guardian = PositionGuardian(DummyBinance())
    account_state = AccountState()
    account_state.upsert_position(
        PositionState(
            symbol="ETHUSDT",
            position_side="BOTH",
            direction=PositionDirection.SHORT,
            quantity=Decimal("-1"),
            entry_price=Decimal("3000"),
        )
    )
    account_state.upsert_order(
        OrderState(
            symbol="ETHUSDT",
            position_side="BOTH",
            status=OrderLifecycleStatus.NEW,
            side=Side.BUY,
            algo_order_id="algo-1",
            close_position=True,
            is_algo=True,
        )
    )

    alerts = guardian.find_unprotected_positions(account_state)

    assert alerts == []
    assert account_state.kill_switch_active is False


def test_guardian_kill_switches_when_protection_order_is_rejected() -> None:
    guardian = PositionGuardian(DummyBinance())
    account_state = AccountState()
    account_state.upsert_position(
        PositionState(
            symbol="SOLUSDT",
            position_side="BOTH",
            direction=PositionDirection.LONG,
            quantity=Decimal("10"),
            entry_price=Decimal("100"),
        )
    )
    order = OrderState(
        symbol="SOLUSDT",
        position_side="BOTH",
        status=OrderLifecycleStatus.REJECTED,
        side=Side.SELL,
        algo_order_id="algo-2",
        close_position=True,
        is_algo=True,
    )

    alert = guardian.handle_protection_order_update(account_state, order)

    assert alert is not None
    assert "protective order rejected" in alert.reason
    assert account_state.kill_switch_active is True


def test_guardian_starts_and_stops_auto_cancel_heartbeat() -> None:
    binance = DummyBinance()
    guardian = PositionGuardian(binance, heartbeat_seconds=0, countdown_ms=5000)
    account_state = AccountState()

    async def run() -> None:
        started = guardian.start_auto_cancel("BTCUSDT", account_state=account_state)
        duplicate = guardian.start_auto_cancel("BTCUSDT", account_state=account_state)
        await asyncio.sleep(0.01)
        status_before = guardian.heartbeat_status("BTCUSDT")
        stopped = await guardian.stop_auto_cancel("BTCUSDT")
        status_after = guardian.heartbeat_status("BTCUSDT")

        assert started is True
        assert duplicate is False
        assert status_before.active is True
        assert stopped is True
        assert status_after.active is False

    asyncio.run(run())
    assert binance.calls


def test_guardian_heartbeat_failures_activate_kill_switch() -> None:
    binance = FlakyBinance(failures=100)
    guardian = PositionGuardian(binance, heartbeat_seconds=0, countdown_ms=5000)
    account_state = AccountState()

    async def run() -> None:
        guardian.start_auto_cancel("ETHUSDT", account_state=account_state)
        status = guardian.heartbeat_status("ETHUSDT")
        for _ in range(100):
            if status.failure_count >= 2:
                break
            await asyncio.sleep(0.001)
            status = guardian.heartbeat_status("ETHUSDT")
        await guardian.stop_auto_cancel("ETHUSDT")

        assert status.failure_count >= 2
        assert status.last_error == "heartbeat failed"

    asyncio.run(run())
    assert account_state.kill_switch_active is True
