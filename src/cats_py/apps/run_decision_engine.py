from __future__ import annotations

import asyncio
from cats_py.app.bootstrap import bootstrap
from cats_py.domain.enums import DecisionStatus
from cats_py.infra.logging import configure_logging
from cats_py.infra.storage import JsonlStorage
from cats_py.journal.recorder import JournalRecorder
from cats_py.services.decision_runtime import DecisionRuntimeService
from cats_py.services.paper_execution import PaperExecutionService
from cats_py.services.reconciliation import AccountReconciler


async def main() -> None:
    services = bootstrap()
    logger = configure_logging("cats_py.apps.run_decision_engine", log_level=services.runtime.log_level)
    logger.info("service_started", extra={"mode_summary": services.mode_summary.as_dict()})

    nofx = services.nofx
    decision_engine = services.decision_engine
    reconciler = AccountReconciler(services.binance)
    storage = JsonlStorage(base_dir="data")
    journal = JournalRecorder(storage)
    paper_execution = None
    if services.mode_summary.paper_execution:
        paper_execution = PaperExecutionService(
            journal=journal,
            starting_balance=services.app_config.paper_starting_balance,
            slippage_bps=services.app_config.paper_fill_slippage_bps,
            taker_fee_bps=services.app_config.paper_taker_fee_bps,
            funding_interval_hours=services.app_config.paper_funding_interval_hours,
        )
        logger.info(
            "paper_runtime_initialized",
            extra={
                "starting_balance": services.app_config.paper_starting_balance,
                "slippage_bps": services.app_config.paper_fill_slippage_bps,
                "taker_fee_bps": services.app_config.paper_taker_fee_bps,
                "funding_interval_hours": services.app_config.paper_funding_interval_hours,
            },
        )
    runtime_service = DecisionRuntimeService(
        nofx=nofx,
        decision_engine=decision_engine,
        reconciler=reconciler,
        journal=journal,
        app_config=services.app_config,
        symbol_config=services.symbol_config,
        mode_summary=services.mode_summary,
        paper_execution=paper_execution,
    )

    try:
        while True:
            try:
                result = await runtime_service.run_cycle()
            except Exception:  # noqa: BLE001
                logger.exception("decision_cycle_failed", extra={"mode": services.mode_summary.mode.value})
                await asyncio.sleep(services.app_config.core_loop_interval_seconds)
                continue

            execute_decisions = [decision for decision in result.decisions if decision.status == DecisionStatus.EXECUTE]
            account_snapshot = result.account_state.to_snapshot()
            logger.info(
                "decision_cycle_completed",
                extra={
                    "cycle_id": result.cycle_id,
                    "mode": services.mode_summary.mode.value,
                    "evaluated_symbols": len(result.decisions),
                    "execute_count": len(execute_decisions),
                    "no_trade_count": len(result.decisions) - len(execute_decisions),
                    "nofx_api_requests": result.request_stats.api_requests,
                    "nofx_cache_hits": result.request_stats.cache_hits,
                    "paper_equity": account_snapshot.equity if services.mode_summary.paper_execution else None,
                    "paper_gross_exposure": account_snapshot.gross_exposure if services.mode_summary.paper_execution else None,
                    "paper_open_positions": account_snapshot.open_positions if services.mode_summary.paper_execution else None,
                },
            )

            for decision in execute_decisions:
                logger.info(
                    "decision_execute_candidate",
                    extra={
                        "decision_id": decision.decision_id,
                        "symbol": decision.symbol,
                        "status": decision.status.value,
                        "side": decision.side.value if decision.side is not None else None,
                        "selected_strategy": decision.selected_strategy,
                        "regime": decision.regime.value,
                        "action_score": decision.action_score,
                        "approved_notional": decision.risk.approved_notional if decision.risk is not None else None,
                        "approved_leverage": decision.risk.approved_leverage if decision.risk is not None else None,
                    },
                )
            await asyncio.sleep(services.app_config.core_loop_interval_seconds)
    finally:
        await nofx.close()
        await services.binance.close()


if __name__ == "__main__":
    asyncio.run(main())
