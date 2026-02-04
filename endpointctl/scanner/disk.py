import psutil
from rich.console import Console 

console = Console()

def check_disk():
    usage = psutil.disk_usage("/")
    percent = usage.percent

    status = "OK" if percent < 85 else "WARNING"

    console.print(f"Disk Usage: {percent}% [{status}]")

    return {
        "disk_usage": percent,
        "status": status
    }
