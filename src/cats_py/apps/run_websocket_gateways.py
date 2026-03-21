from __future__ import annotations

import asyncio
import logging

from cats_py.app.bootstrap import bootstrap
from cats_py.connectors.binance.user_stream import UserStreamSession
from cats_py.connectors.binance.ws_market import BinanceMarketStream
from cats_py.connectors.binance.ws_private import BinancePrivateStream
from cats_py.connectors.binance.ws_public import BinancePublicStream
from cats_py.domain.models import AccountState, OrderState
from cats_py.execution.guardian import PositionGuardian
from cats_py.infra.logging import configure_logging
from cats_py.infra.storage import JsonlStorage
from cats_py.services.reconciliation import AccountReconciler
from cats_py.services.recovery import UserStreamRecoveryCoordinator
from cats_py.services.user_state import BinanceUserEventHandler


async def consume(
    name: str,
    stream,
    storage: JsonlStorage,
    logger: logging.Logger,
    *,
    user_handler: BinanceUserEventHandler | None = None,
    guardian: PositionGuardian | None = None,
    connection_id: str | None = None,
    on_connect=None,
    on_disconnect=None,
) -> None:
    count = 0
    async for message in stream.messages(on_connect=on_connect, on_disconnect=on_disconnect):
        if name == "private":
            event_type = BinanceUserEventHandler.event_type(message)
            storage.append_event(
                "binance_user_event",
                message,
                event_type=event_type,
                connection_id=connection_id,
                tags={"stream": name},
            )
            if user_handler is not None:
                account_state = user_handler.apply(message)
                protection_alerts = _collect_guardian_alerts(
                    guardian=guardian,
                    account_state=account_state,
                    event_type=event_type,
                    message=message,
                )
                logger.info(
                    "user_state_updated",
                    extra={
                        "event_type": event_type,
                        "open_positions": account_state.open_position_count(),
                        "tracked_orders": len(account_state.orders),
                    },
                )
                for alert in protection_alerts:
                    logger.warning(
                        "protection_alert",
                        extra={
                            "symbol": alert.symbol,
                            "position_side": alert.position_side,
                            "reason": alert.reason,
                            "severity": alert.severity,
                        },
                    )
        else:
            storage.append(f"binance_{name}", message)
        logger.info("ws_message_received", extra={"stream": name, "message": message})
        count += 1
        if count >= 3:
            break


async def main() -> None:
    services = bootstrap()
    logger = configure_logging("cats_py.apps.run_websocket_gateways", log_level=services.runtime.log_level)
    logger.info("service_started", extra={"mode_summary": services.mode_summary.as_dict()})

    runtime = services.runtime
    binance = services.binance
    storage = JsonlStorage(base_dir="data")
    user_handler = BinanceUserEventHandler()
    guardian = PositionGuardian(binance)
    reconciler = AccountReconciler(binance, account_state=user_handler.account_state)
    recovery = UserStreamRecoveryCoordinator(reconciler, logger)

    user_session = UserStreamSession(binance)
    listen_key = await user_session.start()

    public_stream = BinancePublicStream(
        runtime.binance_ws_public_url,
        streams=["btcusdt@depth", "ethusdt@bookTicker"],
    )
    market_stream = BinanceMarketStream(
        runtime.binance_ws_market_url,
        streams=["btcusdt@markPrice", "btcusdt@kline_1m"],
    )
    private_stream = BinancePrivateStream(
        runtime.binance_ws_private_url,
        listen_key=listen_key,
        events=["ORDER_TRADE_UPDATE", "ACCOUNT_UPDATE", "ALGO_UPDATE"],
    )

    try:
        await asyncio.gather(
            consume("public", public_stream, storage, logger),
            consume("market", market_stream, storage, logger),
            consume(
                "private",
                private_stream,
                storage,
                logger,
                user_handler=user_handler,
                guardian=guardian,
                connection_id=listen_key,
                on_connect=recovery.on_private_stream_connect,
                on_disconnect=recovery.on_private_stream_disconnect,
            ),
        )
    finally:
        await user_session.close()
        await binance.close()


if __name__ == "__main__":
    asyncio.run(main())


def _collect_guardian_alerts(
    *,
    guardian: PositionGuardian | None,
    account_state: AccountState,
    event_type: str,
    message: dict[str, object],
) -> list:
    if guardian is None:
        return []

    alerts = []
    if event_type == "ALGO_UPDATE":
        order = _resolve_private_order(account_state, message)
        alert = guardian.handle_protection_order_update(account_state, order)
        if alert is not None:
            alerts.append(alert)
    alerts.extend(guardian.find_unprotected_positions(account_state))
    return alerts


def _resolve_private_order(account_state: AccountState, message: dict[str, object]) -> OrderState | None:
    payload = message.get("ao") or message.get("o") or message.get("algoOrder")
    if not isinstance(payload, dict):
        return None

    algo_order_id = payload.get("ai") or payload.get("algoId") or payload.get("algoOrderId")
    if algo_order_id is not None:
        order = account_state.orders.get(f"algo:{algo_order_id}")
        if order is not None:
            return order

    order_id = payload.get("i") or payload.get("orderId")
    if order_id is not None:
        order = account_state.orders.get(f"order:{order_id}")
        if order is not None:
            return order

    client_order_id = payload.get("c") or payload.get("clientOrderId") or payload.get("clientAlgoId")
    if client_order_id is not None:
        return account_state.orders.get(f"client:{client_order_id}")
    return None
