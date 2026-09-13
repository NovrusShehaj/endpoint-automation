"""Preflight controls shared by any future remediation.

These helpers are kept (and tested) so that a reviewed apply path can be built
on them later. They are deliberately strict: elevation that cannot be proven is
treated as "not elevated", and a non-interactive stdin is a refusal rather than
an unhandled ``EOFError``.
"""

from __future__ import annotations

from endpointctl.privileges import elevation

__all__ = [
    "RemediationDisabledError",
    "RemediationError",
    "confirm_action",
    "require_admin",
]


class RemediationError(Exception):
    """A remediation could not run: cancelled, unsupported, or not permitted."""


class RemediationDisabledError(RemediationError):
    """The requested remediation is switched off in this release."""


def require_admin() -> None:
    """Raise unless the process is *provably* elevated.

    Windows is checked with ``IsUserAnAdmin`` rather than being skipped, and an
    undeterminable result fails closed.
    """
    elevated, detail = elevation()
    if elevated is True:
        return
    if elevated is False:
        raise RemediationError(f"administrator privileges required: {detail}")
    raise RemediationError(
        f"administrator privileges could not be verified, refusing to continue: {detail}"
    )


def confirm_action(message: str, *, assume_yes: bool = False) -> None:
    """Require a literal ``yes`` on an interactive terminal.

    ``assume_yes`` exists for tests and for a future non-interactive approval
    flow; it is not wired to a CLI flag while no apply path exists.
    """
    if assume_yes:
        return
    try:
        response = input(f"{message} (yes/no): ")
    except EOFError as exc:
        raise RemediationError("confirmation required but stdin is not interactive") from exc
    except KeyboardInterrupt as exc:
        raise RemediationError("remediation cancelled by user") from exc

    if response.strip().lower() != "yes":
        raise RemediationError("remediation cancelled by user")
