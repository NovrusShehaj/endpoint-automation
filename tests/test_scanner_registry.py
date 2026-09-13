from __future__ import annotations

import pytest

from endpointctl.config import default_config
from endpointctl.models import ScanResult, Status
from endpointctl.scanner import SCAN_TARGETS, SCANNERS, run_scan


def test_targets_include_os_as_a_first_class_scan() -> None:
    assert "os" in SCANNERS
    assert SCAN_TARGETS == ("os", "disk", "encryption", "security", "all")


def test_single_target_runs_one_scanner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        SCANNERS, "disk", lambda config: ScanResult(name="disk_usage", status=Status.OK)
    )
    report = run_scan("disk", default_config())
    assert [r.name for r in report.results] == ["disk_usage"]


def test_all_runs_every_scanner_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in SCANNERS:
        monkeypatch.setitem(
            SCANNERS, key, lambda config, key=key: ScanResult(name=key, status=Status.OK)
        )
    report = run_scan("all", default_config())
    assert [r.name for r in report.results] == ["os", "disk", "encryption", "security"]


def test_all_is_best_effort_when_one_scanner_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_config: object) -> ScanResult:
        raise RuntimeError("scanner exploded")

    for key in SCANNERS:
        monkeypatch.setitem(
            SCANNERS, key, lambda config, key=key: ScanResult(name=key, status=Status.OK)
        )
    monkeypatch.setitem(SCANNERS, "encryption", boom)

    report = run_scan("all", default_config())
    assert len(report.results) == 4
    failed = next(r for r in report.results if r.name == "encryption")
    assert failed.status is Status.ERROR
    assert "scanner exploded" in (failed.error or "")
    assert report.status is Status.ERROR


def test_unknown_target_raises() -> None:
    with pytest.raises(KeyError):
        run_scan("nope", default_config())
