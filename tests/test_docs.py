"""Documentation must not drift from the binary - the previous README did."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from endpointctl import __version__
from endpointctl.cli import REMEDIATION_TARGETS
from endpointctl.config import REMEDIATION_ENV_VAR, load_config
from endpointctl.models import ExitCode
from endpointctl.scanner import SCAN_TARGETS

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DOCS = sorted((ROOT / "docs").glob("*.md"))
MARKDOWN_FILES = [README, ROOT / "CHANGELOG.md", ROOT / "CONTRIBUTING.md", *DOCS]


def test_readme_documents_the_remediation_gate() -> None:
    assert REMEDIATION_ENV_VAR in README.read_text(encoding="utf-8")


def test_readme_documents_every_scan_target() -> None:
    text = README.read_text(encoding="utf-8")
    for target in SCAN_TARGETS:
        assert f"scan {target}" in text, f"README does not document 'scan {target}'"


def test_readme_documents_every_exit_code() -> None:
    text = README.read_text(encoding="utf-8")
    for code in ExitCode:
        assert f"| `{int(code)}` |" in text, f"README does not document exit code {int(code)}"


def test_readme_version_matches_the_package() -> None:
    assert f"`{__version__}`" in README.read_text(encoding="utf-8")


def test_readme_does_not_promise_removed_behaviour() -> None:
    text = README.read_text(encoding="utf-8").lower()
    for claim in ("manage-bde -on", "fdesetup enable"):
        assert claim not in text, f"README still advertises {claim}"


def test_remediation_targets_are_documented() -> None:
    text = (ROOT / "docs" / "operations.md").read_text(encoding="utf-8")
    assert "remediate" in text
    assert set(REMEDIATION_TARGETS) == {"disk", "encryption"}


@pytest.mark.parametrize("path", MARKDOWN_FILES, ids=lambda p: p.name)
def test_relative_links_resolve(path: Path) -> None:
    for match in re.finditer(r"\]\(([^)#]+?)(?:#[^)]*)?\)", path.read_text(encoding="utf-8")):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        assert (path.parent / target).exists(), f"{path.name} links to missing {target}"


def test_example_configuration_is_valid() -> None:
    config = load_config(ROOT / "endpointctl.example.toml")
    assert config.disk.warning_threshold == 85
    assert config.process.timeout_seconds == 30
    assert "msmpeng" in config.security.protection_processes
