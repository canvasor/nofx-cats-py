from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol

from cats_py.domain.enums import PositionDirection
from cats_py.domain.models import AccountState, BalanceState, OrderState, PositionState
from cats_py.services.user_state import (
    _parse_order_status,
    _parse_order_type,
    _parse_side,
    _to_bool,
    _to_datetime,
    _to_decimal,
)


class BinanceAccountReader(Protocol):
    async def get_account_info(self) -> dict[str, Any]: ...

    async def get_position_risk(self, symbol: str | None = None) -> dict[str, Any]: ...

    async def get_open_orders(self, symbol: str | None = None) -> dict[str, Any]: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_position_direction(quantity: Decimal) -> PositionDirection:
    if quantity > 0:
        return PositionDirection.LONG
    if quantity < 0:
        return PositionDirection.SHORT
    return PositionDirection.FLAT


class AccountReconciler:
    def __init__(self, client: BinanceAccountReader, account_state: AccountState | None = None) -> None:
        self.client = client
        self.account_state = account_state or AccountState()
        self.logger = logging.getLogger("cats_py.services.reconciliation")

    async def reconcile(self, symbol: str | None = None) -> AccountState:
        try:
            account_info = await self.client.get_account_info()
            position_risk = await self.client.get_position_risk(symbol=symbol)
            open_orders = await self.client.get_open_orders(symbol=symbol)

            balances = self._parse_balances(account_info)
            positions = self._parse_positions(account_info, position_risk)
            orders = self._parse_orders(open_orders)

            if self._has_existing_state() and self._is_mismatch(balances, positions, orders):
                self.account_state.record_state_mismatch("incremental state diverged from reconciliation snapshot")
                self.logger.warning(
                    "account_state_mismatch",
                    extra={"mismatch_count": self.account_state.state_mismatch_count},
                )
            else:
                self.account_state.clear_state_mismatch()

            self.account_state.replace_balances(balances)
            self.account_state.replace_positions(positions)
            self.account_state.replace_orders(orders)
            self.account_state.mark_reconciled()
            self.account_state.clear_reconcile_failure()
            return self.account_state
        except Exception as exc:
            self.account_state.record_reconcile_failure(str(exc))
            self.logger.warning(
                "account_reconcile_failed",
                extra={"failure_count": self.account_state.reconcile_failure_count, "reason": str(exc)},
            )
            raise

    def _parse_balances(self, account_info: dict[str, Any]) -> list[BalanceState]:
        assets = account_info.get("data", account_info).get("assets", [])
        if not isinstance(assets, list):
            return []

        reconciled_at = _utc_now()
        balances: list[BalanceState] = []
        for item in assets:
            if not isinstance(item, dict):
                continue
            asset = item.get("asset")
            if not isinstance(asset, str):
                continue
            balances.append(
                BalanceState(
                    asset=asset,
                    wallet_balance=_to_decimal(item.get("walletBalance")),
                    available_balance=_to_decimal(item.get("availableBalance")),
                    cross_wallet_balance=_to_decimal(item.get("crossWalletBalance")),
                    updated_at=reconciled_at,
                    raw=item,
                )
            )
        return balances

    def _parse_positions(self, account_info: dict[str, Any], position_risk: dict[str, Any]) -> list[PositionState]:
        positions = account_info.get("data", account_info).get("positions", [])
        if not isinstance(positions, list):
            return []

        risk_rows = position_risk.get("data", position_risk)
        risk_map: dict[tuple[str, str], dict[str, Any]] = {}
        if isinstance(risk_rows, list):
            for item in risk_rows:
                if not isinstance(item, dict):
                    continue
                symbol = item.get("symbol")
                if not isinstance(symbol, str):
                    continue
                position_side = str(item.get("positionSide") or "BOTH")
                risk_map[(symbol, position_side)] = item

        reconciled_at = _utc_now()
        result: list[PositionState] = []
        for item in positions:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            if not isinstance(symbol, str):
                continue
            position_side = str(item.get("positionSide") or "BOTH")
            quantity = _to_decimal(item.get("positionAmt"))
            risk_item = risk_map.get((symbol, position_side), {})
            result.append(
                PositionState(
                    symbol=symbol,
                    position_side=position_side,
                    direction=_parse_position_direction(quantity),
                    quantity=quantity,
                    entry_price=_to_decimal(item.get("entryPrice")),
                    mark_price=_to_decimal(risk_item.get("markPrice")),
                    notional=_to_decimal(risk_item.get("notional")),
                    unrealized_pnl=_to_decimal(item.get("unrealizedProfit")),
                    leverage=int(str(item.get("leverage") or 1)),
                    margin_type=str(item.get("marginType") or "cross"),
                    isolated_wallet=_to_decimal(item.get("isolatedWallet")),
                    updated_at=reconciled_at,
                    raw={**item, "positionRisk": risk_item},
                )
            )
        return result

    def _parse_orders(self, open_orders: dict[str, Any]) -> list[OrderState]:
        rows = open_orders.get("data", open_orders)
        if not isinstance(rows, list):
            return []

        result: list[OrderState] = []
        reconciled_at = _utc_now()
        for item in rows:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            if not isinstance(symbol, str):
                continue
            order_id = item.get("orderId")
            result.append(
                OrderState(
                    symbol=symbol,
                    status=_parse_order_status(item.get("status")),
                    side=_parse_side(item.get("side")),
                    position_side=str(item.get("positionSide") or "BOTH"),
                    order_id=str(order_id) if order_id is not None else None,
                    client_order_id=item.get("clientOrderId"),
                    order_type=_parse_order_type(item.get("type")),
                    price=_to_decimal(item.get("price")),
                    avg_price=_to_decimal(item.get("avgPrice")),
                    orig_qty=_to_decimal(item.get("origQty")),
                    executed_qty=_to_decimal(item.get("executedQty")),
                    reduce_only=_to_bool(item.get("reduceOnly")),
                    close_position=_to_bool(item.get("closePosition")),
                    is_algo=False,
                    created_at=_to_datetime(item.get("time") or reconciled_at),
                    updated_at=_to_datetime(item.get("updateTime") or reconciled_at),
                    raw=item,
                )
            )
        return result

    def _has_existing_state(self) -> bool:
        return bool(self.account_state.balances or self.account_state.positions or self.account_state.orders)

    def _is_mismatch(
        self,
        balances: list[BalanceState],
        positions: list[PositionState],
        orders: list[OrderState],
    ) -> bool:
        current_balances = sorted(
            (asset, state.wallet_balance, state.available_balance, state.cross_wallet_balance)
            for asset, state in self.account_state.balances.items()
        )
        next_balances = sorted(
            (state.asset, state.wallet_balance, state.available_balance, state.cross_wallet_balance)
            for state in balances
        )
        if current_balances != next_balances:
            return True

        current_positions = sorted(
            (
                key[0],
                key[1],
                state.quantity,
                state.entry_price,
                state.mark_price,
                state.notional,
                state.unrealized_pnl,
            )
            for key, state in self.account_state.positions.items()
        )
        next_positions = sorted(
            (
                state.symbol,
                state.position_side,
                state.quantity,
                state.entry_price,
                state.mark_price,
                state.notional,
                state.unrealized_pnl,
            )
            for state in positions
        )
        if current_positions != next_positions:
            return True

        current_orders = sorted(
            (
                key,
                state.status.value,
                state.executed_qty,
                state.orig_qty,
                state.price,
                state.avg_price,
            )
            for key, state in self.account_state.orders.items()
        )
        next_orders = sorted(
            (
                state.identity,
                state.status.value,
                state.executed_qty,
                state.orig_qty,
                state.price,
                state.avg_price,
            )
            for state in orders
        )
        return current_orders != next_orders
