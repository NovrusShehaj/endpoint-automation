"""Single elevation check shared by the security scanner and remediation preflight.

The check fails closed: when elevation cannot be determined (no Windows API, no
``geteuid``) the result is ``None``, which callers must not treat as elevated.
"""

from __future__ import annotations

import os
import platform

__all__ = ["elevation", "is_elevated"]


def is_elevated() -> bool | None:
    """``True`` if the current process is elevated, ``False`` if not, ``None`` if unknown."""
    if platform.system() == "Windows":
        return _windows_is_elevated()
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None:
        return None
    try:
        return geteuid() == 0
    except OSError:
        return None


def elevation() -> tuple[bool | None, str]:
    """:func:`is_elevated` plus a human-readable explanation for reports and logs."""
    elevated = is_elevated()
    if elevated is True:
        return True, "process is running with administrative privileges"
    if elevated is False:
        return False, "process is not running with administrative privileges"
    return None, "elevation could not be determined on this platform"


def _windows_is_elevated() -> bool | None:
    try:
        import ctypes

        shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
        return bool(shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001 # pragma: no cover - must fail closed, not crash
        # No Windows API available, or the call failed: fail closed.
        return None
