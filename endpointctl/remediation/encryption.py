import platform
import subprocess

def check_encryption():
    os_name = platform.system()

    if os_name == "Windows":
        cmd = ["manage-bde", "-status"]
    elif os_name == "Darwin":
        cmd = ["fdesetup", "status"]
    else:
        return {"encryption": "unsupported"}

    return = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )

    return {
        "encryption_output": result.stdout.strip()
    }
