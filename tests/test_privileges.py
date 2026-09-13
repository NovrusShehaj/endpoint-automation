from __future__ import annotations

import os

import pytest

from endpointctl import privileges


def test_posix_root_is_elevated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(privileges.platform, "system", lambda: "Linux")
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    assert privileges.is_elevated() is True


def test_posix_non_root_is_not_elevated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(privileges.platform, "system", lambda: "Linux")
    monkeypatch.setattr(os, "geteuid", lambda: 1000, raising=False)
    assert privileges.is_elevated() is False


def test_missing_geteuid_is_undetermined(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(privileges.platform, "system", lambda: "Linux")
    monkeypatch.delattr(os, "geteuid", raising=False)
    assert privileges.is_elevated() is None


def test_windows_uses_the_shell32_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(privileges.platform, "system", lambda: "Windows")
    monkeypatch.setattr(privileges, "_windows_is_elevated", lambda: True)
    assert privileges.is_elevated() is True

    monkeypatch.setattr(privileges, "_windows_is_elevated", lambda: False)
    assert privileges.is_elevated() is False


def test_windows_never_falls_back_to_geteuid(monkeypatch: pytest.MonkeyPatch) -> None:
    """The old code skipped the check on Windows; an unavailable API must fail closed."""
    monkeypatch.setattr(privileges.platform, "system", lambda: "Windows")
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    assert privileges._windows_is_elevated() is None  # noqa: SLF001 - fail-closed guard
    assert privileges.is_elevated() is None


def test_elevation_reports_a_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(privileges, "is_elevated", lambda: None)
    elevated, detail = privileges.elevation()
    assert elevated is None
    assert "could not be determined" in detail
