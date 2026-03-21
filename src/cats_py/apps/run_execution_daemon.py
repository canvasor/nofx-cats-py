from __future__ import annotations

import asyncio
from decimal import Decimal

from cats_py.app.bootstrap import bootstrap
from cats_py.domain.enums import OrderType, Side, TimeInForce
from cats_py.domain.models import OrderRequest
from cats_py.execution.order_router import OrderRouter
from cats_py.execution.validator import PreTradeValidator


async def main() -> None:
    services = bootstrap()
    binance = services["binance"]

    exchange_info = await binance.get_exchange_info()
    leverage_brackets = await binance.get_leverage_brackets()
    symbol_rules = PreTradeValidator.build_symbol_rules(exchange_info, leverage_brackets)
    validator = PreTradeValidator(symbol_rules)
    router = OrderRouter(binance, validator)

    # 这里只演示构造，不建议直接在 production 环境调用。
    sample_order = OrderRequest(
        symbol="BTCUSDT",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("0.001"),
        price=Decimal("50000"),
        time_in_force=TimeInForce.GTC,
        client_order_id="demo-limit-order",
        new_order_resp_type="ACK",
    )
    print("[execution] validated payload would be routed as:", router._to_payload(sample_order))

    sample_stop = OrderRouter.build_disaster_stop_request(
        symbol="BTCUSDT",
        exit_side=Side.SELL,
        trigger_price=Decimal("48000"),
        client_order_id="demo-close-all-stop",
    )
    print("[execution] disaster stop payload would be routed as:", router._to_payload(sample_stop))
    await binance.close()


if __name__ == "__main__":
    asyncio.run(main())
