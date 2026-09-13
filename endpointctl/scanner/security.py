"""Endpoint security baseline: elevation and endpoint-protection presence.

Process matching is exact on the normalised process name (lower-cased, ``.exe``
stripped). The previous implementation joined every process name into one string
and searched for substrings such as ``sentinel``, which both missed real agents
and matched unrelated processes.

A single inaccessible process never fails the scan.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import psutil

from endpointctl.config import Config, default_config
from endpointctl.models import ScanResult, Status
from endpointctl.privileges import elevation

__all__ = ["check_security", "normalise_process_name"]


def normalise_process_name(name: str) -> str:
    normalised = name.strip().lower()
    return normalised[:-4] if normalised.endswith(".exe") else normalised


def check_security(config: Config | None = None) -> ScanResult:
    """Report elevation (informational) and endpoint-protection presence."""
    config = config or default_config()

    elevated, elevation_detail = elevation()
    findings: list[dict[str, Any]] = [
        {
            "check": "admin_privileges",
            "status": Status.INFO.value,
            "elevated": elevated,
            "detail": elevation_detail,
        }
    ]

    names, inaccessible = _running_process_names()
    expected = set(config.security.protection_processes)
    detected = sorted(names & expected)
    protection_status = Status.OK if detected else Status.WARNING

    findings.append(
        {
            "check": "endpoint_protection",
            "status": protection_status.value,
            "detected": bool(detected),
            "matched_processes": detected,
            "inspected_processes": len(names),
            "inaccessible_processes": inaccessible,
            "detail": (
                f"matched {', '.join(detected)}"
                if detected
                else "no configured endpoint-protection process is running"
            ),
        }
    )

    statuses = [Status(finding["status"]) for finding in findings]
    aggregate = max(statuses, key=lambda s: s.severity)
    return ScanResult(
        name="security_baseline",
        status=aggregate,
        message=(
            "endpoint protection detected"
            if detected
            else "no endpoint-protection process detected"
        ),
        data={"findings": findings},
    )


def _running_process_names(
    processes: Iterable[Any] | None = None,
) -> tuple[set[str], int]:
    """Normalised names of running processes, plus how many could not be read."""
    iterator = psutil.process_iter(["name"]) if processes is None else processes
    names: set[str] = set()
    inaccessible = 0
    for process in iterator:
        try:
            raw = process.info.get("name")
        except (psutil.Error, OSError, AttributeError):
            inaccessible += 1
            continue
        if not raw:
            inaccessible += 1
            continue
        names.add(normalise_process_name(raw))
    return names, inaccessible
