from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, TextIO, cast


_RESERVED_RECORD_FIELDS = {
    "args",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


def _serialize_log_value(value: Any) -> Any:
    if is_dataclass(value):
        return _serialize_log_value(asdict(cast(Any, value)))
    if isinstance(value, dict):
        return {str(key): _serialize_log_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_log_value(item) for item in value]
    if hasattr(value, "value") and hasattr(value, "name"):
        return getattr(value, "value")
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:  # noqa: BLE001
            return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_FIELDS or key.startswith("_"):
                continue
            payload[key] = _serialize_log_value(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = record.stack_info

        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class JsonStreamHandler(logging.StreamHandler[TextIO]):
    pass


def configure_logging(service: str, log_level: str = "INFO") -> logging.Logger:
    root = logging.getLogger()
    has_json_handler = any(isinstance(handler, JsonStreamHandler) for handler in root.handlers)
    if not has_json_handler:
        handler = JsonStreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        root.handlers = [handler]

    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logger = logging.getLogger(service)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    return logger
