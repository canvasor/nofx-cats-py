from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from cats_py.domain.enums import OrderLifecycleStatus, OrderType, PositionDirection, Side
from cats_py.domain.models import AccountState, BalanceState, OrderState, PositionState


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if value is None:
        return datetime.now(timezone.utc)

    timestamp = float(value)
    if timestamp > 1_000_000_000_000:
        timestamp /= 1000.0
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _to_decimal(value: Any, default: str = "0") -> Decimal:
    if value in (None, ""):
        return Decimal(default)
    return Decimal(str(value))


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes"}
    return bool(value)


def _parse_side(value: Any) -> Side:
    if value == Side.SELL.value:
        return Side.SELL
    return Side.BUY


def _parse_order_type(value: Any) -> OrderType | None:
    if not isinstance(value, str):
        return None
    try:
        return OrderType(value)
    except ValueError:
        return None


def _parse_order_status(value: Any) -> OrderLifecycleStatus:
    if not isinstance(value, str):
        return OrderLifecycleStatus.UNKNOWN
    try:
        return OrderLifecycleStatus(value)
    except ValueError:
        return OrderLifecycleStatus.UNKNOWN


def _parse_position_direction(quantity: Decimal) -> PositionDirection:
    if quantity > 0:
        return PositionDirection.LONG
    if quantity < 0:
        return PositionDirection.SHORT
    return PositionDirection.FLAT


class BinanceUserEventHandler:
    def __init__(self, account_state: AccountState | None = None) -> None:
        self.account_state = account_state or AccountState()

    @staticmethod
    def event_type(payload: dict[str, Any]) -> str:
        event_type = payload.get("e") or payload.get("eventType")
        return str(event_type) if event_type is not None else "UNKNOWN"

    def apply(self, payload: dict[str, Any]) -> AccountState:
        event_time = _to_datetime(payload.get("E") or payload.get("eventTime") or payload.get("T"))
        self.account_state.record_user_stream_event(event_time)

        event_type = self.event_type(payload)
        if event_type == "ACCOUNT_UPDATE":
            self._apply_account_update(payload, event_time)
        elif event_type == "ORDER_TRADE_UPDATE":
            self._apply_order_trade_update(payload, event_time)
        elif event_type == "ALGO_UPDATE":
            self._apply_algo_update(payload, event_time)

        return self.account_state

    def _apply_account_update(self, payload: dict[str, Any], event_time: datetime) -> None:
        account = payload.get("a") or payload.get("account") or {}
        balances = account.get("B") or account.get("balances") or []
        for item in balances:
            if not isinstance(item, dict):
                continue
            asset = item.get("a") or item.get("asset")
            if not isinstance(asset, str):
                continue
            self.account_state.upsert_balance(
                BalanceState(
                    asset=asset,
                    wallet_balance=_to_decimal(item.get("wb") or item.get("walletBalance")),
                    available_balance=_to_decimal(
                        item.get("ab")
                        or item.get("availableBalance")
                        or item.get("cw")
                        or item.get("crossWalletBalance")
                    ),
                    cross_wallet_balance=_to_decimal(item.get("cw") or item.get("crossWalletBalance")),
                    updated_at=event_time,
                    raw=item,
                )
            )

        positions = account.get("P") or account.get("positions") or []
        for item in positions:
            if not isinstance(item, dict):
                continue
            symbol = item.get("s") or item.get("symbol")
            if not isinstance(symbol, str):
                continue
            quantity = _to_decimal(item.get("pa") or item.get("positionAmt"))
            self.account_state.upsert_position(
                PositionState(
                    symbol=symbol,
                    position_side=str(item.get("ps") or item.get("positionSide") or "BOTH"),
                    direction=_parse_position_direction(quantity),
                    quantity=quantity,
                    entry_price=_to_decimal(item.get("ep") or item.get("entryPrice")),
                    mark_price=_to_decimal(item.get("mp") or item.get("markPrice")),
                    notional=_to_decimal(item.get("notional")),
                    unrealized_pnl=_to_decimal(item.get("up") or item.get("unRealizedProfit")),
                    leverage=int(str(item.get("l") or item.get("leverage") or 1)),
                    margin_type=str(item.get("mt") or item.get("marginType") or "cross"),
                    isolated_wallet=_to_decimal(item.get("iw") or item.get("isolatedWallet")),
                    updated_at=event_time,
                    raw=item,
                )
            )

    def _apply_order_trade_update(self, payload: dict[str, Any], event_time: datetime) -> None:
        order = payload.get("o") or payload.get("order") or {}
        if not isinstance(order, dict):
            return

        symbol = order.get("s") or order.get("symbol")
        if not isinstance(symbol, str):
            return

        order_id = order.get("i") or order.get("orderId")
        self.account_state.upsert_order(
            OrderState(
                symbol=symbol,
                status=_parse_order_status(order.get("X") or order.get("status")),
                side=_parse_side(order.get("S") or order.get("side")),
                position_side=str(order.get("ps") or order.get("positionSide") or "BOTH"),
                order_id=str(order_id) if order_id is not None else None,
                client_order_id=order.get("c") or order.get("clientOrderId"),
                order_type=_parse_order_type(order.get("o") or order.get("type")),
                price=_to_decimal(order.get("p") or order.get("price")),
                avg_price=_to_decimal(order.get("ap") or order.get("avgPrice")),
                orig_qty=_to_decimal(order.get("q") or order.get("origQty")),
                executed_qty=_to_decimal(order.get("z") or order.get("executedQty")),
                reduce_only=_to_bool(order.get("R") or order.get("reduceOnly")),
                close_position=_to_bool(order.get("cp") or order.get("closePosition")),
                is_algo=False,
                created_at=event_time,
                updated_at=event_time,
                raw=order,
            )
        )

    def _apply_algo_update(self, payload: dict[str, Any], event_time: datetime) -> None:
        order = payload.get("ao") or payload.get("o") or payload.get("algoOrder") or {}
        if not isinstance(order, dict):
            return

        symbol = order.get("s") or order.get("symbol")
        if not isinstance(symbol, str):
            return

        algo_order_id = order.get("ai") or order.get("algoId") or order.get("algoOrderId")
        self.account_state.upsert_order(
            OrderState(
                symbol=symbol,
                status=_parse_order_status(order.get("X") or order.get("status") or order.get("algoStatus")),
                side=_parse_side(order.get("S") or order.get("side")),
                position_side=str(order.get("ps") or order.get("positionSide") or "BOTH"),
                client_order_id=order.get("c") or order.get("clientAlgoId"),
                algo_order_id=str(algo_order_id) if algo_order_id is not None else None,
                order_type=_parse_order_type(order.get("ot") or order.get("type")),
                price=_to_decimal(order.get("p") or order.get("price")),
                avg_price=_to_decimal(order.get("ap") or order.get("avgPrice")),
                orig_qty=_to_decimal(order.get("q") or order.get("origQty")),
                executed_qty=_to_decimal(order.get("z") or order.get("executedQty")),
                reduce_only=_to_bool(order.get("R") or order.get("reduceOnly")),
                close_position=_to_bool(order.get("cp") or order.get("closePosition")),
                is_algo=True,
                created_at=event_time,
                updated_at=event_time,
                raw=order,
            )
        )
