"""Allow ``python -m endpointctl`` as an alternative to the console script."""

import sys

from endpointctl.cli import main

if __name__ == "__main__":
    sys.exit(main())
