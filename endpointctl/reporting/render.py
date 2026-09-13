"""Presentation. Scanners return data; only this module formats it.

``render_text`` is for humans (Rich), ``render_json`` is the automation
contract: one JSON object per invocation with a stable key set.
"""

from __future__ import annotations

import json
from typing import Any

from rich.console import Console
from rich.table import Table

from endpointctl import __version__
from endpointctl.models import ScanReport, ScanResult, Status

__all__ = ["render_json", "render_text", "report_payload"]

_STATUS_STYLES: dict[Status, str] = {
    Status.OK: "bold green",
    Status.INFO: "bold cyan",
    Status.UNSUPPORTED: "bold yellow",
    Status.WARNING: "bold yellow",
    Status.ERROR: "bold red",
}


def report_payload(report: ScanReport) -> dict[str, Any]:
    """The JSON document for one invocation."""
    payload = report.to_dict()
    return {"tool": "endpointctl", "version": __version__, **payload}


def render_json(report: ScanReport) -> str:
    return json.dumps(report_payload(report), indent=2, default=str)


def render_text(report: ScanReport, console: Console, *, verbose: bool = False) -> None:
    for result in report.results:
        console.rule(f"[bold blue]{result.name}")
        console.print(_status_line(result))
        if result.message:
            console.print(result.message)
        if result.error:
            console.print(f"[red]error:[/red] {result.error}")
        if result.data:
            console.print(_data_table(result, verbose=verbose))
    console.rule("[bold blue]Summary")
    style = _STATUS_STYLES[report.status]
    console.print(f"Overall status: [{style}]{report.status.value}[/{style}]")


def _status_line(result: ScanResult) -> str:
    style = _STATUS_STYLES[result.status]
    return f"Status: [{style}]{result.status.value}[/{style}]"


def _data_table(result: ScanResult, *, verbose: bool) -> Table:
    table = Table(show_header=True, header_style="bold")
    table.add_column("field")
    table.add_column("value", overflow="fold")
    for key, value in result.data.items():
        if key == "raw_output" and not verbose:
            continue
        table.add_row(str(key), _format_value(value))
    return table


def _format_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, indent=2, default=str)
    if value is None:
        return "unknown"
    return str(value)
