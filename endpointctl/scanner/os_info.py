"""Host and operating-system metadata. Read-only, no OS tools, no printing."""

from __future__ import annotations

import platform
import socket
import sys

from endpointctl.config import Config
from endpointctl.models import ScanResult, Status

__all__ = ["check_os"]


def check_os(config: Config | None = None) -> ScanResult:
    """Collect host identity. Always ``INFO``: there is nothing to fail."""
    data = {
        "hostname": socket.gethostname(),
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
    }
    return ScanResult(
        name="os_info",
        status=Status.INFO,
        message=f"{data['os']} {data['os_release']} on {data['hostname']}",
        data=data,
    )
