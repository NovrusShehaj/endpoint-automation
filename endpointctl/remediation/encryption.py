"""Full-disk-encryption enablement - out of scope for v1.

``manage-bde -on`` and ``fdesetup enable`` are not called from this tool. There
is no rollback for either one: a host that ends up encrypted without its
recovery key escrowed is a data-loss event. Enabling full-disk encryption from
a self-service CLI requires, at minimum, a written key-escrow design, proof of
elevation, return-code handling and an audit record.

The unsupported-platform branch here also used to reference a non-existent
``RunTimeError``, so Linux raised ``NameError`` instead of a controlled error.
"""

from __future__ import annotations

import platform
from typing import Any, NoReturn

from endpointctl.remediation.base import RemediationDisabledError

__all__ = ["enable_encryption", "plan_encryption_remediation"]

_ESCROW_NOTICE = (
    "enabling full-disk encryption is not available in this release: it requires "
    "recovery-key escrow, proof of elevation and a documented rollback plan. "
    "Use the platform's managed encryption workflow (Intune/Jamf/MDM) instead."
)


def enable_encryption(*_args: Any, **_kwargs: Any) -> NoReturn:
    """Always refuses. Kept so the refusal is explicit, typed and testable."""
    raise RemediationDisabledError(_ESCROW_NOTICE)


def plan_encryption_remediation() -> dict[str, Any]:
    """Describe what an operator should do instead. Runs no OS tool."""
    os_name = platform.system()
    managed_tool = {
        "Windows": "BitLocker via Intune/Configuration Manager with recovery keys in Entra ID",
        "Darwin": "FileVault via Jamf/Intune with escrowed personal recovery keys",
    }.get(os_name, "the platform's managed disk-encryption workflow")

    return {
        "action": "enable_encryption",
        "mode": "preview",
        "applied": False,
        "supported": False,
        "platform": os_name,
        "reason": _ESCROW_NOTICE,
        "recommended_path": managed_tool,
        "next_step": "run 'endpointctl scan encryption' to confirm the current state",
    }
