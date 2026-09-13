"""Experimental, preview-only remediation.

Nothing in this package changes host state in v1. The ``remediate`` command is
not registered on the default command line at all (see
``endpointctl.config.REMEDIATION_ENV_VAR``), and even when it is enabled the
only available mode is a dry-run preview.

Re-enabling an apply path is a new production review, not a toggle: it requires
recovery-key escrow for full-disk encryption, proof of elevation, return-code
handling and an audit record per action.
"""

from endpointctl.remediation.base import (
    RemediationDisabledError,
    RemediationError,
    confirm_action,
    require_admin,
)

__all__ = [
    "RemediationDisabledError",
    "RemediationError",
    "confirm_action",
    "require_admin",
]
