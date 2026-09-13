"""endpointctl — a scan-only endpoint health and security posture CLI.

Version 1 is deliberately read-only: scans never modify host state and the
remediation surface is not registered on the default command line. See
``docs/operations.md`` and the Safety section of ``README.md``.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
