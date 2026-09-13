"""Configuration layer: safe defaults, optional TOML file, env overrides.

Search order for the configuration file (first match wins):

1. ``--config PATH`` / the ``path`` argument to :func:`load_config`
2. ``$ENDPOINTCTL_CONFIG``
3. ``$XDG_CONFIG_HOME/endpointctl/endpointctl.toml`` (POSIX) or
   ``%APPDATA%\\endpointctl\\endpointctl.toml`` (Windows)
4. ``~/.config/endpointctl/endpointctl.toml``
5. ``./endpointctl.toml``

Individual ``ENDPOINTCTL_*`` environment variables override the file. Invalid
values raise :class:`ConfigError` and fail startup; nothing is silently clamped.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

__all__ = [
    "Config",
    "ConfigError",
    "DiskConfig",
    "EncryptionConfig",
    "LoggingConfig",
    "ProcessConfig",
    "SecurityConfig",
    "default_config",
    "load_config",
    "remediation_enabled",
]

#: Set ``ENDPOINTCTL_ENABLE_REMEDIATION=1`` to expose the experimental,
#: preview-only ``remediate`` command. No apply path ships in v1.
REMEDIATION_ENV_VAR = "ENDPOINTCTL_ENABLE_REMEDIATION"

CONFIG_FILE_NAME = "endpointctl.toml"

#: Process names (normalised: lower-case, ``.exe`` stripped) that count as an
#: endpoint-protection agent. Matched exactly - never as a substring.
#:
#: Deliberately limited to anti-malware / EDR agents. Telemetry daemons such as
#: ``auditd`` or ``osqueryd`` are not protection and would turn almost every
#: Linux host into a false "OK". Override the list per OS image in
#: ``endpointctl.toml`` rather than editing this file.
DEFAULT_PROTECTION_PROCESSES: tuple[str, ...] = (
    # Windows
    "msmpeng",
    "mssense",
    "sensecncproxy",
    "windefend",
    "csfalconservice",
    "cylancesvc",
    "cyserver",
    "sentinelagent",
    "sentinelstaticengine",
    "elastic-endpoint",
    # macOS
    "falcond",
    "falcon-sensor",
    "com.crowdstrike.falcon.agent",
    "sentineld",
    "sentineld-helper",
    "mdatp",
    "wdavdaemon",
    # Linux
    "clamd",
    "clamonacc",
    "falcon-sensor-bpf",
    "ds_agent",
)

DEFAULT_DISK_WARNING_THRESHOLD = 85
DEFAULT_PROCESS_TIMEOUT_SECONDS = 30.0
DEFAULT_LOG_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 3


class ConfigError(Exception):
    """Raised when configuration is present but invalid. Fails startup."""


@dataclass(frozen=True)
class DiskConfig:
    paths: tuple[str, ...]
    warning_threshold: int


@dataclass(frozen=True)
class EncryptionConfig:
    #: BitLocker volumes to query. Ignored on non-Windows hosts.
    windows_volumes: tuple[str, ...]


@dataclass(frozen=True)
class SecurityConfig:
    protection_processes: tuple[str, ...]


@dataclass(frozen=True)
class ProcessConfig:
    timeout_seconds: float


@dataclass(frozen=True)
class LoggingConfig:
    file: Path
    max_bytes: int
    backup_count: int


@dataclass(frozen=True)
class RemediationConfig:
    #: Mirror of :data:`REMEDIATION_ENV_VAR`. Even when true, only the preview
    #: (dry-run) path exists in v1.
    enabled: bool


@dataclass(frozen=True)
class Config:
    disk: DiskConfig
    encryption: EncryptionConfig
    security: SecurityConfig
    process: ProcessConfig
    logging: LoggingConfig
    remediation: RemediationConfig
    #: Configuration file the values came from, if any.
    source: Path | None = None


def default_disk_paths() -> tuple[str, ...]:
    """System volume for the running OS. Windows is ``C:\\``, never ``/``."""
    return ("C:\\",) if os.name == "nt" else ("/",)


def default_log_file() -> Path:
    """Per-user state location; never the current working directory."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        return root / "endpointctl" / "logs" / "endpoint.log"
    state_home = os.environ.get("XDG_STATE_HOME")
    root = Path(state_home) if state_home else Path.home() / ".local" / "state"
    return root / "endpointctl" / "endpoint.log"


