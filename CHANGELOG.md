# Changelog

All notable changes to this project are documented here. This project follows
[Semantic Versioning](https://semver.org/); it is pre-1.0, so the CLI contract
may still change between minor versions.

## [0.1.0] — Unreleased

First production-readiness pass. The tool is now **scan-only**: previous
versions shipped live remediations that could delete the contents of `/tmp` and
`/var/tmp` or enable BitLocker/FileVault behind nothing but a typed `yes`.

### Security

* `remediate` is no longer registered on the default command line. It appears
  only when `ENDPOINTCTL_ENABLE_REMEDIATION=1` is set, and even then it cannot
  apply changes: the temp-file cleanup is preview-only and `--apply` is refused.
* Removed all deletion code from the temp-cleanup path. The preview filters by
  age (7 days minimum), skips protected names and symlinks, and requires each
  candidate to resolve inside its temp root.
* Full-disk-encryption enablement is no longer callable. `manage-bde -on` and
  `fdesetup enable` are not executed by this tool; the command explains the
  recovery-key escrow requirement instead.
* Elevation is now checked on Windows with `IsUserAnAdmin()` instead of being
  skipped, and fails closed when it cannot be determined.
* Every OS-tool call goes through a single helper with a fixed argv, no shell
  and a hard timeout.

### Fixed

* **BitLocker false positive:** encryption detection tested whether the strings
  `on` or `encrypted` appeared anywhere in `manage-bde` output, which matched
  `Protection Off` and `Percentage Encrypted: 0.0%`. A fully decrypted Windows
  volume was reported as encrypted. Detection now parses the documented
  `Protection Status` field, and unrecognised output is `ERROR`, never a guess.
* FileVault detection now matches the documented `FileVault is On/Off.`
  sentence, including the deferred-enablement and in-progress variants.
* Non-zero exit codes, missing binaries and timeouts from OS tools are reported
  as `ERROR` instead of being read as "not encrypted".
* Disk usage no longer hardcodes `/`; the default is OS-correct and the paths
  and threshold are configuration.
* `scan security` no longer aborts when a process is inaccessible, and matches
  agent names exactly instead of substring-searching a concatenation of every
  process name.
* `enable_encryption` raised `NameError` on Linux (`RunTimeError`); unsupported
  paths now raise a typed error.
* Module-level `logger.info("... completed")` calls that fired on import and
  claimed scans had run were removed.
* A bare invocation now prints help and exits non-zero instead of doing nothing
  and exiting 0.
* Cancellation, EOF on a non-interactive stdin and Ctrl-C no longer produce
  tracebacks.

### Added

* `scan os` as a first-class target; `scan all` is best-effort and reports every
  scanner's result even when one fails.
* `--json` automation contract, `--version`, `--verbose`, `--quiet`,
  `--config`, `--log-file`, `--no-log`; global flags work before or after the
  subcommand.
* Documented exit codes: 0 ok, 1 usage/refused, 2 warning, 3 error, 4 unexpected.
* Single result schema (`ScanResult`/`ScanReport`) and a scanner registry, so a
  new check needs no argparse change.
* Configuration layer (`endpointctl.toml` + `ENDPOINTCTL_*` env overrides) with
  validation that fails startup rather than clamping.
* Rotating JSON-lines audit log with one record per invocation (version, argv,
  uid/euid, command, status, exit code, duration). OS-tool output is never
  logged.
* Packaging: `pyproject.toml` (hatchling), `uv.lock`, `endpointctl` console
  script, `python -m endpointctl`, `__version__`.
* Test suite (pytest) with recorded `manage-bde`/`fdesetup` fixtures, plus
  static guards against `shell=True`, direct `subprocess` use and any delete
  call in the remediation package.
* GitHub Actions CI: ruff, ruff format, mypy, tests on Linux 3.11-3.14 and
  Windows/macOS 3.12, plus a wheel build and clean-venv smoke test.
* Documentation: rewritten README, operations runbook, configuration reference,
  architecture notes and open decisions.
* `.gitignore`; bytecode and the stale `logs/endpoint.log` are no longer tracked.

### Known limitations

* Linux full-disk-encryption detection is not implemented; `scan encryption`
  returns `UNSUPPORTED` on Linux rather than guessing.
* Windows and macOS behaviour is verified against recorded fixtures, not on
  hardware.
* Encryption parsing assumes English tool output.
* No `LICENSE` file yet — see [docs/open-questions.md](docs/open-questions.md).
