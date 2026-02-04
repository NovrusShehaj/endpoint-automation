import platform
import socket
from rich.console import Console
from endpointctl.reporting.logger import logger

console = Console()

def scan_os():
    console.rule("[bold blue]Endpoint OS Information")

    info = {
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "os_version": platform.version(),
        "architecture": platform.machine()
    }

    for k, v in info.items():
        console.print(f"[green]{k}:[/green] {v}")

logger.info("OS Information Retrieved")
