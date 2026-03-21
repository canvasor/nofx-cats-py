import asyncio
from decimal import Decimal

import pytest

from cats_py.domain.enums import OrderType, Side
from cats_py.domain.models import OrderRequest
from cats_py.execution.order_router import ALGO_ORDER_TYPES, OrderRouter
from cats_py.execution.validator import PreTradeValidator, SymbolRule


class DummyBinance:
    async def new_algo_order(self, params):
        return {"data": {"algoId": "algo-1", "algoStatus": "NEW", "echo": params}}

    async def new_order(self, params):
        return {"data": {"orderId": "order-1", "status": "NEW", "echo": params}}


def test_order_router_uses_algo_for_conditional_orders() -> None:
    validator = PreTradeValidator(
        {
            "BTCUSDT": SymbolRule(
                symbol="BTCUSDT",
                tick_size=Decimal("0.1"),
                step_size=Decimal("0.001"),
                min_qty=Decimal("0.001"),
                min_notional=Decimal("5"),
            )
        }
    )
    router = OrderRouter(DummyBinance(), validator)

    req = OrderRequest(
        symbol="BTCUSDT",
        side=Side.BUY,
        order_type=OrderType.STOP_MARKET,
        trigger_price=Decimal("50000"),
        close_position=True,
        client_order_id="algo-demo",
    )
    resp = asyncio.run(router.place(req))
    assert req.order_type in ALGO_ORDER_TYPES
    assert resp.route == "algo"
    assert resp.venue_order_id == "algo-1"


def test_order_router_uses_client_algo_id_for_algo_payload() -> None:
    validator = PreTradeValidator(
        {
            "BTCUSDT": SymbolRule(
                symbol="BTCUSDT",
                tick_size=Decimal("0.1"),
                step_size=Decimal("0.001"),
                min_qty=Decimal("0.001"),
                min_notional=Decimal("5"),
            )
        }
    )
    router = OrderRouter(DummyBinance(), validator)
    req = OrderRequest(
        symbol="BTCUSDT",
        side=Side.SELL,
        order_type=OrderType.STOP_MARKET,
        trigger_price=Decimal("48000"),
        close_position=True,
        client_order_id="algo-123",
    )
    payload = router._to_payload(req)
    assert payload["clientAlgoId"] == "algo-123"
    assert "newClientOrderId" not in payload


def test_validator_rejects_close_position_with_reduce_only() -> None:
    validator = PreTradeValidator(
        {
            "BTCUSDT": SymbolRule(
                symbol="BTCUSDT",
                tick_size=Decimal("0.1"),
                step_size=Decimal("0.001"),
                min_qty=Decimal("0.001"),
                min_notional=Decimal("5"),
            )
        }
    )
    req = OrderRequest(
        symbol="BTCUSDT",
        side=Side.SELL,
        order_type=OrderType.STOP_MARKET,
        trigger_price=Decimal("48000"),
        close_position=True,
        reduce_only=True,
    )
    with pytest.raises(ValueError, match="reduceOnly"):
        validator.validate(req)
