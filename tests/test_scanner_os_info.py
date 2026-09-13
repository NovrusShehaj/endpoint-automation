from __future__ import annotations

from endpointctl.config import default_config
from endpointctl.models import Status
from endpointctl.scanner.os_info import check_os


def test_os_scan_returns_data_instead_of_printing(capsys) -> None:
    result = check_os(default_config())
    assert capsys.readouterr().out == ""
    assert result.status is Status.INFO
    assert set(result.data) >= {"hostname", "os", "os_version", "architecture"}
    assert result.data["hostname"]


def test_os_scan_works_without_a_config() -> None:
    assert check_os().name == "os_info"
