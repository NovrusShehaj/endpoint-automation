"""Scanner registry.

A new read-only check is added by writing a function that takes a
:class:`~endpointctl.config.Config` and returns a
:class:`~endpointctl.models.ScanResult`, then registering it here. The CLI reads
its choices from :data:`SCAN_TARGETS`, so no argparse edits are needed.
"""

from __future__ import annotations

from collections.abc import Callable

from endpointctl.config import Config
from endpointctl.models import ScanReport, ScanResult, Status
from endpointctl.scanner.disk import check_disk
from endpointctl.scanner.encryption import check_encryption
from endpointctl.scanner.os_info import check_os
from endpointctl.scanner.security import check_security

__all__ = [
    "ALL_TARGET",
    "SCANNERS",
    "SCAN_TARGETS",
    "check_disk",
    "check_encryption",
    "check_os",
    "check_security",
    "run_scan",
]

ALL_TARGET = "all"

#: Ordered so ``scan all`` reads host identity first.
SCANNERS: dict[str, Callable[[Config], ScanResult]] = {
    "os": check_os,
    "disk": check_disk,
    "encryption": check_encryption,
    "security": check_security,
}

SCAN_TARGETS: tuple[str, ...] = (*SCANNERS, ALL_TARGET)


def run_scan(target: str, config: Config) -> ScanReport:
    """Run one scanner, or every scanner for ``all``.

    ``all`` is best-effort: one failing scanner does not hide the others, but it
    does raise the aggregate status (and therefore the exit code).
    """
    if target == ALL_TARGET:
        names = list(SCANNERS)
    elif target in SCANNERS:
        names = [target]
    else:
        raise KeyError(f"unknown scan target: {target}")

    return ScanReport(results=tuple(_safe_run(name, config) for name in names))


def _safe_run(name: str, config: Config) -> ScanResult:
    try:
        return SCANNERS[name](config)
    except Exception as exc:  # noqa: BLE001 - one bad scanner must not hide the rest
        return ScanResult(
            name=name,
            status=Status.ERROR,
            message=f"scanner '{name}' failed",
            error=f"{type(exc).__name__}: {exc}",
        )