def default_config() -> Config:
    return Config(
        disk=DiskConfig(
            paths=default_disk_paths(),
            warning_threshold=DEFAULT_DISK_WARNING_THRESHOLD,
        ),
        encryption=EncryptionConfig(windows_volumes=("C:",)),
        security=SecurityConfig(protection_processes=DEFAULT_PROTECTION_PROCESSES),
        process=ProcessConfig(timeout_seconds=DEFAULT_PROCESS_TIMEOUT_SECONDS),
        logging=LoggingConfig(
            file=default_log_file(),
            max_bytes=DEFAULT_LOG_MAX_BYTES,
            backup_count=DEFAULT_LOG_BACKUP_COUNT,
        ),
        remediation=RemediationConfig(enabled=remediation_enabled()),
    )


def remediation_enabled(env: dict[str, str] | None = None) -> bool:
    """True only for the exact opt-in values, so typos fail closed."""
    source = os.environ if env is None else env
    return source.get(REMEDIATION_ENV_VAR, "").strip().lower() in {"1", "true", "yes"}


def candidate_config_paths(explicit: str | os.PathLike[str] | None = None) -> list[Path]:
    if explicit is not None:
        return [Path(explicit)]

    candidates: list[Path] = []
    from_env = os.environ.get("ENDPOINTCTL_CONFIG")
    if from_env:
        candidates.append(Path(from_env))

    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "endpointctl" / CONFIG_FILE_NAME)
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            candidates.append(Path(xdg) / "endpointctl" / CONFIG_FILE_NAME)

    candidates.append(Path.home() / ".config" / "endpointctl" / CONFIG_FILE_NAME)
    candidates.append(Path.cwd() / CONFIG_FILE_NAME)
    return candidates


def load_config(
    explicit_path: str | os.PathLike[str] | None = None,
    env: dict[str, str] | None = None,
) -> Config:
    """Build the effective configuration. Raises :class:`ConfigError` if invalid."""
    environ = dict(os.environ) if env is None else env
    config = default_config()

    document: dict[str, Any] = {}
    source: Path | None = None
    for candidate in candidate_config_paths(explicit_path):
        if candidate.is_file():
            document = _read_toml(candidate)
            source = candidate
            break
    else:
        if explicit_path is not None:
            raise ConfigError(f"configuration file not found: {explicit_path}")

    config = _apply_document(config, document, source)
    config = _apply_env(config, environ)
    return _validate(replace(config, source=source))


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except OSError as exc:
        raise ConfigError(f"cannot read configuration file {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc


def _section(document: dict[str, Any], name: str, source: Path | None) -> dict[str, Any]:
    value = document.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"[{name}] must be a table in {source or '<config>'}")
    return value


def _apply_document(config: Config, document: dict[str, Any], source: Path | None) -> Config:
    known = {"disk", "encryption", "security", "process", "logging"}
    unknown = sorted(set(document) - known)
    if unknown:
        raise ConfigError(
            f"unknown configuration section(s): {', '.join(unknown)} "
            f"(supported: {', '.join(sorted(known))})"
        )

    disk = _section(document, "disk", source)
    encryption = _section(document, "encryption", source)
    security = _section(document, "security", source)
    process = _section(document, "process", source)
    logging_section = _section(document, "logging", source)

    return Config(
        disk=DiskConfig(
            paths=_as_str_tuple(disk.get("paths"), "disk.paths", config.disk.paths),
            warning_threshold=_as_int(
                disk.get("warning_threshold"),
                "disk.warning_threshold",
                config.disk.warning_threshold,
            ),
        ),
        encryption=EncryptionConfig(
            windows_volumes=_as_str_tuple(
                encryption.get("windows_volumes"),
                "encryption.windows_volumes",
                config.encryption.windows_volumes,
            )
        ),
        security=SecurityConfig(
            protection_processes=_as_str_tuple(
                security.get("protection_processes"),
                "security.protection_processes",
                config.security.protection_processes,
            )
        ),
        process=ProcessConfig(
            timeout_seconds=_as_float(
                process.get("timeout_seconds"),
                "process.timeout_seconds",
                config.process.timeout_seconds,
            )
        ),
        logging=LoggingConfig(
            file=_as_path(logging_section.get("file"), "logging.file", config.logging.file),
            max_bytes=_as_int(
                logging_section.get("max_bytes"), "logging.max_bytes", config.logging.max_bytes
            ),
            backup_count=_as_int(
                logging_section.get("backup_count"),
                "logging.backup_count",
                config.logging.backup_count,
            ),
        ),
        remediation=config.remediation,
        source=source,
    )


