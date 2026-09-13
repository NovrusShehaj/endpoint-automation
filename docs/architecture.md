# Architecture

`endpointctl` is a one-shot CLI. There is no service, queue, database or
scheduler in this repository, and adding one is explicitly out of v1 scope.

```
endpointctl scan all --json
  └── cli.main
        ├── config.load_config          TOML + env, validated, fails startup on error
        ├── reporting.logger            handlers installed here (never at import)
        ├── scanner.run_scan(target)    registry lookup, best-effort for "all"
        │     ├── scanner.os_info.check_os
        │     ├── scanner.disk.check_disk          psutil.disk_usage per configured path
        │     ├── scanner.encryption.check_encryption
        │     │     └── process.run_os_tool        fixed argv, hard timeout, no shell
        │     └── scanner.security.check_security
        │           └── privileges.elevation       shared with remediation preflight
        ├── reporting.render            Rich text or JSON
        └── reporting.logger.audit      one JSON line per invocation
```

## Rules the code follows

1. **Scanners return data, never print.** Every check returns a `ScanResult`
   (`models.py`). Presentation lives only in `reporting/render.py`, so the same
   result renders as Rich text or JSON without duplicated logic. A test asserts
   scanners produce no stdout.
2. **One result schema.** `name`, `status`, `message`, `data`, `error`. The
   aggregate status of a report is the worst result in it, and the exit code is
   derived from that single value.
3. **One subprocess call site.** `process.run_os_tool` is the only place that
   calls `subprocess`, always with a fixed argv, `shell=False` and a timeout. A
   test walks the AST of every module to enforce this.
4. **One elevation check.** `privileges.elevation()` backs both the security
   scan finding and remediation preflight, and fails closed when it cannot
   determine the answer.
5. **Import is side-effect free.** No module creates directories, opens files or
   logs at import time. Logging is configured in `cli.main`.
6. **Remediation is not imported by a scan.** `cli._handle_remediate` imports
   the remediation modules inside the branch, so state-changing code is never
   loaded during a scan.
7. **Configuration, not literals.** Thresholds, volumes, agent names and
   timeouts come from `config.py`.

## Adding a scanner

Write a function taking a `Config` and returning a `ScanResult`, then register
it in `endpointctl/scanner/__init__.py`:

```python
SCANNERS: dict[str, Callable[[Config], ScanResult]] = {
    ...,
    "firewall": check_firewall,
}
```

The CLI reads its choices from `SCAN_TARGETS`, so no argparse change is needed,
and `scan all` picks the new check up automatically. If the check shells out to
an OS tool, use `run_os_tool` and add recorded output fixtures under
`tests/fixtures/` — CI must never invoke the real tool.
