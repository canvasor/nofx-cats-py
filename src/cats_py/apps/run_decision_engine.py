from __future__ import annotations

import asyncio
from cats_py.app.bootstrap import bootstrap
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

            for decision in result.decisions:
                logger.info(
                    "decision_evaluated",
                    extra={
                        "decision_id": decision.decision_id,
                        "symbol": decision.symbol,
                        "status": decision.status.value,
                        "selected_strategy": decision.selected_strategy,
                        "regime": decision.regime.value,
                        "action_score": decision.action_score,
                    },
                )
            await asyncio.sleep(services.app_config.core_loop_interval_seconds)
    finally:
        await nofx.close()
        await services.binance.close()


if __name__ == "__main__":
    asyncio.run(main())
