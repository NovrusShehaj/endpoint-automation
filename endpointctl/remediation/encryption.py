import platform
import subprocess
from endpointctl.remediation.base import require_admin, confirm_action

def enable_encryption():
    require_admin()
    confirm_action("This will enable full disk encryption")

    os_name = platform.system()

    if os_name == "Windows":
        cmd = ["manage-bde", "-on", "c:"]
    elif os_name == "Darwin":
        cmd = ["fdesetup", "enable"]
    else:
        raise RunTimeError("Encryption not supported on this OS")

    result = subprocess.run(cmd, capture_output=True, text=True)

    return {
        "action": "enable_encryption",
        "stdout": result.stdout,
        "stderr": result.stderr
    }
