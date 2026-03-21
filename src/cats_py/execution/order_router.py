from __future__ import annotations

from decimal import Decimal
from typing import Any

from cats_py.connectors.binance.rest import BinanceRestClient
from cats_py.domain.enums import OrderType, Side
from cats_py.domain.models import OrderRequest, OrderResponse
from cats_py.execution.validator import ALGO_ORDER_TYPES, PreTradeValidator


class OrderRouter:
    def __init__(self, binance: BinanceRestClient, validator: PreTradeValidator) -> None:
        self.binance = binance
        self.validator = validator

    async def place(self, request: OrderRequest, mark_price: Decimal | None = None) -> OrderResponse:
        normalized = self.validator.validate(request, mark_price=mark_price)
        payload = self._to_payload(normalized)

        if normalized.order_type in ALGO_ORDER_TYPES:
            raw = await self.binance.new_algo_order(payload)
            return OrderResponse(
                venue_order_id=self._extract_order_id(raw),
                route="algo",
                status=self._extract_status(raw, fallback="submitted"),
                raw=raw,
            )

        raw = await self.binance.new_order(payload)
        return OrderResponse(
            venue_order_id=self._extract_order_id(raw),
            route="normal",
            status=self._extract_status(raw, fallback="submitted"),
            raw=raw,
        )

    @staticmethod
    def build_disaster_stop_request(
        *,
        symbol: str,
        exit_side: Side,
        trigger_price: Decimal,
        position_side: str = "BOTH",
        client_order_id: str | None = None,
        working_type: str = "MARK_PRICE",
        price_protect: bool = False,
    ) -> OrderRequest:
        return OrderRequest(
            symbol=symbol,
            side=exit_side,
            order_type=OrderType.STOP_MARKET,
            trigger_price=trigger_price,
            close_position=True,
            position_side=position_side,
            client_order_id=client_order_id,
            working_type=working_type,
            price_protect=price_protect,
        )

    def _to_payload(self, request: OrderRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "symbol": request.symbol,
            "side": request.side.value,
            "type": request.order_type.value,
            "positionSide": request.position_side,
        }

        if request.quantity is not None:
            payload["quantity"] = str(request.quantity)
        if request.price is not None:
            payload["price"] = str(request.price)
        if request.trigger_price is not None:
            payload["triggerPrice"] = str(request.trigger_price)
        if request.time_in_force is not None:
            payload["timeInForce"] = request.time_in_force.value
        if request.reduce_only:
            payload["reduceOnly"] = "true"
        if request.close_position:
            payload["closePosition"] = "true"
        if request.working_type:
            payload["workingType"] = request.working_type
        if request.price_protect:
            payload["priceProtect"] = "TRUE"
        if request.self_trade_prevention_mode:
            payload["selfTradePreventionMode"] = request.self_trade_prevention_mode
        if request.new_order_resp_type:
            payload["newOrderRespType"] = request.new_order_resp_type
        if request.activate_price is not None:
            payload["activatePrice"] = str(request.activate_price)
        if request.callback_rate is not None:
            payload["callbackRate"] = str(request.callback_rate)

        if request.client_order_id:
            key = "clientAlgoId" if request.order_type in ALGO_ORDER_TYPES else "newClientOrderId"
            payload[key] = request.client_order_id

        return payload

    @staticmethod
    def _extract_order_id(raw: dict[str, Any]) -> str | None:
        data = raw.get("data", raw)
        if isinstance(data, dict):
            value = data.get("orderId") or data.get("algoId") or data.get("algoOrderId")
            return str(value) if value is not None else None
        return None

    @staticmethod
    def _extract_status(raw: dict[str, Any], fallback: str) -> str:
        data = raw.get("data", raw)
        if isinstance(data, dict):
            value = data.get("status") or data.get("algoStatus")
            return str(value) if value is not None else fallback
        return fallback
