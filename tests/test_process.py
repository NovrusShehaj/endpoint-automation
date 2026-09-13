from __future__ import annotations

import subprocess
import sys

import pytest

from endpointctl.process import run_os_tool


def test_successful_tool_run() -> None:
    result = run_os_tool([sys.executable, "-c", "print('hello')"], timeout=30)
    assert result.ok is True
    assert result.returncode == 0
    assert "hello" in result.stdout
    assert result.failure is None


def test_non_zero_exit_is_reported_not_raised() -> None:
    result = run_os_tool([sys.executable, "-c", "raise SystemExit(3)"], timeout=30)
    assert result.ok is False
    assert result.returncode == 3
    assert result.failure is None


def test_missing_binary_is_not_found() -> None:
    result = run_os_tool(["endpointctl-does-not-exist"], timeout=5)
    assert result.failure == "not_found"
    assert result.returncode is None
    assert result.ok is False


def test_timeout_is_surfaced(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="slow", timeout=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_os_tool(["slow"], timeout=1)
    assert result.failure == "timeout"
    assert result.ok is False
    assert "timed out" in (result.error or "")


def test_os_error_is_surfaced(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert run_os_tool(["blocked"], timeout=1).failure == "os_error"


def test_never_uses_a_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(argv: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured.update(kwargs)
        return subprocess.CompletedProcess(args=list(argv), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_os_tool(["tool", "--flag"], timeout=7)
    assert captured["shell"] is False
    assert captured["timeout"] == 7
    assert captured["check"] is False
    assert captured["argv"] == ("tool", "--flag")


@pytest.mark.parametrize(("argv", "timeout"), [([], 5), (["x"], 0), (["x"], -1)])
def test_programming_errors_raise(argv: list[str], timeout: float) -> None:
    with pytest.raises(ValueError):
        run_os_tool(argv, timeout=timeout)
