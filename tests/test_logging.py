from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

from endpointctl.cli import main
from endpointctl.reporting.logger import ROOT_LOGGER_NAME, audit, configure_logging


@pytest.fixture(autouse=True)
def reset_handlers():
    yield
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_importing_a_scanner_creates_no_files(tmp_path: Path) -> None:
    """Importing used to mkdir ./logs and write two bogus 'scan completed' lines."""
    code = (
        "import pathlib, endpointctl.scanner.disk, endpointctl.scanner.os_info;"
        " print(sorted(p.name for p in pathlib.Path('.').iterdir()))"
    )
    workdir = tmp_path / "empty-cwd"
    workdir.mkdir()
    completed = subprocess.run(
        [sys.executable, "-c", code], cwd=workdir, capture_output=True, text=True, check=True
    )
    assert completed.stdout.strip() == "[]"


def test_audit_record_is_one_json_line(tmp_path: Path) -> None:
    log_file = tmp_path / "nested" / "audit.log"
    assert configure_logging(log_file) == log_file
    audit("invocation", command="scan", target="disk", status="OK")

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["message"] == "invocation"
    assert record["command"] == "scan"
    assert record["status"] == "OK"
    assert record["level"] == "INFO"
    assert record["ts"].endswith("Z")


def test_rotation_is_configured(tmp_path: Path) -> None:
    configure_logging(tmp_path / "audit.log", max_bytes=1024, backup_count=2)
    handler = next(
        h
        for h in logging.getLogger(ROOT_LOGGER_NAME).handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    )
    assert handler.maxBytes == 1024
    assert handler.backupCount == 2


def test_unwritable_log_destination_does_not_fail_the_run(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    assert configure_logging(blocker / "sub" / "audit.log") is None


def test_no_log_disables_file_logging(tmp_path: Path) -> None:
    assert configure_logging(None) is None


def test_cli_writes_exactly_one_audit_record(tmp_path: Path) -> None:
    log_file = tmp_path / "cli-audit.log"
    assert main(["--log-file", str(log_file), "--json", "--quiet", "scan", "os"]) == 0

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["command"] == "scan"
    assert record["target"] == "os"
    assert record["exit_code"] == 0
    assert record["argv"][-1] == "os"
    assert record["hostname"]
    assert "version" in record
    assert "duration_ms" in record


def test_audit_log_never_contains_encryption_tool_output(tmp_path: Path) -> None:
    log_file = tmp_path / "audit.log"
    main(["--log-file", str(log_file), "--quiet", "scan", "encryption"])
    contents = log_file.read_text(encoding="utf-8")
    assert "manage-bde" not in contents
    assert "fdesetup" not in contents
