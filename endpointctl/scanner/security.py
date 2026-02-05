import platform
import psutil
import os

def check_security():
    findings = []

    # Check privilage level
    is_admin = os.geteuid() == 0 if hasattr(os, "getuid") else False
    findings.append({
        "check": "admin_privileges",
        "status": "INFO",
        "enabled": is_admin
    })

    # Antivirus / XDR check (process-based heuristic)
    known_security_process = [
        "defender",
        "msmpeng",
        "falcon",
        "cortex",
        "sentinel",
        "crowdstrike"
    ]

    running_processes = " ".join(p.name().lower() for p in psutil.process_iter())
    security_running = any(proc in running_processes for proc in known_security_process)

    findings.append({
        "check": "endpoint_protection",
        "status": "OK" if security_running else "WARNING",
        "detected": security_running
    })

    return {
        "metric": "security_baseline",
        "findings": findings
    }
