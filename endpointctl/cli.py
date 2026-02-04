import argparse
from endpointctl.scanner.os_info import scan_os

def run():
    parser = argparse.ArgumentParser(
        prog="endpointctl",
        description="Endpoint Automation & Self-Service Tool"
    )

    subparsers = parser.add_subparsers(dest="command")

    scan_parser = subparsers.add_parser("scan", help="Run endpoint health scan")

    args = parser.parse_args()

    if args.command == "scan":
        scan_os()
    else:
        parser.print_help()
