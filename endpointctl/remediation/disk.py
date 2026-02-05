import shutil
from pathlib import Path
from endpointctl.remediation.base import require_admin, confirm_action

def cleanup_temp():
    require_admin()
    confirm_action("This will remove temporary files")

    temp_dirs = [Path("/tmp"), Path("/var/tmp")]

    removed = 0

    for d in temp_dirs:
        if d.exists():
            for item in d.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                        removed += 1
                    elif item.is_dir():
                        shutil.rmtree(item)
                        removed += 1
                except Exception:
                    pass
    
    return {
        "action": "cleanup_temp",
        "removed_items": removed
    }
