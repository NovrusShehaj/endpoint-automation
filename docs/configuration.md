# Configuration reference

Every setting has a safe default; `endpointctl.toml` is optional. Invalid
values **fail startup** with exit code 1 — nothing is silently clamped or
ignored.

## File search order

First match wins:

1. `--config PATH`
2. `$ENDPOINTCTL_CONFIG`
3. `$XDG_CONFIG_HOME/endpointctl/endpointctl.toml` (POSIX) or
   `%APPDATA%\endpointctl\endpointctl.toml` (Windows)
4. `~/.config/endpointctl/endpointctl.toml`
5. `./endpointctl.toml` (working directory, last resort)

A `--config` path that does not exist is an error rather than a silent fallback.

## Settings

| Key | Type | Default | Notes |
|---|---|---|---|
| `disk.paths` | array of strings | `["/"]` POSIX, `["C:\\"]` Windows | Must be absolute. Each path is reported separately. |
| `disk.warning_threshold` | integer | `85` | 1–99. Usage **at or above** this is `WARNING`. |
| `encryption.windows_volumes` | array of strings | `["C:"]` | Queried with `manage-bde -status <volume>`. Ignored off Windows. |
| `security.protection_processes` | array of strings | built-in AV/EDR list | Matched **exactly** against normalised process names (lower-case, `.exe` stripped). |
| `process.timeout_seconds` | number | `30` | >0 and ≤3600. Applies to every OS-tool call. |
| `logging.file` | string | per-OS state dir | Absolute path recommended. |
| `logging.max_bytes` | integer | `5242880` | Rotation size. |
| `logging.backup_count` | integer | `3` | Rotated files kept. |

Unknown top-level sections are rejected, so a typo cannot silently disable a
setting.

## Environment overrides

Environment variables win over the file. Lists are comma-separated (or
`:`/`;` separated, following the platform).

| Variable | Overrides |
|---|---|
| `ENDPOINTCTL_CONFIG` | Config file location |
| `ENDPOINTCTL_DISK_PATHS` | `disk.paths` |
| `ENDPOINTCTL_DISK_WARNING_THRESHOLD` | `disk.warning_threshold` |
| `ENDPOINTCTL_ENCRYPTION_VOLUMES` | `encryption.windows_volumes` |
| `ENDPOINTCTL_SECURITY_PROCESSES` | `security.protection_processes` |
| `ENDPOINTCTL_PROCESS_TIMEOUT` | `process.timeout_seconds` |
| `ENDPOINTCTL_LOG_FILE` | `logging.file` |
| `ENDPOINTCTL_LOG_MAX_BYTES` | `logging.max_bytes` |
| `ENDPOINTCTL_LOG_BACKUP_COUNT` | `logging.backup_count` |
| `ENDPOINTCTL_ENABLE_REMEDIATION` | Registers the preview-only `remediate` command. Accepts `1`, `true`, `yes`; anything else is off. |

## Tuning the endpoint-protection list

The default list contains anti-malware / EDR agents only. Telemetry daemons
(`auditd`, `osqueryd`) are deliberately excluded — matching them would report
`OK` on almost every Linux host regardless of whether anything protects it.

Find the exact process name on a representative host, then pin it per OS image:

```toml
[security]
protection_processes = ["msmpeng", "csfalconservice"]   # Windows image
```

Matching is exact after normalisation. `sentinel-worker` will not match
`sentinelagent`, by design.

## Example

See [`endpointctl.example.toml`](../endpointctl.example.toml) in the repository
root. Copy it to one of the search locations and edit.
