from __future__ import annotations

import asyncio
from decimal import Decimal

from cats_py.app.bootstrap import bootstrap
from cats_py.domain.enums import OrderLifecycleStatus, OrderType, PositionDirection, Side, TimeInForce
from cats_py.domain.models import AccountState, OrderRequest, OrderState, PositionState
from cats_py.execution.guardian import PositionGuardian
from cats_py.infra.logging import configure_logging
from cats_py.execution.order_router import OrderRouter
from cats_py.execution.protection import ProtectionOrchestrator
from cats_py.execution.service import ExecutionService
from cats_py.execution.validator import PreTradeValidator


async def main() -> None:
    services = bootstrap()
    logger = configure_logging("cats_py.apps.run_execution_daemon", log_level=services.runtime.log_level)
    logger.info("service_started", extra={"mode_summary": services.mode_summary.as_dict()})

    binance = services.binance

    exchange_info = await binance.get_exchange_info()
    leverage_brackets = await binance.get_leverage_brackets()
    symbol_rules = PreTradeValidator.build_symbol_rules(exchange_info, leverage_brackets)
    validator = PreTradeValidator(symbol_rules)
    router = OrderRouter(binance, validator)
    guardian = PositionGuardian(binance, router=router)
    protection = ProtectionOrchestrator(guardian)
    execution_service = ExecutionService(guardian, protection)

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
    logger.info(
        "payload_preview",
        extra={"route": "normal", "symbol": sample_order.symbol, "payload": router._to_payload(sample_order)},
    )

    sample_stop = OrderRouter.build_disaster_stop_request(
        symbol="BTCUSDT",
        exit_side=Side.SELL,
        trigger_price=Decimal("48000"),
        client_order_id="demo-close-all-stop",
    )
    logger.info(
        "payload_preview",
        extra={"route": "algo", "symbol": sample_stop.symbol, "payload": router._to_payload(sample_stop)},
    )

    account_state = AccountState()
    account_state.upsert_position(
        PositionState(
            symbol="BTCUSDT",
            position_side="BOTH",
            direction=PositionDirection.LONG,
            quantity=Decimal("0.001"),
            entry_price=Decimal("50000"),
            mark_price=Decimal("50010"),
            notional=Decimal("50"),
        )
    )
    filled_order = OrderState(
        symbol="BTCUSDT",
        position_side="BOTH",
        status=OrderLifecycleStatus.FILLED,
        side=Side.BUY,
        order_id="demo-fill-1",
        client_order_id="demo-limit-order",
        executed_qty=Decimal("0.001"),
    )
    execution_result = await execution_service.handle_order_update(
        account_state=account_state,
        order=filled_order,
    )
    logger.info(
        "execution_cycle_preview",
        extra={
            "symbol": filled_order.symbol,
            "placed_protection": execution_result.placed_protection,
            "heartbeat_started": execution_result.heartbeat_started,
            "heartbeat_stopped": execution_result.heartbeat_stopped,
            "protection_alerts": execution_result.protection_alerts,
        },
    )
    await guardian.stop_all_auto_cancel()
    await binance.close()


if __name__ == "__main__":
    asyncio.run(main())
