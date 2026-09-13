from __future__ import annotations

import pytest

from endpointctl.models import ExitCode, ScanReport, ScanResult, Status


def result(status: Status) -> ScanResult:
    return ScanResult(name="check", status=status)


def test_empty_report_is_info_and_exits_zero() -> None:
    report = ScanReport(results=())
    assert report.status is Status.INFO
    assert report.exit_code is ExitCode.OK


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ((Status.OK, Status.INFO), Status.OK),
        ((Status.OK, Status.UNSUPPORTED), Status.UNSUPPORTED),
        ((Status.UNSUPPORTED, Status.WARNING), Status.WARNING),
        ((Status.WARNING, Status.ERROR), Status.ERROR),
        ((Status.ERROR, Status.OK), Status.ERROR),
    ],
)
def test_aggregate_status_is_the_worst_result(
    statuses: tuple[Status, ...], expected: Status
) -> None:
    assert ScanReport(tuple(result(s) for s in statuses)).status is expected


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (Status.OK, ExitCode.OK),
        (Status.INFO, ExitCode.OK),
        (Status.UNSUPPORTED, ExitCode.OK),
        (Status.WARNING, ExitCode.WARNING),
        (Status.ERROR, ExitCode.ERROR),
    ],
)
def test_exit_code_contract(status: Status, code: ExitCode) -> None:
    assert ScanReport((result(status),)).exit_code is code


def test_result_dict_has_a_stable_key_set() -> None:
    payload = ScanResult(
        name="disk_usage", status=Status.WARNING, message="hi", data={"a": 1}
    ).to_dict()
    assert set(payload) == {"name", "status", "message", "data", "error"}
    assert payload["status"] == "WARNING"
    assert payload["error"] is None


def test_report_dict_contains_status_and_results() -> None:
    payload = ScanReport((result(Status.OK), result(Status.WARNING))).to_dict()
    assert payload["status"] == "WARNING"
    assert len(payload["results"]) == 2
