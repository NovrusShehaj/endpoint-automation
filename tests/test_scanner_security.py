from __future__ import annotations

import psutil
import pytest
from helpers import FakeProcess

from endpointctl.config import SecurityConfig, default_config
from endpointctl.models import Status
from endpointctl.scanner import security as security_module
from endpointctl.scanner.security import check_security, normalise_process_name


def config_with(processes: tuple[str, ...]):
    base = default_config()
    return type(base)(
        disk=base.disk,
        encryption=base.encryption,
        security=SecurityConfig(protection_processes=processes),
        process=base.process,
        logging=base.logging,
        remediation=base.remediation,
    )


def use_processes(monkeypatch: pytest.MonkeyPatch, processes: list[FakeProcess]) -> None:
    monkeypatch.setattr(security_module.psutil, "process_iter", lambda attrs: iter(processes))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("MsMpEng.EXE", "msmpeng"), (" falcond ", "falcond"), ("clamd", "clamd")],
)
def test_name_normalisation(raw: str, expected: str) -> None:
    assert normalise_process_name(raw) == expected


def test_detects_an_exact_agent_name(monkeypatch: pytest.MonkeyPatch) -> None:
    use_processes(monkeypatch, [FakeProcess("bash"), FakeProcess("MsMpEng.exe")])
    result = check_security(config_with(("msmpeng",)))
    finding = result.data["findings"][1]
    assert finding["detected"] is True
    assert finding["matched_processes"] == ["msmpeng"]
    assert result.status is Status.OK


def test_substring_matches_are_not_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """`sentinel-worker` is not SentinelOne; the old blob match claimed it was."""
    use_processes(monkeypatch, [FakeProcess("sentinel-worker"), FakeProcess("falcon-tui")])
    result = check_security(config_with(("sentinelagent", "falcond")))
    assert result.data["findings"][1]["detected"] is False
    assert result.status is Status.WARNING


def test_missing_agent_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    use_processes(monkeypatch, [FakeProcess("bash")])
    assert check_security(config_with(("msmpeng",))).status is Status.WARNING


def test_access_denied_on_one_process_does_not_fail_the_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_processes(
        monkeypatch,
        [
            FakeProcess(raises=psutil.AccessDenied(pid=1)),
            FakeProcess(raises=psutil.ZombieProcess(pid=2)),
            FakeProcess(raises=psutil.NoSuchProcess(pid=3)),
            FakeProcess("clamd"),
        ],
    )
    result = check_security(config_with(("clamd",)))
    finding = result.data["findings"][1]
    assert finding["detected"] is True
    assert finding["inaccessible_processes"] == 3
    assert finding["inspected_processes"] == 1


def test_process_with_no_name_counts_as_inaccessible(monkeypatch: pytest.MonkeyPatch) -> None:
    use_processes(monkeypatch, [FakeProcess(None)])
    assert (
        check_security(config_with(("clamd",))).data["findings"][1]["inaccessible_processes"] == 1
    )


@pytest.mark.parametrize("elevated", [True, False, None])
def test_admin_finding_uses_the_shared_helper(
    monkeypatch: pytest.MonkeyPatch, elevated: bool | None
) -> None:
    use_processes(monkeypatch, [FakeProcess("clamd")])
    monkeypatch.setattr(
        security_module, "elevation", lambda: (elevated, "detail from shared helper")
    )
    finding = check_security(config_with(("clamd",))).data["findings"][0]
    assert finding["check"] == "admin_privileges"
    assert finding["elevated"] is elevated
    assert finding["status"] == Status.INFO.value


def test_scanner_does_not_print(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    use_processes(monkeypatch, [FakeProcess("clamd")])
    check_security(config_with(("clamd",)))
    assert capsys.readouterr().out == ""
