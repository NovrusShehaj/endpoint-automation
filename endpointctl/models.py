"""Result schema shared by every scanner, renderer and exit-code decision.

Scanners return :class:`ScanResult` objects and never print. Presentation lives
in :mod:`endpointctl.reporting.render`, so the same result can be rendered as
Rich text or as JSON for automation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Any

__all__ = ["ExitCode", "ScanReport", "ScanResult", "Status"]


class Status(StrEnum):
    """Outcome of a single check.

    ``OK``/``INFO`` are healthy, ``UNSUPPORTED`` means the check cannot run on
    this platform (an honest "unknown", not a pass), ``WARNING`` is a finding an
    operator should act on, and ``ERROR`` means the check itself failed.
    """

    OK = "OK"
    INFO = "INFO"
    UNSUPPORTED = "UNSUPPORTED"
    WARNING = "WARNING"
    ERROR = "ERROR"

    @property
    def severity(self) -> int:
        """Ordering used to aggregate several results into one status."""
        return _SEVERITY[self]


#: Ordering for aggregation. ``INFO`` ranks below ``OK`` so a report that mixes
#: purely informational results with a real pass still reads as ``OK``; neither
#: affects the exit code.
_SEVERITY: dict[Status, int] = {
    Status.INFO: 0,
    Status.OK: 1,
    Status.UNSUPPORTED: 2,
    Status.WARNING: 3,
    Status.ERROR: 4,
}


class ExitCode(IntEnum):
    """Process exit contract. Documented in README and ``docs/operations.md``."""

    OK = 0
    USAGE = 1
    WARNING = 2
    ERROR = 3
    UNEXPECTED = 4


#: Aggregate status -> process exit code. ``UNSUPPORTED`` does not fail a run;
#: operators who require a check to be supported should gate on the JSON status.
_STATUS_EXIT_CODES: dict[Status, ExitCode] = {
    Status.OK: ExitCode.OK,
    Status.INFO: ExitCode.OK,
    Status.UNSUPPORTED: ExitCode.OK,
    Status.WARNING: ExitCode.WARNING,
    Status.ERROR: ExitCode.ERROR,
}


@dataclass(frozen=True)
class ScanResult:
    """One check's outcome.

    ``data`` holds machine-readable detail (never raw OS-tool output unless the
    operator asked for it with ``--verbose``); ``error`` is set only when the
    check could not be completed.
    """

    name: str
    status: Status
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "data": self.data,
            "error": self.error,
        }


@dataclass(frozen=True)
class ScanReport:
    """One invocation's results plus the aggregate status derived from them."""

    results: tuple[ScanResult, ...]

    @property
    def status(self) -> Status:
        """Worst status across all results; ``INFO`` when there are none."""
        if not self.results:
            return Status.INFO
        return max((r.status for r in self.results), key=lambda s: s.severity)

    @property
    def exit_code(self) -> ExitCode:
        return _STATUS_EXIT_CODES[self.status]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "results": [r.to_dict() for r in self.results],
        }
