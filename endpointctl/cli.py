"""Command-line entry point.

Operational contract:

* a subcommand is required; a bare invocation prints help and exits non-zero
* ``--json`` prints exactly one JSON object for automation
* findings affect the exit code (see :class:`~endpointctl.models.ExitCode`)
* every invocation writes one structured audit record
* the ``remediate`` command is registered only when
  ``ENDPOINTCTL_ENABLE_REMEDIATION`` is set, and never applies changes

Remediation modules are imported lazily inside the ``remediate`` branch, so a
scan never loads state-changing code.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from rich.console import Console

from endpointctl import __version__
from endpointctl.config import Config, ConfigError, load_config, remediation_enabled
from endpointctl.models import ExitCode, ScanReport, ScanResult, Status
from endpointctl.reporting.logger import audit, configure_logging, invocation_context
from endpointctl.reporting.render import render_json, render_text
from endpointctl.scanner import SCAN_TARGETS, run_scan

__all__ = ["build_parser", "main", "run"]

REMEDIATION_TARGETS: tuple[str, ...] = ("disk", "encryption")


class UsageError(Exception):
    """Raised instead of ``SystemExit(2)`` so argparse cannot claim exit code 2."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise UsageError(message)


def _common_options() -> _Parser:
    """Flags accepted both before and after the subcommand.

    ``SUPPRESS`` defaults keep the subparser copy from clobbering a value that
    was given before the subcommand; :func:`_apply_defaults` fills the gaps.
    """
    common = _Parser(add_help=False)
    common.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
        help="emit one JSON object on stdout",
    )
    common.add_argument(
        "--verbose",
        action="store_true",
        default=argparse.SUPPRESS,
        help="include raw OS-tool output and log diagnostics to stderr",
    )
    common.add_argument(
        "--quiet",
        action="store_true",
        default=argparse.SUPPRESS,
        help="suppress human-readable output",
    )
    common.add_argument(
        "--config",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help="path to an endpointctl.toml file",
    )
    common.add_argument(
        "--log-file",
        metavar="PATH",
        default=argparse.SUPPRESS,
        help="override the audit log location",
    )
    common.add_argument(
        "--no-log",
        action="store_true",
        default=argparse.SUPPRESS,
        help="do not write an audit log for this invocation",
    )
    return common


_OPTION_DEFAULTS: dict[str, Any] = {
    "json": False,
    "verbose": False,
    "quiet": False,
    "config": None,
    "log_file": None,
    "no_log": False,
}


def _apply_defaults(args: argparse.Namespace) -> argparse.Namespace:
    for name, value in _OPTION_DEFAULTS.items():
        if not hasattr(args, name):
            setattr(args, name, value)
    return args


