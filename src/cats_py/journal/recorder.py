from __future__ import annotations

from typing import Any

from cats_py.infra.storage import JsonlStorage, json_ready


class JournalRecorder:
    def __init__(self, storage: JsonlStorage) -> None:
        self.storage = storage

    def record(self, stream: str, payload: Any) -> None:
        if isinstance(payload, dict):
            self.storage.append(stream, payload)
            return
        self.storage.append(stream, {"payload": json_ready(payload)})
