"""Audit logging.

Importing this module has **no side effects**: no directories are created and no
handlers are installed until :func:`configure_logging` is called from
``cli.main``. Records are written as JSON lines to a rotating file so a fleet
tool cannot fill an endpoint's disk.

Raw output of full-disk-encryption tools is never logged - it can contain volume
identifiers and protector hints.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

__all__ = ["ROOT_LOGGER_NAME", "audit", "configure_logging", "get_logger"]

ROOT_LOGGER_NAME = "endpointctl"

#: ``logging.LogRecord`` attributes that are not caller-supplied context.
_RESERVED_RECORD_FIELDS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()
) | {"message", "asctime", "taskName"}


class JsonLinesFormatter(logging.Formatter):
    """Render a record as one JSON object per line, including ``extra`` fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _RESERVED_RECORD_FIELDS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=False)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the package logger (or a child of it). Never configures handlers."""
    if name is None or name == ROOT_LOGGER_NAME:
        return logging.getLogger(ROOT_LOGGER_NAME)
    suffix = name.split(".", 1)[1] if name.startswith(f"{ROOT_LOGGER_NAME}.") else name
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{suffix}")


def configure_logging(
    log_file: Path | None,
    *,
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
    stderr_level: int | None = None,
) -> Path | None:
    """Install handlers for this invocation.

    Returns the log file actually in use, or ``None`` when file logging was
    disabled or the destination is not writable. A failure to log never fails
    the scan: the reason is reported on stderr and the run continues.
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(min(level, stderr_level) if stderr_level is not None else level)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    if stderr_level is not None:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(stderr_level)
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(stream_handler)

    if log_file is None:
        logger.addHandler(logging.NullHandler())
        return None

    log_file = Path(log_file)

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
            delay=True,
        )
    except OSError as exc:
        logger.addHandler(logging.NullHandler())
        logger.warning("audit log disabled: %s", exc)
        return None

    file_handler.setLevel(level)
    file_handler.setFormatter(JsonLinesFormatter())
    logger.addHandler(file_handler)
    return log_file


def audit(message: str, **fields: Any) -> None:
    """Write one structured audit record for an invocation."""
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.info(message, extra={"audit": True, **fields})


def invocation_context(argv: list[str]) -> dict[str, Any]:
    """Identity and environment fields attached to every invocation record."""
    from endpointctl import __version__

    getuid = getattr(os, "getuid", None)
    geteuid = getattr(os, "geteuid", None)
    return {
        "version": __version__,
        "hostname": socket.gethostname(),
        "argv": argv,
        "pid": os.getpid(),
        "uid": getuid() if getuid is not None else None,
        "euid": geteuid() if geteuid is not None else None,
        "user": os.environ.get("USER") or os.environ.get("USERNAME"),
    }