def _apply_env(config: Config, environ: dict[str, str]) -> Config:
    disk = config.disk
    if "ENDPOINTCTL_DISK_PATHS" in environ:
        disk = replace(disk, paths=_split_list(environ["ENDPOINTCTL_DISK_PATHS"]))
    if "ENDPOINTCTL_DISK_WARNING_THRESHOLD" in environ:
        disk = replace(
            disk,
            warning_threshold=_env_int(
                environ["ENDPOINTCTL_DISK_WARNING_THRESHOLD"],
                "ENDPOINTCTL_DISK_WARNING_THRESHOLD",
            ),
        )

    encryption = config.encryption
    if "ENDPOINTCTL_ENCRYPTION_VOLUMES" in environ:
        encryption = replace(
            encryption,
            windows_volumes=_split_list(environ["ENDPOINTCTL_ENCRYPTION_VOLUMES"]),
        )

    security = config.security
    if "ENDPOINTCTL_SECURITY_PROCESSES" in environ:
        security = replace(
            security,
            protection_processes=_split_list(environ["ENDPOINTCTL_SECURITY_PROCESSES"]),
        )

    process = config.process
    if "ENDPOINTCTL_PROCESS_TIMEOUT" in environ:
        process = replace(
            process,
            timeout_seconds=_env_float(
                environ["ENDPOINTCTL_PROCESS_TIMEOUT"], "ENDPOINTCTL_PROCESS_TIMEOUT"
            ),
        )

    logging_config = config.logging
    if "ENDPOINTCTL_LOG_FILE" in environ:
        logging_config = replace(logging_config, file=Path(environ["ENDPOINTCTL_LOG_FILE"]))
    if "ENDPOINTCTL_LOG_MAX_BYTES" in environ:
        logging_config = replace(
            logging_config,
            max_bytes=_env_int(environ["ENDPOINTCTL_LOG_MAX_BYTES"], "ENDPOINTCTL_LOG_MAX_BYTES"),
        )
    if "ENDPOINTCTL_LOG_BACKUP_COUNT" in environ:
        logging_config = replace(
            logging_config,
            backup_count=_env_int(
                environ["ENDPOINTCTL_LOG_BACKUP_COUNT"], "ENDPOINTCTL_LOG_BACKUP_COUNT"
            ),
        )

    return replace(
        config,
        disk=disk,
        encryption=encryption,
        security=security,
        process=process,
        logging=logging_config,
        remediation=RemediationConfig(enabled=remediation_enabled(environ)),
    )


def _validate(config: Config) -> Config:
    if not config.disk.paths:
        raise ConfigError("disk.paths must list at least one path")
    for path in config.disk.paths:
        if not _is_absolute(path):
            raise ConfigError(f"disk.paths entries must be absolute, got {path!r}")

    threshold = config.disk.warning_threshold
    if not 1 <= threshold <= 99:
        raise ConfigError(f"disk.warning_threshold must be between 1 and 99, got {threshold}")

    if not config.encryption.windows_volumes:
        raise ConfigError("encryption.windows_volumes must list at least one volume")

    if not config.security.protection_processes:
        raise ConfigError("security.protection_processes must list at least one name")
    for name in config.security.protection_processes:
        if not name.strip():
            raise ConfigError("security.protection_processes entries must not be blank")

    timeout = config.process.timeout_seconds
    if not 0 < timeout <= 3600:
        raise ConfigError(f"process.timeout_seconds must be >0 and <=3600, got {timeout}")

    if config.logging.max_bytes <= 0:
        raise ConfigError("logging.max_bytes must be positive")
    if config.logging.backup_count < 0:
        raise ConfigError("logging.backup_count must not be negative")

    normalised = tuple(name.strip().lower() for name in config.security.protection_processes)
    return replace(config, security=SecurityConfig(protection_processes=normalised))


def _is_absolute(value: str) -> bool:
    """Accept both POSIX and Windows absolute paths regardless of the host OS."""
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _split_list(raw: str) -> tuple[str, ...]:
    separator = ";" if os.name == "nt" else ":"
    if "," in raw:
        separator = ","
    return tuple(part.strip() for part in raw.split(separator) if part.strip())


def _as_str_tuple(value: Any, key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return fallback
    if isinstance(value, str) or not isinstance(value, (list, tuple)):
        raise ConfigError(f"{key} must be an array of strings")
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(f"{key} must contain only strings, got {item!r}")
    return tuple(value)


def _as_int(value: Any, key: str, fallback: int) -> int:
    if value is None:
        return fallback
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{key} must be an integer, got {value!r}")
    return value


def _as_float(value: Any, key: str, fallback: float) -> float:
    if value is None:
        return fallback
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{key} must be a number, got {value!r}")
    return float(value)


def _as_path(value: Any, key: str, fallback: Path) -> Path:
    if value is None:
        return fallback
    if not isinstance(value, str):
        raise ConfigError(f"{key} must be a string path, got {value!r}")
    return Path(value).expanduser()


def _env_int(raw: str, name: str) -> int:
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _env_float(raw: str, name: str) -> float:
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc
