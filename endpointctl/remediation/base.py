import os
import platform

class RemediationError(Exception):
    pass

def require_admin():
    if platform.system() != "Windows":
        if os.geteuid() != 0:
            raise RemediationError("Administrator privileges required")

def confirm_action(message):
    response = input(f"{message} (yes/no): ").strip().lower()
    if response != "yes":
        raise RemediationError("Remediation cancelled by user")

