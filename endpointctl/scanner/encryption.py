"""Full-disk-encryption detection (detect-only; nothing is ever enabled here).

The parsers read documented fields - ``Protection Status:`` from ``manage-bde``
and the ``FileVault is On/Off.`` sentence from ``fdesetup`` - rather than
searching the whole output for the substrings ``on`` or ``encrypted``, which
matched ``Protection`` and ``Percentage Encrypted: 0.0%`` and reported
decrypted Windows volumes as encrypted.

Unrecognised output is ``ERROR``, never an optimistic ``encrypted: true``.
"""

from __future__ import annotations

import platform
import re
from dataclasses import dataclass, field
from typing import Any

from endpointctl.config import Config, default_config
from endpointctl.models import ScanResult, Status
from endpointctl.process import run_os_tool

__all__ = [
    "EncryptionState",
    "check_encryption",
    "parse_fdesetup_status",
    "parse_manage_bde_status",
]

_MANAGE_BDE_FIELD = re.compile(r"^\s*([A-Za-z][A-Za-z /-]+?):\s*(.+?)\s*$")
_FILEVAULT_STATE = re.compile(r"^\s*FileVault is (On|Off)\b(.*)$", re.IGNORECASE | re.MULTILINE)


@dataclass(frozen=True)
class EncryptionState:
    """Parsed state of one volume.

    ``encrypted`` is ``None`` when the tool output did not contain the field we
    require - the honest "we do not know" that keeps a decrypted host from
    being reported as compliant.
    """

    encrypted: bool | None
    detail: str
    fields: dict[str, Any] = field(default_factory=dict)


def parse_manage_bde_status(output: str) -> EncryptionState:
    """Parse ``manage-bde -status <volume>`` output for one volume.

    A volume counts as encrypted only when protection is on. ``Protection Off``
    with ``Fully Encrypted`` (BitLocker suspended) is reported as not encrypted,
    because the key is no longer protected.
    """
    fields: dict[str, Any] = {}
    for line in output.splitlines():
        match = _MANAGE_BDE_FIELD.match(line)
        if match:
            key = match.group(1).strip().lower().replace(" ", "_")
            fields[key] = match.group(2).strip()

    protection = fields.get("protection_status")
    if protection is None:
        return EncryptionState(None, "no 'Protection Status' field in manage-bde output", fields)

    normalised = protection.strip().lower()
    if normalised.startswith("protection on"):
        return EncryptionState(True, protection, fields)
    if normalised.startswith("protection off"):
        return EncryptionState(False, protection, fields)
    return EncryptionState(None, f"unrecognised protection status: {protection!r}", fields)


def parse_fdesetup_status(output: str) -> EncryptionState:
    """Parse ``fdesetup status`` output (English locale)."""
    match = _FILEVAULT_STATE.search(output)
    if not match:
        return EncryptionState(None, "no 'FileVault is On/Off' sentence in fdesetup output", {})

    state = match.group(1).lower()
    detail = match.group(0).strip()
    fields: dict[str, Any] = {"filevault": state}
    progress = re.search(r"Percent completed\s*=\s*([0-9.]+)", output, re.IGNORECASE)
    if progress:
        fields["percent_completed"] = progress.group(1)
    return EncryptionState(state == "on", detail, fields)


def check_encryption(config: Config | None = None) -> ScanResult:
    """Detect full-disk encryption on the running host."""
    config = config or default_config()
    os_name = platform.system()

    if os_name == "Windows":
        return _check_windows(config)
    if os_name == "Darwin":
        return _check_macos(config)
    return ScanResult(
        name="disk_encryption",
        status=Status.UNSUPPORTED,
        message=(
            f"disk-encryption detection is not implemented for {os_name or 'this platform'}; "
            "Linux LUKS/dm-crypt detection is planned but not part of v1"
        ),
        data={"platform": os_name, "detector": None},
    )


