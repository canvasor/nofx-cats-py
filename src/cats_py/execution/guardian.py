from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal

from cats_py.connectors.binance.rest import BinanceRestClient
from cats_py.domain.enums import OrderLifecycleStatus, Side
from cats_py.domain.models import AccountState, OrderResponse, OrderState, PositionState
from cats_py.execution.order_router import OrderRouter


@dataclass(slots=True, frozen=True)
class ProtectionAlert:
    symbol: str
    position_side: str
    reason: str
    severity: str = "warning"


@dataclass(slots=True, frozen=True)
class HeartbeatStatus:
    symbol: str
    active: bool
    failure_count: int
    last_error: str | None = None


class PositionGuardian:
    """维护交易所侧 auto-cancel 心跳，并可挂出灾难止损。"""

    def __init__(
        self,
        binance: BinanceRestClient,
        router: OrderRouter | None = None,
        heartbeat_seconds: int = 30,
        countdown_ms: int = 120000,
    ) -> None:
        self.binance = binance
        self.router = router
        self.heartbeat_seconds = heartbeat_seconds
        self.countdown_ms = countdown_ms
        self._running = True
        self._heartbeat_tasks: dict[str, asyncio.Task[None]] = {}
        self._heartbeat_failures: dict[str, int] = {}
        self._heartbeat_last_errors: dict[str, str] = {}

    async def maintain_auto_cancel(self, symbol: str, account_state: AccountState | None = None) -> None:
        while self._running and symbol in self._heartbeat_tasks:
            try:
                await self.binance.countdown_cancel_all(symbol=symbol, countdown_ms=self.countdown_ms)
                self._heartbeat_failures[symbol] = 0
                self._heartbeat_last_errors.pop(symbol, None)
            except Exception as exc:  # noqa: BLE001
                self._heartbeat_failures[symbol] = self._heartbeat_failures.get(symbol, 0) + 1
                self._heartbeat_last_errors[symbol] = str(exc)
                if account_state is not None and self._heartbeat_failures[symbol] >= 2:
                    account_state.activate_kill_switch(f"countdownCancelAll heartbeat failed for {symbol}: {exc}")
            await asyncio.sleep(self.heartbeat_seconds)

    def start_auto_cancel(self, symbol: str, account_state: AccountState | None = None) -> bool:
        if symbol in self._heartbeat_tasks:
            return False
        self._heartbeat_failures.setdefault(symbol, 0)
        self._heartbeat_tasks[symbol] = asyncio.create_task(
            self.maintain_auto_cancel(symbol, account_state=account_state),
            name=f"countdown-cancel-{symbol.lower()}",
        )
        return True

    async def stop_auto_cancel(self, symbol: str) -> bool:
        task = self._heartbeat_tasks.pop(symbol, None)
        if task is None:
            return False
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        return True

    async def stop_all_auto_cancel(self) -> None:
        symbols = list(self._heartbeat_tasks.keys())
        for symbol in symbols:
            await self.stop_auto_cancel(symbol)

    def heartbeat_status(self, symbol: str) -> HeartbeatStatus:
        task = self._heartbeat_tasks.get(symbol)
        return HeartbeatStatus(
            symbol=symbol,
            active=task is not None and not task.done(),
            failure_count=self._heartbeat_failures.get(symbol, 0),
            last_error=self._heartbeat_last_errors.get(symbol),
        )

    async def place_disaster_stop(
        self,
        *,
        symbol: str,
        exit_side: Side,
        trigger_price: Decimal,
        position_side: str = "BOTH",
        client_order_id: str | None = None,
    ) -> OrderResponse:
        if self.router is None:
            raise RuntimeError("PositionGuardian requires an OrderRouter to place disaster stops")
        request = OrderRouter.build_disaster_stop_request(
            symbol=symbol,
            exit_side=exit_side,
            trigger_price=trigger_price,
            position_side=position_side,
            client_order_id=client_order_id,
        )
        return await self.router.place(request)

    def has_active_protection(self, account_state: AccountState, position: PositionState) -> bool:
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

    def find_unprotected_positions(self, account_state: AccountState) -> list[ProtectionAlert]:
        alerts: list[ProtectionAlert] = []
        for position in account_state.positions.values():
            if not position.is_open:
                continue
            if self.has_active_protection(account_state, position):
                continue
            reason = f"missing active protective stop for {position.symbol}:{position.position_side}"
            account_state.activate_kill_switch(reason)
            alerts.append(
                ProtectionAlert(
                    symbol=position.symbol,
                    position_side=position.position_side,
                    reason=reason,
                    severity="critical",
                )
            )
        return alerts

    def handle_protection_order_update(
        self,
        account_state: AccountState,
        order: OrderState | None,
    ) -> ProtectionAlert | None:
        if order is None or not order.is_algo or not order.close_position:
            return None

        if order.status not in {
            OrderLifecycleStatus.REJECTED,
            OrderLifecycleStatus.CANCELED,
            OrderLifecycleStatus.EXPIRED,
        }:
            return None

        position = account_state.positions.get((order.symbol, order.position_side))
        if position is None or not position.is_open:
            return None

        reason = (
            f"protective order {order.status.value.lower()} for "
            f"{order.symbol}:{order.position_side}"
        )
        account_state.activate_kill_switch(reason)
        return ProtectionAlert(
            symbol=order.symbol,
            position_side=order.position_side,
            reason=reason,
            severity="critical",
        )

    def stop(self) -> None:
        self._running = False
