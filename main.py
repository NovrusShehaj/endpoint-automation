"""Source-checkout entry point.

Prefer the installed console script (``endpointctl``) or ``python -m endpointctl``.
"""

import sys

from endpointctl.cli import run

if __name__ == "__main__":
    sys.exit(run())
