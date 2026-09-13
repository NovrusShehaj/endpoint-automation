"""The only sanctioned way to run an operating-system tool.

Every call is argv-based (never ``shell=True``), always has a timeout, and never
raises for a failing tool: the caller inspects :class:`ToolResult` and decides.
A test asserts that no other module calls :func:`subprocess.run` directly.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

from endpointctl.reporting.logger import get_logger

__all__ = ["ToolResult", "run_os_tool"]

logger = get_logger(__name__)


@dataclass(frozen=True)
class ToolResult:
    """Outcome of one OS-tool invocation.

    ``failure`` is ``None`` when the tool ran to completion (even with a
    non-zero ``returncode``); otherwise it is ``not_found``, ``timeout`` or
    ``os_error``.
    """

    argv: tuple[str, ...]
    returncode: int | None
    stdout: str
    stderr: str
    failure: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.failure is None and self.returncode == 0

    @property
    def command(self) -> str:
        return " ".join(self.argv)


def run_os_tool(argv: Sequence[str], timeout: float) -> ToolResult:
    """Run ``argv`` with a hard timeout and capture its output.

    Raises :class:`ValueError` for an empty argv or a non-positive timeout -
    both are programming errors rather than host conditions.
    """
    command = tuple(argv)
    if not command:
        raise ValueError("argv must not be empty")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    logger.debug("running os tool", extra={"argv": list(command), "timeout": timeout})

    try:
        completed = subprocess.run(  # fixed argv, never shell=True
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except FileNotFoundError as exc:
        return ToolResult(command, None, "", "", "not_found", str(exc))
    except PermissionError as exc:
        return ToolResult(command, None, "", "", "os_error", str(exc))
    except subprocess.TimeoutExpired as exc:
        return ToolResult(command, None, "", "", "timeout", f"timed out after {timeout:g}s: {exc}")
    except OSError as exc:
        return ToolResult(command, None, "", "", "os_error", str(exc))

    return ToolResult(
        argv=command,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
