from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cats_py.infra.storage import JsonlStorage


@dataclass(slots=True)
class PaperReplaySummary:
    total_decisions: int
    executed_decisions: int
    no_trade_decisions: int
    realized_pnl: float
    ending_equity: float
    ending_gross_exposure: float


class PaperDatasetService:
    def __init__(self, storage: JsonlStorage) -> None:
        self.storage = storage

    def build_dataset_rows(self) -> list[dict[str, Any]]:
        decisions = self.storage.read_stream("paper_decision_log")
        fills = self._group_by_decision_id(self.storage.read_stream("paper_fill_log"))
        pnl_by_cycle = self._group_last_by_key(self.storage.read_stream("paper_pnl_log"), key="cycle_id")

        rows: list[dict[str, Any]] = []
        for decision in decisions:
            decision_id = str(decision.get("decision", {}).get("decision_id") or "")
            cycle_id = str(decision.get("cycle_id") or "")
            fill = fills.get(decision_id)
            pnl = pnl_by_cycle.get(cycle_id)
            rows.append(
                {
                    "ts": decision.get("ts"),
                    "cycle_id": cycle_id,
                    "decision_id": decision_id,
                    "mode": decision.get("mode"),
                    "symbol": decision.get("symbol"),
                    "symbol_source": decision.get("symbol_source"),
                    "decision_status": decision.get("decision_status"),
                    "regime": decision.get("regime"),
                    "selected_strategy": decision.get("selected_strategy"),
                    "action_score": decision.get("action_score"),
                    "feature_stale_seconds": decision.get("feature_stale_seconds"),
                    "risk_status": (decision.get("risk") or {}).get("status"),
                    "risk_reason": (decision.get("risk") or {}).get("reason"),
                    "approved_notional": (decision.get("risk") or {}).get("approved_notional"),
                    "approved_leverage": (decision.get("risk") or {}).get("approved_leverage"),
                    "fill_price": (fill or {}).get("fill_price"),
                    "fill_quantity": (fill or {}).get("fill_quantity"),
                    "realized_pnl_delta": (fill or {}).get("realized_pnl_delta"),
                    "resulting_quantity": (fill or {}).get("resulting_quantity"),
                    "turnover_notional_delta": (fill or {}).get("turnover_notional_delta"),
                    "fee_paid_delta": (fill or {}).get("fee_paid_delta"),
                    "wallet_balance": (pnl or {}).get("wallet_balance"),
                    "realized_pnl": (pnl or {}).get("realized_pnl"),
                    "funding_pnl": (pnl or {}).get("funding_pnl"),
                    "funding_pnl_delta": (pnl or {}).get("funding_pnl_delta"),
                    "fees_paid": (pnl or {}).get("fees_paid"),
                    "turnover_notional": (pnl or {}).get("turnover_notional"),
                    "unrealized_pnl": (pnl or {}).get("unrealized_pnl"),
                    "equity": (pnl or {}).get("equity"),
                    "gross_exposure": (pnl or {}).get("gross_exposure"),
                    "open_positions": (pnl or {}).get("open_positions"),
                }
            )
        return rows

    def build_summary(self, rows: list[dict[str, Any]] | None = None) -> PaperReplaySummary:
        dataset_rows = rows if rows is not None else self.build_dataset_rows()
        total_decisions = len(dataset_rows)
        executed_decisions = sum(1 for row in dataset_rows if row.get("decision_status") == "EXECUTE")
        no_trade_decisions = sum(1 for row in dataset_rows if row.get("decision_status") == "NO_TRADE")
        ending_row = dataset_rows[-1] if dataset_rows else {}
        return PaperReplaySummary(
            total_decisions=total_decisions,
            executed_decisions=executed_decisions,
            no_trade_decisions=no_trade_decisions,
            realized_pnl=float(ending_row.get("realized_pnl") or 0.0),
            ending_equity=float(ending_row.get("equity") or 0.0),
            ending_gross_exposure=float(ending_row.get("gross_exposure") or 0.0),
        )

    def build_aggregate_rows(self, rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        dataset_rows = rows if rows is not None else self.build_dataset_rows()
        aggregate_rows: list[dict[str, Any]] = []
        for group_by in ("selected_strategy", "regime", "symbol_source"):
            grouped: dict[str, list[dict[str, Any]]] = {}
            for row in dataset_rows:
                group_value = str(row.get(group_by) or "unknown")
                grouped.setdefault(group_value, []).append(row)

            for group_value, group_rows in grouped.items():
                executed_rows = [row for row in group_rows if row.get("decision_status") == "EXECUTE"]
                aggregate_rows.append(
                    {
                        "group_by": group_by,
                        "group_value": group_value,
                        "total_decisions": len(group_rows),
                        "executed_decisions": len(executed_rows),
                        "execute_rate": len(executed_rows) / len(group_rows) if group_rows else 0.0,
                        "avg_action_score": self._average(group_rows, "action_score"),
                        "avg_approved_notional": self._average(executed_rows, "approved_notional"),
                        "total_realized_pnl_delta": self._sum(executed_rows, "realized_pnl_delta"),
                        "total_fee_paid_delta": self._sum(executed_rows, "fee_paid_delta"),
                        "total_turnover_notional_delta": self._sum(executed_rows, "turnover_notional_delta"),
                    }
                )
        return aggregate_rows

    def export_dataset(self, stream: str = "paper_replay_dataset") -> Path:
        rows = self.build_dataset_rows()
        path = self.storage.stream_path(stream)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fp:
            for row in rows:
                fp.write(self._to_json_line(row))
        return path

    def export_summary(self, stream: str = "paper_replay_summary") -> Path:
        summary = self.build_summary()
        path = self.storage.stream_path(stream)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fp:
            fp.write(self._to_json_line(asdict(summary)))
        return path

    def export_aggregates(self, stream: str = "paper_replay_aggregates") -> Path:
        rows = self.build_aggregate_rows()
        path = self.storage.stream_path(stream)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fp:
            for row in rows:
                fp.write(self._to_json_line(row))
        return path

    @staticmethod
    def _group_by_decision_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for item in items:
            decision_id = item.get("decision_id")
            if decision_id is None:
                continue
            result[str(decision_id)] = item
        return result

    @staticmethod
    def _group_last_by_key(items: list[dict[str, Any]], *, key: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for item in items:
            value = item.get(key)
            if value is None:
                continue
            result[str(value)] = item
        return result

    @staticmethod
    def _to_json_line(payload: dict[str, Any]) -> str:
        import json

        return json.dumps(payload, ensure_ascii=False) + "\n"

    @staticmethod
    def _average(rows: list[dict[str, Any]], key: str) -> float:
        values = [float(row.get(key) or 0.0) for row in rows]
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def _sum(rows: list[dict[str, Any]], key: str) -> float:
        return sum(float(row.get(key) or 0.0) for row in rows)
