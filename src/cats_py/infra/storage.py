from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonlStorage:
    """开发态本地存储；生产态可切换到 ClickHouse / PostgreSQL。"""

    def __init__(self, base_dir: str = "data") -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def append(self, stream: str, payload: dict[str, Any]) -> None:
        path = self.base_dir / f"{stream}.jsonl"
        with path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(json_ready(payload), ensure_ascii=False) + "\n")

    def append_snapshot(
        self,
        stream: str,
        payload: Any,
        *,
        source: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        status: str = "ok",
        fetched_at: datetime | None = None,
        latency_ms: float | None = None,
        tags: dict[str, Any] | None = None,
    ) -> None:
        envelope = {
            "fetched_at": (fetched_at or datetime.now(timezone.utc)).isoformat(),
            "source": source,
            "endpoint": endpoint,
            "params": params or {},
            "status": status,
            "latency_ms": latency_ms,
            "tags": tags or {},
            "payload": json_ready(payload),
        }
        self.append(stream, envelope)


def json_ready(value: Any) -> Any:
    if is_dataclass(value):
        return json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            return str(value)
    return str(value) if value.__class__.__name__ == "Decimal" else value
