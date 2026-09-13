"""Disk-capacity check for the configured volumes.

Defaults are OS-correct (``/`` on POSIX, ``C:\\`` on Windows) and the warning
threshold comes from configuration, not from a literal in this function.
"""

from __future__ import annotations

from typing import Any

import psutil

from endpointctl.config import Config, default_config
from endpointctl.models import ScanResult, Status

__all__ = ["check_disk"]


def check_disk(config: Config | None = None) -> ScanResult:
    """Report usage per configured path; ``WARNING`` at or above the threshold."""
    config = config or default_config()
    threshold = config.disk.warning_threshold

    volumes: list[dict[str, Any]] = []
    statuses: list[Status] = []
    errors: list[str] = []

    for path in config.disk.paths:
        try:
            usage = psutil.disk_usage(path)
        except (OSError, psutil.Error) as exc:
            statuses.append(Status.ERROR)
            errors.append(f"{path}: {exc}")
            volumes.append({"mountpoint": path, "status": Status.ERROR.value, "error": str(exc)})
            continue

        status = Status.WARNING if usage.percent >= threshold else Status.OK
        statuses.append(status)
        volumes.append(
            {
                "mountpoint": path,
                "percent_used": round(usage.percent, 1),
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "warning_threshold_percent": threshold,
                "status": status.value,
            }
        )

    aggregate = max(statuses, key=lambda s: s.severity) if statuses else Status.ERROR
    return ScanResult(
        name="disk_usage",
        status=aggregate,
        message=_message(volumes, threshold),
        data={"warning_threshold_percent": threshold, "volumes": volumes},
        error="; ".join(errors) or None,
    )


def _message(volumes: list[dict[str, Any]], threshold: int) -> str:
    if not volumes:
        return "no volumes were inspected"
    parts = []
    for volume in volumes:
        percent = volume.get("percent_used")
        if percent is None:
            parts.append(f"{volume['mountpoint']}: unavailable")
        else:
            parts.append(f"{volume['mountpoint']}: {percent}% used")
    return f"threshold {threshold}% - " + ", ".join(parts)
