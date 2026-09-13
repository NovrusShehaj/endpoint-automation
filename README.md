# endpointctl — Endpoint Health & Security Posture Scanner

A cross-platform Python CLI that reports endpoint health and security posture:
host metadata, disk capacity, full-disk-encryption state, and an endpoint
protection baseline.

**Version 1 is scan-only.** Nothing this tool does in its default configuration
modifies host state. There is no command that deletes files and no command that
enables BitLocker or FileVault. That is a deliberate design decision, not a
missing feature — see [Safety](#safety) and
[docs/open-questions.md](docs/open-questions.md).

---

## Status

| | |
|---|---|
| Version | `0.1.0` (pre-1.0; the CLI contract may still change) |
| Posture | Scan-only. Remediation is preview-only and off by default. |
| Python | 3.11 – 3.14 (`requires-python = ">=3.11,<3.15"`) |
| Tested | Linux on hardware/CI. Windows and macOS logic is covered by recorded output fixtures, **not** by hardware testing. |
| License | **Not yet chosen.** Absent a `LICENSE` file this is all-rights-reserved; see [docs/open-questions.md](docs/open-questions.md#q5--license). |

### Support matrix

| Check | Linux | Windows | macOS |
|---|---|---|---|
| `scan os` — host metadata | ✅ | ✅ | ✅ |
| `scan disk` — capacity vs threshold | ✅ | ✅ | ✅ |
| `scan encryption` — full-disk encryption | ⛔ `UNSUPPORTED` (LUKS detection is not in v1) | ✅ `manage-bde -status` | ✅ `fdesetup status` |
| `scan security` — elevation + protection agents | ✅ | ✅ | ✅ |

Encryption parsing assumes the **English** output of `manage-bde` / `fdesetup`.
Unrecognised output is reported as `ERROR`, never as "encrypted".

---

## Install

Recommended (isolated, versioned):

```bash
pipx install .          # or: pipx install endpointctl-0.1.0-py3-none-any.whl
endpointctl --version
```

Standard virtualenv:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install .
```

From a source checkout without installing:

```bash
pip install psutil rich
python3 main.py scan all        # equivalent to: python -m endpointctl scan all
```

Do **not** `git pull` this repository onto endpoints. Install a built wheel
pinned to a version or hash. Rollback is reinstalling the previous wheel.

Development install:

```bash
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check . && mypy
```

`uv.lock` pins the exact resolved versions used by CI.

---

## Usage

```bash
endpointctl scan os           # hostname, OS, version, architecture
endpointctl scan disk         # usage per configured volume vs threshold
endpointctl scan encryption   # BitLocker / FileVault state
endpointctl scan security     # elevation + endpoint-protection processes
endpointctl scan all          # every scan above, best-effort
```

Global options work before or after the subcommand:

| Option | Effect |
|---|---|
| `--json` | Print exactly one JSON object on stdout (the automation contract) |
| `--verbose` | Include raw OS-tool output in the report and log diagnostics to stderr |
| `--quiet` | Suppress human-readable output (JSON still prints when `--json` is given) |
| `--config PATH` | Use a specific `endpointctl.toml` |
| `--log-file PATH` | Write the audit record somewhere other than the default |
| `--no-log` | Do not write an audit record for this invocation |
| `--version` | Print the version |

### Exit codes

A bare `endpointctl` prints help and exits non-zero; findings change the exit
code so cron / Intune / Jamf / systemd can gate on them.

| Code | Meaning |
|---|---|
| `0` | All results `OK` / `INFO` / `UNSUPPORTED` |
| `1` | Usage error, invalid configuration, refused remediation, cancelled, or interrupted |
| `2` | At least one `WARNING` finding (for example disk above threshold, encryption off) |
| `3` | At least one `ERROR` (a check could not be completed) |
| `4` | Unexpected internal failure |

`UNSUPPORTED` deliberately does not fail a run. If your fleet requires
encryption coverage, gate on the JSON `status` field rather than the exit code.

### JSON contract

```bash
endpointctl --json scan all
```

```json
{
  "tool": "endpointctl",
  "version": "0.1.0",
  "status": "WARNING",
  "results": [
    {
      "name": "disk_encryption",
      "status": "WARNING",
      "message": "full-disk encryption is NOT active on C:",
      "data": { "detector": "manage-bde", "encrypted": false, "volumes": [] },
      "error": null
    }
  ]
}
```

Every result has the same five keys. `status` is one of `OK`, `INFO`,
`UNSUPPORTED`, `WARNING`, `ERROR`. The top-level `status` is the worst result in
the report. Raw OS-tool output appears in `data.raw_output` only with
`--verbose`.

Scheduling belongs to the platform, not to this tool — call
`endpointctl scan all --json` from systemd timers, Task Scheduler, Intune or
Jamf.

---

## Configuration

Thresholds, volumes and agent lists are configuration, not literals in the
source. Everything has a safe default, so `endpointctl.toml` is optional.

```toml
[disk]
paths = ["/"]            # default: "/" on POSIX, "C:\\" on Windows
warning_threshold = 85   # 1-99

[encryption]
windows_volumes = ["C:"]

[security]
protection_processes = ["msmpeng", "falcond", "clamd"]

[process]
timeout_seconds = 30     # every OS-tool call has a hard timeout
```

See [docs/configuration.md](docs/configuration.md) for the full reference,
the file search order, and the `ENDPOINTCTL_*` environment overrides.
Invalid configuration fails startup with exit code `1` — values are never
silently clamped.

---

## Safety

* **Scans never modify host state.** They read `psutil` counters and run only
  read-only OS tools (`manage-bde -status`, `fdesetup status`).
* **The `remediate` command is not registered** unless
  `ENDPOINTCTL_ENABLE_REMEDIATION=1` is set in the environment. Without it,
  `endpointctl remediate disk` is an unknown command.
* **Even when enabled, there is no apply path.** `remediate disk` produces a
  preview of files it *would* consider (older than 7 days, not protected by
  name, not symlinks, resolving inside the temp root) and deletes nothing.
  `--apply` is refused.
* **This tool does not enable full-disk encryption.** `remediate encryption`
  explains why and points at the platform's managed workflow. Enabling BitLocker
  or FileVault without escrowed recovery keys is an unrecoverable host-lockout
  risk; there is no rollback.
* **No shell.** Every OS tool is invoked with a fixed argument list, never
  `shell=True`, always with a timeout. A test enforces that no module calls
  `subprocess` outside `endpointctl/process.py`.
* **Privilege checks fail closed.** Elevation is checked with
  `IsUserAnAdmin()` on Windows and `geteuid()` elsewhere; an undeterminable
  result counts as not elevated.
* **Audit log contains no tool output.** One JSON line per invocation with
  timestamp, version, argv, uid/euid, command, aggregate status and exit code.
  Full-disk-encryption tool output is never written to it.

Re-enabling any apply path is a new production review, not a toggle.

---

## Operations

Audit records default to `$XDG_STATE_HOME/endpointctl/endpoint.log`
(`%LOCALAPPDATA%\endpointctl\logs\endpoint.log` on Windows) and rotate at 5 MB
with 3 backups. Full runbook — log locations, failure modes, what to do on
`ERROR`, deployment and rollback — is in
[docs/operations.md](docs/operations.md).

---

## Project structure

```
endpoint-automation/
├── endpointctl/
│   ├── __init__.py          # version
│   ├── __main__.py          # python -m endpointctl
│   ├── cli.py               # argument parsing, exit codes, audit record
│   ├── config.py            # TOML + env configuration with validation
│   ├── models.py            # Status / ScanResult / ScanReport / ExitCode
│   ├── privileges.py        # single elevation check (Windows + POSIX)
│   ├── process.py           # the only subprocess call site; always timed out
│   ├── reporting/
│   │   ├── logger.py        # rotating JSON-lines audit log (no import side effects)
│   │   └── render.py        # Rich and JSON renderers
│   ├── scanner/             # read-only checks; return data, never print
│   │   ├── __init__.py      # scanner registry used by the CLI
│   │   ├── os_info.py
│   │   ├── disk.py
│   │   ├── encryption.py
│   │   └── security.py
│   └── remediation/         # preview-only; no apply path ships
│       ├── base.py          # require_admin / confirm_action building blocks
│       ├── disk.py          # temp-cleanup preview
│       └── encryption.py    # refuses, with guidance
├── docs/
├── tests/                   # pytest suite + recorded OS-tool fixtures
├── main.py                  # source-checkout entry point
├── pyproject.toml
└── uv.lock
```

---

## Testing

```bash
pip install -e ".[dev]"
pytest                     # unit + CLI tests, all host interaction mocked
pytest --cov               # with coverage
ruff check . && ruff format --check . && mypy
```

CI (GitHub Actions) runs lint, mypy, the suite on Python 3.11–3.14 on
Linux plus 3.12 on Windows and macOS, then builds a wheel, installs it into a
clean virtualenv and smoke-tests the console script.

Tests never call real encryption tools, never delete anything, and never run an
apply path. Windows and macOS parsing is locked by recorded fixtures in
`tests/fixtures/`, including the case where a fully decrypted BitLocker volume
must report `encrypted: false`.

---

## Not in v1

Deliberately out of scope until the scan contract has proven itself in
production:

* Enabling full-disk encryption, or any destructive remediation
* Linux LUKS/dm-crypt detection (planned next; today Linux returns `UNSUPPORTED`)
* CSV export and a richer severity model
* REST API / Web UI, ITSM integrations, an in-process scheduler
* Signed releases and an internal package feed

---

## Disclaimer

This project is provided as-is for endpoint health reporting. Validate scan
results against your own platform tooling before relying on them for compliance
decisions.

**Author:** Novrus Shehaj
