"""Structured JSON logger.

A single configured logger is used across the application. Every log line
is JSON with a fixed envelope so it can be shipped to a SIEM/log pipeline
without further parsing.

Never log secrets. Callers must run payloads through
`app.security.sanitizer.redact_secrets` before including them in `extra`.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any


_RESERVED = {
    "args",
    "asctime",
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
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
                  + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Merge user-supplied extras.
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            if key in payload:
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = repr(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once. Safe to call repeatedly."""
    global _configured
    root = logging.getLogger()
    root.setLevel(level.upper())

    # Remove any pre-existing handlers to avoid duplicate output.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(JsonFormatter())
    root.addHandler(stream)

    # Tame noisy third-party loggers.
    for name in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(name).setLevel("WARNING")

    _configured = True


def get_logger(name: str) -> logging.Logger:
    if not _configured:
        configure_logging()
    return logging.getLogger(name)