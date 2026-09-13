"""Static guards that lock in the security properties of this release."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "endpointctl"
SOURCE_FILES = sorted(PACKAGE_ROOT.rglob("*.py"))
RUNNER_MODULE = PACKAGE_ROOT / "process.py"


def test_sources_were_found() -> None:
    assert len(SOURCE_FILES) > 5


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_no_shell_execution(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == "shell":
                    assert not (
                        isinstance(keyword.value, ast.Constant) and keyword.value.value is True
                    ), f"{path.name} passes shell=True"
        if isinstance(node, ast.Attribute) and node.attr in {"system", "popen", "Popen"}:
            value = node.value
            if isinstance(value, ast.Name) and value.id in {"os", "subprocess"}:
                pytest.fail(f"{path.name} uses {value.id}.{node.attr}")


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda p: p.name)
def test_only_the_runner_calls_subprocess(path: Path) -> None:
    """Every OS tool call must go through run_os_tool, which always has a timeout."""
    if path == RUNNER_MODULE:
        return
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in {"run", "call", "check_output"}:
            value = node.value
            if isinstance(value, ast.Name) and value.id == "subprocess":
                pytest.fail(f"{path.name} calls subprocess directly; use run_os_tool")


def test_runner_always_passes_a_timeout() -> None:
    tree = ast.parse(RUNNER_MODULE.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
    ]
    assert calls, "expected subprocess.run in the runner"
    for call in calls:
        keywords = {kw.arg for kw in call.keywords}
        assert "timeout" in keywords
        assert "shell" in keywords


def test_no_encryption_enabling_verbs_in_scanners() -> None:
    """A scan module may not contain an argv token that enables encryption."""
    forbidden = {"-on", "enable", "-turnon"}
    for path in (PACKAGE_ROOT / "scanner").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value.strip().lower() not in forbidden, (
                    f"{path.name} contains the enabling token {node.value!r}"
                )


def test_remediation_modules_have_no_delete_calls() -> None:
    """No apply path ships: nothing in remediation may unlink or rmtree."""
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in (PACKAGE_ROOT / "remediation").rglob("*.py")
    )
    for forbidden in ("shutil.rmtree", ".unlink(", "os.remove", "os.rmdir"):
        assert forbidden not in text, f"remediation must not call {forbidden}"


def test_package_is_a_real_package_not_a_namespace() -> None:
    for directory in (PACKAGE_ROOT, *(p for p in PACKAGE_ROOT.iterdir() if p.is_dir())):
        if directory.name == "__pycache__":
            continue
        assert (directory / "__init__.py").is_file(), f"{directory} is missing __init__.py"
