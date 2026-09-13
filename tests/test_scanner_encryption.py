"""Encryption parsing, including the false-positive this release exists to fix."""

from __future__ import annotations

import pytest
from helpers import FakeToolResult

from endpointctl.config import default_config
from endpointctl.models import Status
from endpointctl.scanner import encryption as encryption_module
from endpointctl.scanner.encryption import (
    check_encryption,
    parse_fdesetup_status,
    parse_manage_bde_status,
)


def test_bitlocker_off_is_not_encrypted(fixture_text) -> None:
    """Regression lock: the old substring check reported this output as encrypted."""
    text = fixture_text("manage_bde_off.txt")
    assert "on" in text.lower()  # inside "Protection Off"/"Conversion"
    assert "encrypted" in text.lower()  # "Percentage Encrypted: 0.0%"

    state = parse_manage_bde_status(text)
    assert state.encrypted is False
    assert state.fields["percentage_encrypted"] == "0.0%"


def test_bitlocker_on_is_encrypted(fixture_text) -> None:
    state = parse_manage_bde_status(fixture_text("manage_bde_on.txt"))
    assert state.encrypted is True
    assert state.fields["conversion_status"] == "Fully Encrypted"


def test_suspended_bitlocker_is_not_encrypted(fixture_text) -> None:
    """Fully encrypted but unprotected: the key is not protected, so not compliant."""
    state = parse_manage_bde_status(fixture_text("manage_bde_suspended.txt"))
    assert state.encrypted is False


def test_unrecognised_bitlocker_output_is_unknown(fixture_text) -> None:
    state = parse_manage_bde_status(fixture_text("manage_bde_unrecognised.txt"))
    assert state.encrypted is None
    assert "Protection Status" in state.detail


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("fdesetup_on.txt", True),
        ("fdesetup_off.txt", False),
        ("fdesetup_in_progress.txt", True),
        ("fdesetup_deferred.txt", False),
        ("fdesetup_unrecognised.txt", None),
    ],
)
def test_filevault_parsing(fixture_text, name: str, expected: bool | None) -> None:
    assert parse_fdesetup_status(fixture_text(name)).encrypted is expected


def test_filevault_progress_is_captured(fixture_text) -> None:
    state = parse_fdesetup_status(fixture_text("fdesetup_in_progress.txt"))
    assert state.fields["percent_completed"] == "42"


def test_linux_is_unsupported_not_a_guess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(encryption_module.platform, "system", lambda: "Linux")
    result = check_encryption(default_config())
    assert result.status is Status.UNSUPPORTED
    assert result.data["detector"] is None
    assert "encrypted" not in result.data


def test_windows_scan_uses_status_only(monkeypatch: pytest.MonkeyPatch, fixture_text) -> None:
    calls: list[list[str]] = []

    def fake_run(argv, timeout):  # test double
        calls.append(list(argv))
        return FakeToolResult(stdout=fixture_text("manage_bde_off.txt"))

    monkeypatch.setattr(encryption_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(encryption_module, "run_os_tool", fake_run)

    result = check_encryption(default_config())
    assert calls == [["manage-bde", "-status", "C:"]]
    assert result.status is Status.WARNING
    assert result.data["encrypted"] is False
    assert "NOT active" in result.message


def test_windows_scan_reports_ok_when_protected(
    monkeypatch: pytest.MonkeyPatch, fixture_text
) -> None:
    monkeypatch.setattr(encryption_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        encryption_module,
        "run_os_tool",
        lambda argv, timeout: FakeToolResult(stdout=fixture_text("manage_bde_on.txt")),
    )
    result = check_encryption(default_config())
    assert result.status is Status.OK
    assert result.data["encrypted"] is True


@pytest.mark.parametrize(
    ("tool_result", "needle"),
    [
        (FakeToolResult(failure="not_found", returncode=None), "not available"),
        (FakeToolResult(failure="timeout", returncode=None), "timed out"),
        (FakeToolResult(returncode=1, stderr="Access is denied."), "exited with status 1"),
    ],
)
def test_tool_failures_are_errors_not_false_negatives(
    monkeypatch: pytest.MonkeyPatch, tool_result: FakeToolResult, needle: str
) -> None:
    monkeypatch.setattr(encryption_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(encryption_module, "run_os_tool", lambda argv, timeout: tool_result)

    result = check_encryption(default_config())
    assert result.status is Status.ERROR
    assert result.data["encrypted"] is None
    assert needle in (result.error or "")


def test_macos_scan(monkeypatch: pytest.MonkeyPatch, fixture_text) -> None:
    calls: list[list[str]] = []

    def fake_run(argv, timeout):  # test double
        calls.append(list(argv))
        return FakeToolResult(stdout=fixture_text("fdesetup_off.txt"))

    monkeypatch.setattr(encryption_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(encryption_module, "run_os_tool", fake_run)

    result = check_encryption(default_config())
    assert calls == [["fdesetup", "status"]]
    assert result.status is Status.WARNING
    assert result.data["encrypted"] is False


def test_scan_never_enables_encryption(monkeypatch: pytest.MonkeyPatch, fixture_text) -> None:
    """No scan path may pass an enabling verb to an OS tool."""
    seen: list[list[str]] = []

    def fake_run(argv, timeout):  # test double
        seen.append(list(argv))
        return FakeToolResult(stdout=fixture_text("manage_bde_on.txt"))

    monkeypatch.setattr(encryption_module.platform, "system", lambda: "Windows")
    monkeypatch.setattr(encryption_module, "run_os_tool", fake_run)
    check_encryption(default_config())

    flattened = [token.lower() for argv in seen for token in argv]
    assert "-on" not in flattened
    assert "enable" not in flattened
