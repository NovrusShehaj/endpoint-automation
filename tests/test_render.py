from __future__ import annotations

import json

from rich.console import Console

from endpointctl.models import ScanReport, ScanResult, Status
from endpointctl.reporting.render import render_json, render_text

REPORT = ScanReport(
    (
        ScanResult(
            name="disk_encryption",
            status=Status.WARNING,
            message="not active",
            data={"encrypted": False, "raw_output": "SECRET-LOOKING TOOL OUTPUT"},
        ),
    )
)


def test_json_is_parseable_and_stable() -> None:
    payload = json.loads(render_json(REPORT))
    assert payload["status"] == "WARNING"
    assert payload["results"][0]["data"]["encrypted"] is False


def test_text_hides_raw_output_unless_verbose() -> None:
    console = Console(record=True, width=120, force_terminal=False)
    render_text(REPORT, console)
    assert "SECRET-LOOKING TOOL OUTPUT" not in console.export_text()

    console = Console(record=True, width=120, force_terminal=False)
    render_text(REPORT, console, verbose=True)
    assert "SECRET-LOOKING TOOL OUTPUT" in console.export_text()


def test_text_shows_the_aggregate_status() -> None:
    console = Console(record=True, width=120, force_terminal=False)
    render_text(REPORT, console)
    output = console.export_text()
    assert "Overall status" in output
    assert "WARNING" in output


def test_errors_are_rendered() -> None:
    console = Console(record=True, width=120, force_terminal=False)
    render_text(
        ScanReport((ScanResult(name="x", status=Status.ERROR, error="tool missing"),)), console
    )
    assert "tool missing" in console.export_text()