def build_parser(*, remediation: bool = False) -> argparse.ArgumentParser:
    common = _common_options()
    parser = _Parser(
        prog="endpointctl",
        description="Endpoint health and security posture scanner (scan-only).",
        parents=[common],
        epilog=(
            "Exit codes: 0 ok, 1 usage/refused, 2 warning findings, 3 errors, 4 unexpected failure."
        ),
    )
    parser.add_argument("--version", action="version", version=f"endpointctl {__version__}")

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    scan_parser = subparsers.add_parser(
        "scan", help="run a read-only endpoint scan", parents=[common]
    )
    scan_parser.add_argument("target", choices=list(SCAN_TARGETS), help="which scan to run")

    if remediation:
        remediate_parser = subparsers.add_parser(
            "remediate",
            help="preview a remediation (experimental; never applies changes)",
            parents=[common],
        )
        remediate_parser.add_argument(
            "target", choices=list(REMEDIATION_TARGETS), help="remediation to preview"
        )
        remediate_parser.add_argument(
            "--apply",
            action="store_true",
            help="request execution (refused: no apply path ships in this release)",
        )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code. Never raises."""
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser(remediation=remediation_enabled())

    if not raw_argv:
        parser.print_help()
        return int(ExitCode.USAGE)

    try:
        args = _apply_defaults(parser.parse_args(raw_argv))
    except UsageError as exc:
        parser.print_usage(sys.stderr)
        print(f"{parser.prog}: error: {exc}", file=sys.stderr)
        return int(ExitCode.USAGE)
    except SystemExit as exc:  # --help / --version
        return int(ExitCode.OK) if not exc.code else int(ExitCode.USAGE)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"endpointctl: configuration error: {exc}", file=sys.stderr)
        return int(ExitCode.USAGE)

    log_file: Path | None = None
    if not args.no_log:
        log_file = Path(args.log_file) if args.log_file else config.logging.file
    configure_logging(
        log_file,
        level=logging.DEBUG if args.verbose else logging.INFO,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
        stderr_level=logging.DEBUG if args.verbose else None,
    )

    console = Console(stderr=False, quiet=args.quiet)
    started = time.monotonic()
    context = invocation_context(raw_argv)
    exit_code = int(ExitCode.UNEXPECTED)
    report: ScanReport | None = None

    try:
        if args.command == "scan":
            report, exit_code = _handle_scan(args, config, console)
        elif args.command == "remediate":
            report, exit_code = _handle_remediate(args, config, console)
        else:  # pragma: no cover - argparse restricts the choices
            parser.print_help()
            exit_code = int(ExitCode.USAGE)
    except KeyboardInterrupt:
        print("endpointctl: interrupted", file=sys.stderr)
        exit_code = int(ExitCode.USAGE)
    except Exception as exc:
        print(f"endpointctl: unexpected failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        logging.getLogger("endpointctl").exception("unexpected failure")
        exit_code = int(ExitCode.UNEXPECTED)
    finally:
        audit(
            "invocation",
            **context,
            command=getattr(args, "command", None),
            target=getattr(args, "target", None),
            status=report.status.value if report is not None else Status.ERROR.value,
            exit_code=exit_code,
            duration_ms=round((time.monotonic() - started) * 1000, 1),
        )

    return exit_code


def run(argv: Sequence[str] | None = None) -> int:
    """Backwards-compatible alias used by ``main.py``."""
    return main(argv)


def _handle_scan(
    args: argparse.Namespace, config: Config, console: Console
) -> tuple[ScanReport, int]:
    report = run_scan(args.target, config)
    _emit(report, args, console)
    return report, int(report.exit_code)


def _handle_remediate(
    args: argparse.Namespace, config: Config, console: Console
) -> tuple[ScanReport, int]:
    # Imported here so a scan never loads state-changing code.
    from endpointctl.remediation.base import RemediationError
    from endpointctl.remediation.disk import apply_temp_cleanup, plan_temp_cleanup
    from endpointctl.remediation.encryption import enable_encryption

    name = f"remediate_{args.target}"
    try:
        if args.target == "disk":
            if args.apply:
                apply_temp_cleanup()
            plan = plan_temp_cleanup()
            result = ScanResult(
                name=name,
                status=Status.INFO,
                message=(
                    f"preview only: {plan['candidate_count']} candidate item(s), "
                    f"{plan['reclaimable_bytes']} byte(s) reclaimable; nothing was deleted"
                ),
                data=plan,
            )
        else:
            # Annotated NoReturn: it always raises RemediationDisabledError.
            enable_encryption()
    except RemediationError as exc:
        from endpointctl.remediation.encryption import plan_encryption_remediation

        data = plan_encryption_remediation() if args.target == "encryption" else {}
        result = ScanResult(
            name=name,
            status=Status.UNSUPPORTED,
            message="remediation refused; no host state was changed",
            data=data,
            error=str(exc),
        )
        report = ScanReport(results=(result,))
        _emit(report, args, console)
        return report, int(ExitCode.USAGE)

    report = ScanReport(results=(result,))
    _emit(report, args, console)
    return report, int(ExitCode.OK)


def _emit(report: ScanReport, args: argparse.Namespace, console: Console) -> None:
    if args.json:
        print(render_json(report))
        return
    render_text(report, console, verbose=args.verbose)