def _check_windows(config: Config) -> ScanResult:
    timeout = config.process.timeout_seconds
    volumes: list[dict[str, Any]] = []
    statuses: list[Status] = []
    errors: list[str] = []

    for volume in config.encryption.windows_volumes:
        result = run_os_tool(["manage-bde", "-status", volume], timeout=timeout)
        entry: dict[str, Any] = {"volume": volume, "tool": "manage-bde"}

        failure = _tool_failure(result, "manage-bde")
        if failure is not None:
            statuses.append(Status.ERROR)
            errors.append(f"{volume}: {failure}")
            entry.update(status=Status.ERROR.value, encrypted=None, detail=failure)
            volumes.append(entry)
            continue

        state = parse_manage_bde_status(result.stdout)
        status = _state_status(state)
        statuses.append(status)
        if state.encrypted is None:
            errors.append(f"{volume}: {state.detail}")
        entry.update(
            status=status.value,
            encrypted=state.encrypted,
            detail=state.detail,
            conversion_status=state.fields.get("conversion_status"),
            percentage_encrypted=state.fields.get("percentage_encrypted"),
            encryption_method=state.fields.get("encryption_method"),
            raw_output=result.stdout.strip(),
        )
        volumes.append(entry)

    return _build_result("manage-bde", volumes, statuses, errors)


def _check_macos(config: Config) -> ScanResult:
    result = run_os_tool(["fdesetup", "status"], timeout=config.process.timeout_seconds)
    entry: dict[str, Any] = {"volume": "system", "tool": "fdesetup"}

    failure = _tool_failure(result, "fdesetup")
    if failure is not None:
        entry.update(status=Status.ERROR.value, encrypted=None, detail=failure)
        return _build_result("fdesetup", [entry], [Status.ERROR], [failure])

    state = parse_fdesetup_status(result.stdout)
    status = _state_status(state)
    entry.update(
        status=status.value,
        encrypted=state.encrypted,
        detail=state.detail,
        raw_output=result.stdout.strip(),
        **{k: v for k, v in state.fields.items() if k != "filevault"},
    )
    errors = [] if state.encrypted is not None else [state.detail]
    return _build_result("fdesetup", [entry], [status], errors)


def _tool_failure(result: Any, tool: str) -> str | None:
    """Map a :class:`~endpointctl.process.ToolResult` to an error string, or ``None``."""
    if result.failure == "not_found":
        return f"{tool} is not available on this host"
    if result.failure == "timeout":
        return f"{tool} timed out"
    if result.failure is not None:
        return f"{tool} could not be executed: {result.error}"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        first_line = detail[0] if detail else "no output"
        return f"{tool} exited with status {result.returncode}: {first_line}"
    return None


def _state_status(state: EncryptionState) -> Status:
    if state.encrypted is None:
        return Status.ERROR
    return Status.OK if state.encrypted else Status.WARNING


def _build_result(
    detector: str,
    volumes: list[dict[str, Any]],
    statuses: list[Status],
    errors: list[str],
) -> ScanResult:
    aggregate = max(statuses, key=lambda s: s.severity) if statuses else Status.ERROR
    encrypted_values = [v.get("encrypted") for v in volumes]
    if encrypted_values and all(value is True for value in encrypted_values):
        encrypted: bool | None = True
    elif any(value is None for value in encrypted_values) or not encrypted_values:
        encrypted = None
    else:
        encrypted = False

    return ScanResult(
        name="disk_encryption",
        status=aggregate,
        message=_encryption_message(encrypted, volumes),
        data={"detector": detector, "encrypted": encrypted, "volumes": volumes},
        error="; ".join(errors) or None,
    )


def _encryption_message(encrypted: bool | None, volumes: list[dict[str, Any]]) -> str:
    names = ", ".join(str(v.get("volume")) for v in volumes) or "no volumes"
    if encrypted is True:
        return f"full-disk encryption is active on {names}"
    if encrypted is False:
        return f"full-disk encryption is NOT active on {names}"
    return f"encryption state of {names} could not be determined"
