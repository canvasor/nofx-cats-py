from __future__ import annotations

from cats_py.infra.logging import configure_logging
from cats_py.infra.storage import JsonlStorage
from cats_py.services.paper_dataset import PaperDatasetService


def main() -> None:
    logger = configure_logging("cats_py.apps.run_paper_export")
    storage = JsonlStorage(base_dir="data")
    dataset = PaperDatasetService(storage)
    dataset_path = dataset.export_dataset()
    summary_path = dataset.export_summary()
    aggregates_path = dataset.export_aggregates()
    summary = dataset.build_summary()
    logger.info(
        "paper_export_completed",
        extra={
            "dataset_path": str(dataset_path),
            "summary_path": str(summary_path),
            "aggregates_path": str(aggregates_path),
            "total_decisions": summary.total_decisions,
            "executed_decisions": summary.executed_decisions,
            "ending_equity": summary.ending_equity,
            "realized_pnl": summary.realized_pnl,
        },
    )


if __name__ == "__main__":
    main()
