from __future__ import annotations

import json
from pathlib import Path

import pytest

from endpointctl import __version__
from endpointctl.cli import build_parser, main
from endpointctl.models import ExitCode, ScanResult, Status
from endpointctl.scanner import SCANNERS


@pytest.fixture
def stub_scanners(monkeypatch: pytest.MonkeyPatch):
    """Replace every scanner so the CLI tests never touch the real host."""

    def _install(status: Status = Status.OK) -> None:
        for key in SCANNERS:
            monkeypatch.setitem(
                SCANNERS,
                key,
                lambda config, key=key: ScanResult(
                    name=key, status=status, message=f"{key} ran", data={"key": key}
                ),
            )

    return _install


def test_bare_invocation_prints_help_and_fails(capsys) -> None:
    assert main([]) == ExitCode.USAGE
    assert "usage: endpointctl" in capsys.readouterr().out


def test_subcommand_is_required(capsys) -> None:
    assert main(["--json"]) == ExitCode.USAGE
    assert "error" in capsys.readouterr().err


def test_unknown_scan_target_is_a_usage_error(capsys) -> None:
    assert main(["scan", "teapot"]) == ExitCode.USAGE
    assert "invalid choice" in capsys.readouterr().err


def test_version_flag(capsys) -> None:
    assert main(["--version"]) == ExitCode.OK
    assert __version__ in capsys.readouterr().out


def test_help_exits_zero(capsys) -> None:
    assert main(["--help"]) == ExitCode.OK
    assert "Exit codes" in capsys.readouterr().out


def test_scan_ok_exits_zero(stub_scanners, capsys) -> None:
    stub_scanners(Status.OK)
    assert main(["scan", "disk", "--no-log"]) == ExitCode.OK
    assert "OK" in capsys.readouterr().out


def test_warning_findings_change_the_exit_code(stub_scanners) -> None:
    stub_scanners(Status.WARNING)
    assert main(["scan", "disk", "--no-log"]) == ExitCode.WARNING


def test_error_findings_exit_three(stub_scanners) -> None:
    stub_scanners(Status.ERROR)
    assert main(["scan", "all", "--no-log"]) == ExitCode.ERROR


def test_unsupported_does_not_fail_the_run(stub_scanners) -> None:
    stub_scanners(Status.UNSUPPORTED)
    assert main(["scan", "encryption", "--no-log"]) == ExitCode.OK


def test_json_output_is_one_object(stub_scanners, capsys) -> None:
    stub_scanners(Status.OK)
    assert main(["--json", "scan", "all", "--no-log"]) == ExitCode.OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["tool"] == "endpointctl"
    assert payload["version"] == __version__
    assert payload["status"] == "OK"
    assert [r["name"] for r in payload["results"]] == ["os", "disk", "encryption", "security"]
    assert set(payload["results"][0]) == {"name", "status", "message", "data", "error"}


def test_os_is_a_first_class_scan_target(capsys) -> None:
    assert main(["--json", "scan", "os", "--no-log"]) == ExitCode.OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["results"][0]["name"] == "os_info"


def test_invalid_configuration_fails_startup(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("[disk]\nwarning_threshold = 250\n")
    assert main(["--config", str(bad), "scan", "disk"]) == ExitCode.USAGE
    assert "configuration error" in capsys.readouterr().err


def test_unexpected_failure_exits_four(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("kaboom")

    monkeypatch.setattr("endpointctl.cli.run_scan", boom)
    assert main(["scan", "disk", "--no-log"]) == ExitCode.UNEXPECTED
    assert "unexpected failure" in capsys.readouterr().err


def test_keyboard_interrupt_is_not_a_traceback(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def interrupt(*_args: object, **_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("endpointctl.cli.run_scan", interrupt)
    assert main(["scan", "disk", "--no-log"]) == ExitCode.USAGE
    assert "interrupted" in capsys.readouterr().err


def test_quiet_suppresses_human_output(stub_scanners, capsys) -> None:
    stub_scanners(Status.OK)
    main(["--quiet", "scan", "disk", "--no-log"])
    assert capsys.readouterr().out == ""


# --- remediation gate -------------------------------------------------------


def test_default_parser_has_no_remediate_command() -> None:
    parser = build_parser(remediation=False)
    subparsers = next(
        action
        for action in parser._subparsers._group_actions  # noqa: SLF001
    )
    assert "remediate" not in subparsers.choices
    assert "scan" in subparsers.choices


def test_remediate_is_rejected_without_the_environment_flag(capsys) -> None:
    assert main(["remediate", "disk"]) == ExitCode.USAGE
    assert "invalid choice" in capsys.readouterr().err


def test_remediate_appears_only_with_the_environment_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENDPOINTCTL_ENABLE_REMEDIATION", "1")
    parser = build_parser(remediation=True)
    subparsers = next(
        action
        for action in parser._subparsers._group_actions  # noqa: SLF001
    )
    assert "remediate" in subparsers.choices


def test_remediate_disk_is_preview_only(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("ENDPOINTCTL_ENABLE_REMEDIATION", "1")
    monkeypatch.setattr(
        "endpointctl.remediation.disk.default_temp_roots", lambda: (Path("/nonexistent-root"),)
    )
    assert main(["--json", "remediate", "disk", "--no-log"]) == ExitCode.OK
    payload = json.loads(capsys.readouterr().out)
    data = payload["results"][0]["data"]
    assert data["applied"] is False
    assert data["mode"] == "preview"


def test_remediate_disk_apply_is_refused(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("ENDPOINTCTL_ENABLE_REMEDIATION", "1")
    assert main(["--json", "remediate", "disk", "--apply", "--no-log"]) == ExitCode.USAGE
    payload = json.loads(capsys.readouterr().out)
    assert payload["results"][0]["status"] == "UNSUPPORTED"
    assert "disabled" in payload["results"][0]["error"]


def test_remediate_encryption_is_refused_with_guidance(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("ENDPOINTCTL_ENABLE_REMEDIATION", "1")
    assert main(["--json", "remediate", "encryption", "--no-log"]) == ExitCode.USAGE
    payload = json.loads(capsys.readouterr().out)
    result = payload["results"][0]
    assert result["data"]["applied"] is False
    assert "recovery-key escrow" in result["error"]


def test_scan_never_imports_remediation(stub_scanners) -> None:
    """A scan must not load state-changing code."""
    import subprocess
    import sys

    stub_scanners(Status.OK)
    code = (
        "import sys; from endpointctl.cli import main;"
        " main(['scan','os','--no-log']);"
        " sys.exit(1 if 'endpointctl.remediation.disk' in sys.modules else 0)"
    )
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
