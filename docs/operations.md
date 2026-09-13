# Operations runbook

Audience: whoever runs `endpointctl` across a fleet and gets paged when it
reports something.

## What this tool is

A one-shot, read-only CLI executed on an endpoint. There is no daemon, no
server, no database, and no central state. It exits with a code, prints a
report, and writes one audit line.

## Invocation

```bash
endpointctl --json scan all
```

Schedule it with the platform you already run (systemd timer, Task Scheduler,
Intune, Jamf). Do not build a scheduler around it and do not run it in a tight
loop — `scan security` enumerates every process on the host.

## Exit codes

| Code | Meaning | Operator action |
|---|---|---|
| 0 | All results `OK` / `INFO` / `UNSUPPORTED` | None |
| 1 | Usage error, invalid config, refused remediation, cancelled/interrupted | Fix the command line or `endpointctl.toml` |
| 2 | At least one `WARNING` | Triage the finding (disk full, encryption off, no protection agent) |
| 3 | At least one `ERROR` | A check could not complete — see below |
| 4 | Unexpected internal failure | File a bug with the audit record and stderr |

`UNSUPPORTED` does not fail the run. On Linux, `scan encryption` is always
`UNSUPPORTED` in v1; gate on the JSON `status` field if you need encryption
coverage enforced.

## Failure modes and what to do

| Symptom | Cause | Action |
|---|---|---|
| `disk_encryption` `ERROR`: "manage-bde is not available" | Tool missing or not on `PATH` (also happens in a non-admin container) | Run on a real Windows endpoint; confirm `manage-bde` exists |
| `disk_encryption` `ERROR`: "exited with status N: Access is denied" | `manage-bde -status` needs elevation for that volume | Run the scan elevated, or scope `encryption.windows_volumes` |
| `disk_encryption` `ERROR`: "no 'Protection Status' field" | Non-English locale or an unexpected tool version | Report the raw output (`--verbose`); do **not** assume encrypted |
| `disk_encryption` `ERROR`: "timed out" | Tool hung | Raise `process.timeout_seconds`; check the host |
| `disk_usage` `ERROR` | Configured path does not exist on this image | Fix `disk.paths` for that image |
| `security_baseline` `WARNING` with a high `inaccessible_processes` count | Scan is unelevated, so many processes are unreadable | Re-run elevated before concluding the agent is missing |
| `security_baseline` `WARNING` on a host that does have an agent | The agent's process name is not in the default list | Add the exact normalised name to `security.protection_processes` |
| Exit 1 with "configuration error" | Invalid `endpointctl.toml` | Values are never clamped; fix the file |

## Logging and audit

* Default location: `$XDG_STATE_HOME/endpointctl/endpoint.log`
  (fallback `~/.local/state/endpointctl/endpoint.log`);
  `%LOCALAPPDATA%\endpointctl\logs\endpoint.log` on Windows.
* Override with `--log-file PATH` or `ENDPOINTCTL_LOG_FILE`; disable with `--no-log`.
* Rotating: 5 MB per file, 3 backups (configurable). It cannot grow unbounded.
* Format: one JSON object per line.

```json
{"ts":"2026-09-13T16:38:12.421Z","level":"INFO","logger":"endpointctl",
 "message":"invocation","audit":true,"version":"0.1.0","hostname":"host-01",
 "argv":["scan","all"],"pid":1234,"uid":1000,"euid":1000,"user":"ops",
 "command":"scan","target":"all","status":"WARNING","exit_code":2,"duration_ms":24.5}
```

**Never logged:** raw `manage-bde` / `fdesetup` output (it can contain volume
identifiers and key-protector hints), process listings, and file contents. If a
log destination is unwritable the run continues and reports the reason on
stderr — a logging failure never fails a scan.

Importing the package writes nothing. If you see a `logs/` directory appear
next to your working directory, that is an old version.

## Deployment and rollback

1. CI builds a wheel.
2. Install per endpoint with `pipx install` (or your package manager) from a
   pinned version or hash. Never `git pull` onto endpoints.
3. Rollback = reinstall the previous wheel. Because v1 is scan-only there is no
   host state to restore and no migration to reverse.
4. Verify after deploy: `endpointctl --version` and
   `endpointctl --json scan os` (exit 0).

## Privileges

Scans run unelevated. Running elevated improves two results:

* Windows `manage-bde -status` may require elevation on some volumes.
* `scan security` can read more process names, lowering `inaccessible_processes`.

Elevation is reported, never assumed: `admin_privileges.elevated` is `true`,
`false`, or `null` when it cannot be determined.

## Remediation

There is none in v1. The `remediate` command is not registered unless
`ENDPOINTCTL_ENABLE_REMEDIATION=1` is set, and even then it only previews. No
`endpointctl` command deletes a file or enables full-disk encryption.

If a future release proposes an apply path, it needs: recovery-key escrow for
FDE, proof of elevation, a dry-run preview, non-zero return-code handling, a
per-action audit record, a canary ring, and a lockout runbook. That is a new
production review.
