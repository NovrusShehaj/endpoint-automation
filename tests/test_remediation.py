"""Remediation is preview-only. No test may exercise a destructive path."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from endpointctl import privileges
from endpointctl.remediation import base as base_module
from endpointctl.remediation.base import (
    RemediationDisabledError,
    RemediationError,
    confirm_action,
    require_admin,
)
from endpointctl.remediation.disk import (
    DEFAULT_MIN_AGE_DAYS,
    apply_temp_cleanup,
    default_temp_roots,
    plan_temp_cleanup,
)
from endpointctl.remediation.encryption import enable_encryption, plan_encryption_remediation

OLD = time.time() - 30 * 86400


def age(path: Path, when: float = OLD) -> Path:
    os.utime(path, (when, when))
    return path


def test_require_admin_passes_when_elevated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base_module, "elevation", lambda: (True, "root"))
    require_admin()


def test_require_admin_rejects_unelevated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base_module, "elevation", lambda: (False, "uid 1000"))
    with pytest.raises(RemediationError, match="administrator privileges required"):
        require_admin()


def test_require_admin_fails_closed_when_undetermined(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base_module, "elevation", lambda: (None, "unknown"))
    with pytest.raises(RemediationError, match="could not be verified"):
        require_admin()


def test_windows_non_admin_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The old require_admin returned early on Windows and checked nothing."""
    monkeypatch.setattr(privileges.platform, "system", lambda: "Windows")
    monkeypatch.setattr(privileges, "_windows_is_elevated", lambda: False)
    with pytest.raises(RemediationError):
        require_admin()


def test_confirm_action_accepts_only_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "  YES ")
    confirm_action("proceed?")


@pytest.mark.parametrize("answer", ["no", "y", "", "yes please"])
def test_confirm_action_rejects_anything_else(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: answer)
    with pytest.raises(RemediationError, match="cancelled"):
        confirm_action("proceed?")


def test_confirm_action_on_non_interactive_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    with pytest.raises(RemediationError, match="not interactive"):
        confirm_action("proceed?")


def test_confirm_action_assume_yes_skips_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_prompt: str) -> str:
        raise AssertionError("stdin must not be read")

    monkeypatch.setattr("builtins.input", fail)
    confirm_action("proceed?", assume_yes=True)


def test_apply_paths_are_disabled() -> None:
    with pytest.raises(RemediationDisabledError):
        apply_temp_cleanup()
    with pytest.raises(RemediationDisabledError, match="recovery-key escrow"):
        enable_encryption()


def test_encryption_preview_runs_no_os_tool() -> None:
    plan = plan_encryption_remediation()
    assert plan["applied"] is False
    assert plan["supported"] is False
    assert "recommended_path" in plan


def test_default_temp_roots_are_os_appropriate() -> None:
    roots = default_temp_roots()
    assert roots
    assert all(root.is_absolute() for root in roots)


def test_plan_lists_old_items_and_deletes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "tmp"
    root.mkdir()
    old_file = root / "old.log"
    old_file.write_text("x" * 10)
    age(old_file)
    old_dir = root / "olddir"
    old_dir.mkdir()
    (old_dir / "inner.bin").write_bytes(b"y" * 20)
    age(old_dir)

    plan = plan_temp_cleanup([root])

    assert plan["applied"] is False
    assert plan["mode"] == "preview"
    assert plan["candidate_count"] == 2
    assert plan["reclaimable_bytes"] == 30
    assert old_file.exists() and old_dir.exists()


def test_plan_skips_recent_items(tmp_path: Path) -> None:
    root = tmp_path / "tmp"
    root.mkdir()
    (root / "fresh.txt").write_text("new")

    plan = plan_temp_cleanup([root])
    assert plan["candidate_count"] == 0
    assert plan["skipped"][0]["reason"] == "newer than the minimum age"


def test_plan_skips_protected_names(tmp_path: Path) -> None:
    root = tmp_path / "tmp"
    root.mkdir()
    for name in (".X11-unix", "systemd-private-abc", "ssh-XYZ"):
        target = root / name
        target.mkdir()
        age(target)

    plan = plan_temp_cleanup([root])
    assert plan["candidate_count"] == 0
    assert all("protected name" in item["reason"] for item in plan["skipped"])


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation needs privileges on Windows")
def test_plan_skips_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "tmp"
    root.mkdir()
    outside = tmp_path / "important.txt"
    outside.write_text("do not touch")
    link = root / "link"
    link.symlink_to(outside)
    os.utime(link, (OLD, OLD), follow_symlinks=False)

    plan = plan_temp_cleanup([root])
    assert plan["candidate_count"] == 0
    assert plan["skipped"][0]["reason"] == "symlink"
    assert outside.read_text() == "do not touch"


def test_plan_reports_absent_roots(tmp_path: Path) -> None:
    plan = plan_temp_cleanup([tmp_path / "missing"])
    assert plan["roots"][0]["present"] is False
    assert plan["candidate_count"] == 0


def test_plan_rejects_a_zero_age_filter(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        plan_temp_cleanup([tmp_path], min_age_days=0)


def test_default_age_filter_is_conservative() -> None:
    assert DEFAULT_MIN_AGE_DAYS >= 7
