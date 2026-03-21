import json

from cats_py.infra.storage import JsonlStorage
from cats_py.services.paper_dataset import PaperDatasetService


def test_jsonl_storage_can_read_back_stream(tmp_path) -> None:
    storage = JsonlStorage(base_dir=str(tmp_path))
    storage.append("paper_fill_log", {"decision_id": "decision-1", "fill_price": 100.0})

    rows = storage.read_stream("paper_fill_log")

    assert rows == [{"decision_id": "decision-1", "fill_price": 100.0}]


def test_paper_dataset_service_builds_joined_rows_and_exports(tmp_path) -> None:
    storage = JsonlStorage(base_dir=str(tmp_path))
    storage.append(
        "paper_decision_log",
        {
            "ts": "2026-03-21T00:00:00+00:00",
            "cycle_id": "cycle-1",
            "mode": "paper",
            "symbol": "BTCUSDT",
            "symbol_source": "core",
            "decision_status": "EXECUTE",
            "regime": "TREND",
            "selected_strategy": "trend_following",
            "action_score": 12.0,
            "feature_stale_seconds": 0.0,
            "risk": {
                "status": "APPROVED",
                "reason": "approved",
                "approved_notional": 100.0,
                "approved_leverage": 1.0,
            },
            "decision": {"decision_id": "decision-1"},
        },
    )
    storage.append(
        "paper_fill_log",
        {
            "ts": "2026-03-21T00:00:00+00:00",
            "cycle_id": "cycle-1",
            "decision_id": "decision-1",
            "symbol": "BTCUSDT",
            "fill_price": 101.0,
            "fill_quantity": 0.99,
            "realized_pnl_delta": 0.0,
            "resulting_quantity": 0.99,
            "turnover_notional_delta": 100.0,
            "fee_paid_delta": 0.04,
        },
    )
    storage.append(
        "paper_pnl_log",
        {
            "ts": "2026-03-21T00:00:00+00:00",
            "cycle_id": "cycle-1",
            "wallet_balance": 1000.0,
            "realized_pnl": 0.0,
            "funding_pnl": -0.2,
            "funding_pnl_delta": -0.2,
            "fees_paid": 0.04,
            "turnover_notional": 100.0,
            "unrealized_pnl": 10.0,
            "equity": 1010.0,
            "gross_exposure": 0.1,
            "open_positions": 1,
        },
    )

    service = PaperDatasetService(storage)

    rows = service.build_dataset_rows()
    summary = service.build_summary(rows)
    aggregates = service.build_aggregate_rows(rows)
    dataset_path = service.export_dataset()
    summary_path = service.export_summary()
    aggregates_path = service.export_aggregates()

    assert rows[0]["decision_id"] == "decision-1"
    assert rows[0]["fill_price"] == 101.0
    assert rows[0]["equity"] == 1010.0
    assert rows[0]["fee_paid_delta"] == 0.04
    assert rows[0]["funding_pnl"] == -0.2
    assert summary.executed_decisions == 1
    assert summary.ending_equity == 1010.0
    assert aggregates[0]["total_turnover_notional_delta"] == 100.0
    assert dataset_path.exists()
    assert summary_path.exists()
    assert aggregates_path.exists()

    exported_rows = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    exported_summary = json.loads(summary_path.read_text(encoding="utf-8").strip())
    exported_aggregates = [json.loads(line) for line in aggregates_path.read_text(encoding="utf-8").splitlines()]
    assert exported_rows[0]["symbol"] == "BTCUSDT"
    assert exported_summary["executed_decisions"] == 1
    assert any(item["group_by"] == "selected_strategy" for item in exported_aggregates)
