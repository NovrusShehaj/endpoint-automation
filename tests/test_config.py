from __future__ import annotations

from pathlib import Path

import pytest

from endpointctl import config as config_module
from endpointctl.config import ConfigError, default_config, load_config, remediation_enabled


def write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "endpointctl.toml"
    path.write_text(body, encoding="utf-8")
    return path


def test_defaults_are_os_correct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_module.os, "name", "posix")
    assert config_module.default_disk_paths() == ("/",)
    monkeypatch.setattr(config_module.os, "name", "nt")
    assert config_module.default_disk_paths() == ("C:\\",)


def test_default_threshold_preserved() -> None:
    assert default_config().disk.warning_threshold == 85


def test_toml_file_overrides_defaults(tmp_path: Path) -> None:
    path = write_config(
        tmp_path,
        """
        [disk]
        paths = ["/", "/home"]
        warning_threshold = 70

        [process]
        timeout_seconds = 5
        """,
    )
    config = load_config(path)
    assert config.disk.paths == ("/", "/home")
    assert config.disk.warning_threshold == 70
    assert config.process.timeout_seconds == 5.0
    assert config.source == path


def test_env_overrides_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = write_config(tmp_path, "[disk]\nwarning_threshold = 70\n")
    monkeypatch.setenv("ENDPOINTCTL_DISK_WARNING_THRESHOLD", "42")
    assert load_config(path).disk.warning_threshold == 42


def test_missing_explicit_config_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "absent.toml")


@pytest.mark.parametrize(
    "body",
    [
        "[disk]\nwarning_threshold = 0\n",
        "[disk]\nwarning_threshold = 100\n",
        "[disk]\nwarning_threshold = 'high'\n",
        "[disk]\npaths = ['relative/path']\n",
        "[disk]\npaths = []\n",
        "[process]\ntimeout_seconds = 0\n",
        "[process]\ntimeout_seconds = -3\n",
        "[logging]\nmax_bytes = 0\n",
        "[logging]\nbackup_count = -1\n",
        "[security]\nprotection_processes = []\n",
        "[unknown]\nkey = 1\n",
        "[disk]\npaths = 'not-a-list'\n",
    ],
)
def test_invalid_configuration_fails_startup(tmp_path: Path, body: str) -> None:
    path = write_config(tmp_path, body)
    with pytest.raises(ConfigError):
        load_config(path)


def test_invalid_toml_syntax_is_reported(tmp_path: Path) -> None:
    path = write_config(tmp_path, "[disk\n")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(path)


def test_windows_absolute_paths_accepted_on_any_host(tmp_path: Path) -> None:
    path = write_config(tmp_path, '[disk]\npaths = ["C:\\\\"]\n')
    assert load_config(path).disk.paths == ("C:\\",)


def test_invalid_env_value_fails_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENDPOINTCTL_PROCESS_TIMEOUT", "soon")
    with pytest.raises(ConfigError, match="ENDPOINTCTL_PROCESS_TIMEOUT"):
        load_config()


def test_process_names_are_normalised(tmp_path: Path) -> None:
    path = write_config(tmp_path, "[security]\nprotection_processes = ['  MsMpEng  ']\n")
    assert load_config(path).security.protection_processes == ("msmpeng",)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", True), ("true", True), ("YES", True), ("0", False), ("", False), ("maybe", False)],
)
def test_remediation_flag_fails_closed(value: str, expected: bool) -> None:
    assert remediation_enabled({"ENDPOINTCTL_ENABLE_REMEDIATION": value}) is expected


def test_remediation_disabled_when_unset() -> None:
    assert remediation_enabled({}) is False
    assert default_config().remediation.enabled is False


def test_log_file_default_is_not_the_working_directory() -> None:
    log_file = default_config().logging.file
    assert log_file.is_absolute()
    assert Path.cwd() not in log_file.parents
