import platform
import subprocess

def check_encryption():

    os_name = platform.system()

    try:
        if os_name == "Windows":
            cmd = ["manage-bde", "-status"]
        elif os_name == "Darwin":
            cmd = ["fdesetup", "status"]
        else:
            return {
                "metric": "disk_encryption",
                "status": "UNSUPPORTED",
                "details": os_name
            }
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        encrypted = "on" in result.stdout.lower() or "encrypted" in result.stdout.lower()

        return {
            "metric": "disk_encryption",
            "encrypted": encrypted,
            "raw_output": result.stdout.strip()
        }

    except Exception as e:
        return {
            "metric": "disk_encryption",
            "status": "ERROR",
            "error": str(e)
        }

