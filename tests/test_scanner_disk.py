from __future__ import annotations

from collections import namedtuple

import psutil
import pytest

from endpointctl.config import DiskConfig, default_config
from endpointctl.models import Status
from endpointctl.scanner import disk as disk_module
from endpointctl.scanner.disk import check_disk

Usage = namedtuple("Usage", "total used free percent")


def config_with(paths: tuple[str, ...] = ("/",), threshold: int = 85):
    base = default_config()
    return type(base)(
        disk=DiskConfig(paths=paths, warning_threshold=threshold),
        encryption=base.encryption,
        security=base.security,
        process=base.process,
        logging=base.logging,
        remediation=base.remediation,
    )


def fake_usage(percent: float):
    def _usage(_path: str) -> Usage:
        return Usage(total=1000, used=int(10 * percent), free=100, percent=percent)

    return _usage


def test_below_threshold_is_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(disk_module.psutil, "disk_usage", fake_usage(42.0))
    result = check_disk(config_with())
    assert result.status is Status.OK
    volume = result.data["volumes"][0]
    assert volume["percent_used"] == 42.0
    assert set(volume) >= {"mountpoint", "total_bytes", "used_bytes", "free_bytes"}


def test_at_threshold_is_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(disk_module.psutil, "disk_usage", fake_usage(85.0))
    assert check_disk(config_with()).status is Status.WARNING


def test_threshold_comes_from_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(disk_module.psutil, "disk_usage", fake_usage(50.0))
    assert check_disk(config_with(threshold=40)).status is Status.WARNING
    assert check_disk(config_with(threshold=60)).status is Status.OK


def test_windows_default_path_is_not_root(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def record(path: str) -> Usage:
        seen.append(path)
        return Usage(total=1, used=0, free=1, percent=1.0)

    monkeypatch.setattr(disk_module.psutil, "disk_usage", record)
    check_disk(config_with(paths=("C:\\",)))
    assert seen == ["C:\\"]


def test_unreadable_path_is_an_error_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_path: str) -> Usage:
        raise OSError("no such volume")

    monkeypatch.setattr(disk_module.psutil, "disk_usage", boom)
    result = check_disk(config_with(paths=("/missing",)))
    assert result.status is Status.ERROR
    assert "no such volume" in (result.error or "")


def test_psutil_error_is_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_path: str) -> Usage:
        raise psutil.Error("psutil failed")

    monkeypatch.setattr(disk_module.psutil, "disk_usage", boom)
    assert check_disk(config_with()).status is Status.ERROR


def test_worst_volume_decides_the_status(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {"/": 10.0, "/data": 99.0}
    monkeypatch.setattr(
        disk_module.psutil,
        "disk_usage",
        lambda path: Usage(total=1000, used=1, free=1, percent=values[path]),
    )
    result = check_disk(config_with(paths=("/", "/data")))
    assert result.status is Status.WARNING
    assert len(result.data["volumes"]) == 2


def test_scanner_does_not_print(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(disk_module.psutil, "disk_usage", fake_usage(10.0))
    check_disk(config_with())
    assert capsys.readouterr().out == ""
