import argparse
from rich.console import Console

from endpointctl.scanner.os_info import scan_os
from endpointctl.scanner.encryption import check_encryption
from endpointctl.scanner.security import check_security
from endpointctl.scanner.disk import check_disk

console = Console()

def run():
    parser = argparse.ArgumentParser(
        prog="endpointctl",
        description="Endpoint Automation & Self-Service Tool"
    )

    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="Run endpoint health scan")
    scan_parser.add_argument(
        "target",
        choices=["disk", "encryption", "security", "all"],
        help="Which scan to run"
    )

    args = parser.parse_args()

    if args.command == "scan":
        if args.target == "disk":
            console.rule("[bold blue]Disk Scan")
            console.print(check_disk())
        elif args.target == "encryption":
            console.rule("[bold blue]Encryption Scan")
            console.print(check_encryption())

        elif args.target == "security":
            console.rule("[bold blue]Security Baseline")
            console.print(check_security())

        elif args.target == "all":
            scan_os()

            console.rule("[bold blue]Disk Scan")
            console.print(check_disk())

            console.rule("[bold blue]Encryption Scan")
            console.print(check_encryption())

            console.rule("[bold blue]Security Baseline")
            console.print(check_security())
