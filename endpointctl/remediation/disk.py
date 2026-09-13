"""Temporary-file cleanup - preview only.

The previous implementation deleted every child of ``/tmp`` and ``/var/tmp``
that it could, swallowed every failure, and reported a count that looked like
success. Nothing here deletes anything: :func:`plan_temp_cleanup` stats
candidates and returns a plan, and :func:`apply_temp_cleanup` refuses.

A future apply path must keep the age filter and the protected-name allowlist
below, resolve every candidate inside its root, and record one audit line per
removed item.
"""

from __future__ import annotations

import fnmatch
import os
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, NoReturn

from endpointctl.remediation.base import RemediationDisabledError

__all__ = [
    "DEFAULT_MIN_AGE_DAYS",
    "PROTECTED_NAME_PATTERNS",
    "apply_temp_cleanup",
    "default_temp_roots",
    "plan_temp_cleanup",
]

#: Items younger than this are never candidates: a running process is very
#: likely still using them.
DEFAULT_MIN_AGE_DAYS = 7

#: Names that are never candidates even when old. These are sockets and
#: per-service private directories whose removal breaks a running system.
PROTECTED_NAME_PATTERNS: tuple[str, ...] = (
    ".X*-unix",
    ".ICE-unix",
    ".font-unix",
    ".Test-unix",
    ".XIM-unix",
    "systemd-private-*",
    "snap-private-*",
    "snap.*",
    "tmux-*",
    "dbus-*",
    "ssh-*",
    "gnupg-*",
    "pulse-*",
    "krb5cc_*",
    ".nfs*",
)


def default_temp_roots() -> tuple[Path, ...]:
    """Temp directories for the running OS (Windows uses ``%TEMP%``)."""
    if os.name == "nt":
        return (Path(tempfile.gettempdir()),)
    return (Path("/tmp"), Path("/var/tmp"))  # noqa: S108 - these are the roots being previewed


def plan_temp_cleanup(
    roots: Iterable[Path] | None = None,
    *,
    min_age_days: int = DEFAULT_MIN_AGE_DAYS,
    now: float | None = None,
) -> dict[str, Any]:
    """Return the items an apply path *would* consider. Read-only (``stat`` only).

    Candidates are direct children of a temp root that are older than
    ``min_age_days``, are not symlinks, are not protected by name, and resolve
    inside their root.
    """
    if min_age_days < 1:
        raise ValueError("min_age_days must be at least 1")

    reference = time.time() if now is None else now
    cutoff = reference - min_age_days * 86400
    roots = tuple(roots) if roots is not None else default_temp_roots()

    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    inspected_roots: list[dict[str, Any]] = []

    for root in roots:
        if not root.is_dir():
            inspected_roots.append({"root": str(root), "present": False})
            continue
        inspected_roots.append({"root": str(root), "present": True})
        try:
            entries = sorted(root.iterdir())
        except OSError as exc:
            skipped.append({"path": str(root), "reason": f"unreadable: {exc}"})
            continue

        for entry in entries:
            reason = _skip_reason(entry, root, cutoff)
            if reason is not None:
                skipped.append({"path": str(entry), "reason": reason})
                continue
            candidates.append(
                {
                    "path": str(entry),
                    "kind": "directory" if entry.is_dir() else "file",
                    "size_bytes": _size_of(entry),
                    "age_days": round((reference - entry.stat().st_mtime) / 86400, 1),
                }
            )

    return {
        "action": "cleanup_temp",
        "mode": "preview",
        "applied": False,
        "min_age_days": min_age_days,
        "roots": inspected_roots,
        "candidate_count": len(candidates),
        "reclaimable_bytes": sum(int(c["size_bytes"]) for c in candidates),
        "candidates": candidates,
        "skipped_count": len(skipped),
        "skipped": skipped,
    }


def apply_temp_cleanup(*_args: Any, **_kwargs: Any) -> NoReturn:
    """Always refuses: there is no destructive path in this release."""
    raise RemediationDisabledError(
        "temporary-file deletion is disabled in this release; "
        "'remediate disk' only produces a preview plan"
    )


def _skip_reason(entry: Path, root: Path, cutoff: float) -> str | None:
    name = entry.name
    for pattern in PROTECTED_NAME_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return f"protected name (matches {pattern})"
    if entry.is_symlink():
        return "symlink"
    try:
        stat_result = entry.stat()
    except OSError as exc:
        return f"unreadable: {exc}"
    if not (entry.is_file() or entry.is_dir()):
        return "not a regular file or directory"
    if stat_result.st_mtime > cutoff:
        return "newer than the minimum age"
    try:
        resolved = entry.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return "does not resolve inside the temp root"
    return None


def _size_of(entry: Path) -> int:
    try:
        if entry.is_file():
            return entry.stat().st_size
    except OSError:
        return 0

    total = 0
    for dirpath, _dirnames, filenames in os.walk(entry, onerror=lambda _exc: None):
        for filename in filenames:
            try:
                file_path = Path(dirpath) / filename
                if not file_path.is_symlink():
                    total += file_path.stat().st_size
            except OSError:
                continue
    return total
