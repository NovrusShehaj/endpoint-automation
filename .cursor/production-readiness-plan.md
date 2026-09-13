# Endpoint-Automation Production Readiness Plan

Audit date: 2026-09-13
Auditor scope: read-only inspection of `/home/ghost/Github/endpoint-automation` on `dev/production-readiness`, plus safe diagnostics. No application code, dependencies, infrastructure, or git history was modified except this file.

## 1. Executive Summary

Endpoint-Automation is a small local Python CLI (`python3 main.py`) that performs host scans (OS metadata, disk usage, disk-encryption heuristics, process-based “security baseline”) and also exposes **live remediations** that can delete the contents of `/tmp` and `/var/tmp` or invoke OS full-disk-encryption enablement.

The repository is **not production-ready**. The README presents a scan-only, enterprise-safe tool with planned remediations and tests. The code on this branch already wires `remediate disk` and `remediate encryption` with insufficient privilege checks, no dry-run, no success detection, no timeouts, and no audit of the actions themselves. Core scan results are also incorrect or platform-wrong (Windows BitLocker detection will treat typical `manage-bde` text as encrypted; disk usage always inspects `"/"`; Windows admin detection is broken).

There is no packaging manifest, lockfile, test suite, CI, `.gitignore`, license, config layer, or installable entry point. Runtime dependencies (`psutil`, `rich`) are imported but undeclared. On this audit host, system Python 3.14 has `psutil` 7.0.0 as a distro package and **does not** have `rich`, so `endpointctl.cli` cannot be imported until `rich` is installed.

**Recommended production posture for v1:** ship **scan-only**, with remediations disabled or removed from the default CLI. Do not enable BitLocker/FileVault from this tool until recovery-key escrow, privilege proof, dry-run, and return-code handling exist. Then make scan results truthful, package the CLI, and add tests/CI before any fleet use.

Priority counts in this plan (grouped tasks, not every line-level nit):

| Priority | Count | Meaning |
|---|---|---|
| P0 Release Blocker | 2 | Destructive or privilege-unsafe remediations that can harm a host |
| P1 Production Critical | 6 | Wrong security/health answers, undeployable package, no tests/CI, docs that contradict safety |
| P2 Production Important | 7 | CLI contract, config, logging, repo hygiene, subprocess timeouts, maintainability |
| P3 Enhancement | 5 | Exports, Linux LUKS, scheduling, API/ITSM, release signing |

## 2. Current State

### Repository / Branch

| Item | Evidence |
|---|---|
| Root | `/home/ghost/Github/endpoint-automation` |
| Remote | `.git/config` `remote.origin.url` = `git@github.com:NovrusShehaj/endpoint-automation.git` |
| Current branch | `.git/HEAD` → `refs/heads/dev/production-readiness` |
| Branch tip | `4c80a95477f691df077e0ad4b29d4edc752edfac` (`.git/refs/heads/dev/production-readiness`) |
| `master` tip | same SHA (`.git/refs/heads/master`) |
| `origin/master` | same SHA (`.git/packed-refs`) |
| Branch tracking | `[branch "dev/production-readiness"]` in `.git/config` has only `vscode-merge-base = origin/master`. No `remote` / `merge` tracking. This branch is local-only. |
| How the branch was created | `.git/logs/HEAD` and `.git/logs/refs/heads/dev/production-readiness`: clone from GitHub onto `master`, then checkout/create `dev/production-readiness` from that tip. No additional commits are referenced locally. |
| Visible remotes | `.git/refs/remotes/origin/HEAD` → `origin/master` only. No `origin/dev/production-readiness`. |
| `.gitignore` | **Absent** (glob over repository root). |
| Working tree at audit start | User-verified clean. This audit adds only `.cursor/production-readiness-plan.md`. |

**Git CLI limitation:** `git status`, `git log`, `git ls-files`, `git rev-parse`, and pack `strings` were blocked in this environment. Commit subject/body for `4c80a95477f691df077e0ad4b29d4edc752edfac` is therefore **unknown**. History reconstruction is limited to reflogs, `packed-refs`, and the working tree.

**Tracked-vs-present tree (all non-`.git` paths observed):**

```
main.py
README.md
logs/endpoint.log
endpointctl/cli.py
endpointctl/scanner/__init__.py
endpointctl/scanner/os_info.py
endpointctl/scanner/disk.py
endpointctl/scanner/encryption.py
endpointctl/scanner/security.py
endpointctl/reporting/logger.py
endpointctl/remediation/base.py
endpointctl/remediation/disk.py
endpointctl/remediation/encryption.py
endpointctl/__pycache__/cli.cpython-314.pyc
endpointctl/scanner/__pycache__/*.cpython-314.pyc
endpointctl/reporting/__pycache__/logger.cpython-314.pyc
endpointctl/remediation/__pycache__/*.cpython-314.pyc
```

Missing relative to README “Project Structure”: `endpointctl/__init__.py`, `tests/`, `venv/`.

Bytecode filenames `*.cpython-314.pyc` and `/usr/bin/python3 → python3.14` show the only observed runtime is **CPython 3.14**.

### Architecture Overview

This is a **single-host CLI**, not a service. There is no HTTP API, queue, database, container, or orchestrator in the tree.

```
python3 main.py
  └── endpointctl.cli.run()                         # argparse + rich printing
        ├── scan {disk,encryption,security,all}
        │     ├── scanner.os_info.scan_os()         # print-only; used only by "all"
        │     ├── scanner.disk.check_disk()         # psutil.disk_usage("/")
        │     ├── scanner.encryption.check_encryption()  # manage-bde / fdesetup
        │     └── scanner.security.check_security() # euid + process-name heuristic
        └── remediate {disk,encryption}
              ├── remediation.disk.cleanup_temp()   # deletes /tmp and /var/tmp entries
              └── remediation.encryption.enable_encryption()  # manage-bde -on / fdesetup enable
                    └── remediation.base.require_admin + confirm_action
```

Cross-cutting: `endpointctl.reporting.logger` configures `logging.basicConfig` to `logs/endpoint.log` **at import** and creates `logs/`.

Dependency direction is flat and inward-broken:

- CLI imports scanners **and** remediations unconditionally (`endpointctl/cli.py` lines 4–9). A scan invocation still loads encryption-enablement code.
- Scanners import `rich` and print, so “scan” is not a pure detection layer.
- Only `endpointctl/scanner/__init__.py` exists. `endpointctl`, `reporting`, and `remediation` rely on implicit namespace packages.
- No config, models, result schema, plugin registry, or version module.

Declared/used third-party libraries (from source + README, **not** from a manifest):

| Library | Where used | Declared? |
|---|---|---|
| `rich` | `cli.py`, `os_info.py`, `disk.py` | No. **Not installed** in `/usr/lib/python3.14/site-packages` or `/usr/lib64/python3.14/site-packages` on the audit host. |
| `psutil` | `scanner/disk.py`, `scanner/security.py` | No. Present as distro `psutil-7.0.0` under `/usr/lib64/python3.14/site-packages/psutil-7.0.0.dist-info`. |

Stdlib used: `argparse`, `platform`, `socket`, `subprocess`, `os`, `shutil`, `pathlib`, `logging`.

### Validation Performed

Read every application module and `README.md`. Inspected `.git/HEAD`, `.git/config`, reflogs, `packed-refs`, directory listings, `__pycache__` names, `logs/endpoint.log` (no secrets present; messages only), and host site-packages for `psutil` / `rich`. Grep for remediations, subprocess, exception handling, config, and TODO/FIXME (none of the latter in `.py` files).

| Command / check | Result |
|---|---|
| `ls -la` repository and package dirs | Success. Tree as listed above. No `.github/`, `pyproject.toml`, `requirements*.txt`, `setup.py`, `tests/`, `Dockerfile`, `LICENSE`, `.gitignore`. |
| Read all `*.py` and `README.md` | Success. Full contents inspected. |
| `ls` `__pycache__` | Success. All modules compiled as `cpython-314`. |
| Read `logs/endpoint.log` | Success. Only `OS Information Retrieved` and `Disk scan completed`. Tight timestamps (1–12 ms pairs) match **import-time** logging, not completed scans. |
| `ls` Python 3.14 site-packages | Success. `psutil` 7.0.0 present. `rich` absent. |
| `ls /usr/bin/python3 /usr/bin/git /usr/bin/gh` | Success. `python3` → `python3.14`; `git` and `gh` exist. |
| `git status`, `git log`, `git ls-files`, `git rev-parse` | **Blocked** by environment. |
| `python3 --version`, `python3 -m py_compile …`, `/usr/bin/python3 --version` | **Blocked**. Syntax of sources was reviewed by reading files; runtime import was **not** executed. |
| `find`, `wc`, `strings` on git pack | **Blocked**. |
| Web search of the GitHub repo | **Rejected**. |
| pytest / ruff / mypy / pre-commit | **Not present** in the repo. No config to run. `/usr/bin/*pytest*` did not exist. |
| Dependency install / upgrade | **Not run** (out of scope). |

**Important limitation:** this plan cannot claim “tests passed/failed” or “import succeeds on a clean venv” because those commands were blocked or impossible without installing `rich`. Findings below are grounded in source text and host filesystem evidence.

### Current Strengths

- Small, readable surface (~11 Python modules). A later agent can change behavior without a rewrite.
- Scan vs remediate is at least split into `endpointctl/scanner/` and `endpointctl/remediation/`.
- Encryption **scan** wraps `subprocess.run` in `try/except` and returns a dict (`check_encryption`).
- `confirm_action` requires the literal string `yes` (`remediation/base.py` lines 13–16), which is stricter than a single `y`.
- Non-Windows remediations call `os.geteuid()` before acting (`require_admin`).
- Encryption scan uses argument lists, not `shell=True`.
- README states the right design goals (read-only default, OS-aware, auditable, extensible) even though the implementation does not meet them.

### Major Production Risks

1. **`remediate disk` deletes every file and directory it can under `/tmp` and `/var/tmp`.** That can break other processes, other users, and the host. Failures are swallowed.
2. **`remediate encryption` runs `manage-bde -on c:` or `fdesetup enable` after an interactive `yes`.** No recovery-key handling, no return-code check, no timeout. On Windows, admin is not required by this program.
3. **Encryption scan on Windows is effectively a false-positive machine:** `"on" in stdout` matches the substring inside `Protection`, and `"encrypted" in stdout` matches `Percentage Encrypted` even at 0%.
4. **Security and disk scans will give wrong answers on Windows** (euid/getuid path; always `"/"`).
5. **Nothing is packaged or tested.** Fleet install, rollback, and regression detection do not exist.
6. **Operators who trust the README will believe remediations are not live.** They are.

## 3. Audit Findings

Each finding is labeled **confirmed issue**, **likely risk**, **assumption**, **open question**, or **optional enhancement**.

### Functionality and Correctness

**Confirmed issue — module-level “scan completed” logs never record a scan.** In `endpointctl/scanner/os_info.py` line 21, `logger.info("OS Information Retrieved")` is indented at module scope after `scan_os`. In `endpointctl/scanner/disk.py` line 20, `logger.info("Disk scan completed")` is likewise outside `check_disk`. Both fire on import. `logs/endpoint.log` pairs those two lines a few milliseconds apart, which matches import of `cli.py` (lines 4 and 7), not user-visible scan completion.

**Confirmed issue — `scan_os` is not a CLI target and returns nothing.** `cli.py` scan choices are `disk|encryption|security|all` (lines 23–27). `scan_os()` is only invoked from `all` (line 52) and prints internally; it does not return the `info` dict. A caller cannot consume OS metadata programmatically.

**Confirmed issue — disk scan is not OS-aware.** `check_disk` (`scanner/disk.py` lines 8–18) always uses `psutil.disk_usage("/")` and a hardcoded 85% warning threshold. On Windows that path is the wrong volume. The function also `console.print`s a line and then the CLI `console.print`s the returned dict (`cli.py` lines 40–41), so disk output is duplicated.

**Confirmed issue — Windows encryption detection is the wrong predicate.** `check_encryption` (`scanner/encryption.py` line 26):

```python
encrypted = "on" in result.stdout.lower() or "encrypted" in result.stdout.lower()
```

Typical `manage-bde -status` text includes `Protection On/Off` and `Percentage Encrypted`. `"on"` is a substring of `protection`; `"encrypted"` matches `Percentage Encrypted: 0.0%`. A fully decrypted Windows volume with standard output will still be reported as `encrypted: True`.

**Likely risk — macOS encryption parse is accidental, not specified.** `fdesetup status` usually prints `FileVault is On.` / `FileVault is Off.`. The `"on"` substring happens to distinguish those two strings, but any extra line containing `on` or `encrypted` flips the result. There is no parse of a documented field.

**Confirmed issue — subprocess success is ignored on scans and remediations.** `scanner/encryption.py` lines 20–24 and `remediation/encryption.py` line 18 call `subprocess.run` without `check=True`, without inspecting `returncode`, and without `timeout`. A missing-tool path is handled (`FileNotFoundError` → `status: ERROR`). A present tool that fails (not elevated, stderr-only) returns `encrypted: False` with empty `raw_output`, or a remediation dict that looks like success.

**Confirmed issue — Linux encryption remediate raises the wrong exception name.** `enable_encryption` else branch (`remediation/encryption.py` line 16) is `raise RunTimeError(...)`. The builtin is `RuntimeError`. That path is a `NameError`, not a controlled unsupported-OS error.

**Confirmed issue — security process enumeration can throw and abort the CLI.** `check_security` (`scanner/security.py` line 26) does `p.name()` for every `psutil.process_iter()` result with no `attrs=` and no per-process exception handling. `AccessDenied` / `ZombieProcess` from psutil will fail the entire `scan security` / `scan all` command.

**Confirmed issue — admin finding is wrong on Windows.** Line 9: `os.geteuid() == 0 if hasattr(os, "getuid") else False`. Windows CPython typically has neither `getuid` nor `geteuid`, so `enabled` is always `False`. The comment says “privilege level” (and misspells it `privilage`).

**Confirmed issue — endpoint-protection check is a substring over a concatenated name string.** Lines 17–27 join every process name with spaces, then test whether `defender`, `msmpeng`, `falcon`, `cortex`, `sentinel`, or `crowdstrike` appear anywhere in that blob. That both misses Linux agents (`clamd`, `osqueryd`, `falcon-sensor` may or may not match `falcon`) and can match unrelated processes (`sentinel` is a common token). `platform` is imported and unused (line 1).

**Confirmed issue — `cleanup_temp` is a recursive wipe, not a temp cleanup.** `remediation/disk.py` lines 9–24 iterate `/tmp` and `/var/tmp`, `unlink` files, and `shutil.rmtree` directories. There is no age filter, allowlist, Windows `%TEMP%` path, skip of sockets/sticky-bit-safe names, or record of failures (`except Exception: pass`). On Windows those Unix paths usually do not exist, so after confirmation the action is a successful no-op (`removed_items: 0`).

**Confirmed issue — CLI does nothing useful with no subcommand.** `add_subparsers(dest="command")` (`cli.py` line 20) is not `required=True`. `python3 main.py` parses, then both `if` branches are false, and `run()` returns. No help, no error, no non-zero exit.

**Confirmed issue — `RemediationError` is not handled.** Cancel (`confirm_action`) or non-admin (`require_admin` on Unix) raises `RemediationError`. `cli.run` does not catch it. The user gets a traceback; process exit code is Python’s uncaught-exception status, not a defined operational code.

**Confirmed issue — scan result schemas are inconsistent.** Disk returns `{disk_usage, status}`; encryption success returns `{metric, encrypted, raw_output}` but unsupported/error uses `{metric, status, ...}`; security returns `{metric, findings}`; OS prints keys and returns `None`. `scan all` does not produce one document.

**Confirmed issue — remediations are not idempotent and do not preflight.** `enable_encryption` does not check current encryption state. Re-running `manage-bde -on` / `fdesetup enable` is undefined here. `cleanup_temp` can partially delete (some `unlink`/`rmtree` fail silently) and still return a count that looks complete.

**Likely risk — `fdesetup enable` with `capture_output=True` will hang or fail.** FileVault enablement is interactive (password / recovery). Capturing stdio hides prompts. Labeled likely because this host is Linux and the command was not executed.

**Open question — intended warning threshold and which volumes matter.** 85% on `/` only is the entire disk product today.

### Architecture and Design

**Confirmed issue — presentation is mixed into detection.** `scan_os` and `check_disk` construct `rich.console.Console` and print. CLI also prints. Tests cannot assert results without capturing stdout and mocking Rich.

**Confirmed issue — no extension point despite README “new scanners can be added easily”.** Adding a scan requires editing `cli.py` choices and branches. `scanner/__init__.py` re-exports four functions but CLI does not use that façade (it imports each module). There is no scanner protocol, registry, or severity type.

**Confirmed issue — remediation is loaded on every process start.** `cli.py` lines 8–9 import `cleanup_temp` and `enable_encryption` before argument parsing. A future plugin/load bug or accidental call is one function away from destructive OS commands.

**Confirmed issue — no domain model.** Status strings are ad hoc (`OK`, `WARNING`, `INFO`, `UNSUPPORTED`, `ERROR`). Encryption success omits `status`. Callers cannot sort or gate on a single enum.

**Confirmed issue — config is not a layer.** Thresholds, paths, process names, and encryption commands are literals inside functions. There is no `config.py`, env schema, or profile for lab vs production.

**Confirmed issue — package is not a package.** Missing `endpointctl/__init__.py`, `endpointctl/reporting/__init__.py`, `endpointctl/remediation/__init__.py`. Import works as a namespace package when cwd is on `sys.path` (`main.py` line 1). It will not install cleanly as a wheel without a build backend and package declaration.

**Optional enhancement — do not introduce FastAPI, ITSM, or an orchestration layer** (README “Next Steps”) until scan contracts, safety gates, and tests exist. Those would multiply the same bugs.

### Security

**Confirmed issue — Windows remediations skip the privilege check.** `require_admin` (`remediation/base.py` lines 7–10):

```python
if platform.system() != "Windows":
    if os.geteuid() != 0:
        raise RemediationError("Administrator privileges required")
```

On Windows the function returns without checking elevation. `enable_encryption` then runs `manage-bde -on c:`. This is a privilege-boundary defect in *this* program (OS may still refuse the command). Combined with no return-code check, a non-admin Windows run can look like a completed action.

**Confirmed issue — confirmation is not an authorization control.** `confirm_action` reads stdin. Any local user who can run the CLI and type `yes` (or pipe `yes`) gets remediations, subject only to Unix euid on non-Windows. There is no `--dry-run`, approval token, allowlist of hosts, or operator identity in the log.

**Confirmed issue — disk remediation is a destructive filesystem operation without path safety.** `cleanup_temp` deletes children of `/tmp` and `/var/tmp`. If those paths were ever parameterized from user input without resolution checks, this would be path traversal; today they are hardcoded, so the issue is **unsafe privileged delete**, not injection. `except Exception: pass` hides EPERM/EBUSY and continues.

**Confirmed issue — encryption enablement has no key-escrow or recovery step.** Commands are exactly `["manage-bde", "-on", "c:"]` and `["fdesetup", "enable"]` (`remediation/encryption.py` lines 12–14). No `-RecoveryPassword`, no recovery-key file, no escrow to an MDM/AD/ITSM record. Enabling FDE from a self-service CLI without escrow is a host-lockout and data-loss class event.

**Confirmed issue — command execution is fixed-argv today, but unguarded.** Both `subprocess.run` call sites use lists (good: no `shell=True`). There is still no timeout, no cwd lock-down, no allowlist wrapper, and no logging of the command/result. `raw_output` / `stdout` / `stderr` are printed via Rich (`cli.py` lines 66, 70), so encryption tool output (which can include volume identifiers and protector hints) goes to the terminal. No secrets were observed in current logs; **future** BitLocker output could include recovery material — treat as a **likely risk** if remediations stay enabled.

**Confirmed issue — README safety claims are false.** README lines 123–129 say remediations are not performed by default, encryption checks are detect-only, and “platform-specific commands are wrapped safely.” `cli.py` lines 29–34 and 63–70 expose remediations. Wrappers do not check return codes or Windows admin.

**Likely risk — process listing is a local information leak and an unreliable control.** Concatenating every process name is fine for a local admin tool; publishing that blob (`raw` is not currently returned for security, only a boolean) is not done. The **control-quality** risk is false `OK` for endpoint protection.

**Assumption — no network/SSRF surface.** No HTTP client, no URL parameters, no server. Do not treat this as a networked app until one is added.

**Assumption — no deserialization / pickle / YAML load.** None in source.

**Open question requiring verification — whether `manage-bde`/`fdesetup` output on real hosts ever includes recovery keys when invoked as this code does.** Scan uses `-status` / `status` (low risk). Remediate uses `-on` / `enable` (higher risk). Do not log stdout at INFO until verified.

**Optional enhancement — do not add telemetry that ships process lists or hostnames off-box** without a data-handling decision.

### Reliability and Resilience

**Confirmed issue — no timeouts.** Any hang in `manage-bde`, `fdesetup`, or `psutil.process_iter` hangs the CLI forever.

**Confirmed issue — no startup validation.** Missing `psutil`/`rich`, unwritable `logs/`, or non-tty stdin for `input()` fail late (import, first log, or first remediate).

**Confirmed issue — logger import fails the process if `logs/` cannot be created.** `reporting/logger.py` lines 4–5: `Path("logs").mkdir(exist_ok=True)` with no `parents` (ok if cwd exists) and no permission handling. Import of `os_info` or `disk` pulls this in. CWD-relative path means two invocations from different directories create two log files and never rotate.

**Confirmed issue — swallowed remediation errors.** `cleanup_temp` lines 23–24. Partial failure is indistinguishable from success except a lower `removed_items` count.

**Confirmed issue — no graceful shutdown or signal handling.** Mid-wipe or mid-`manage-bde` Ctrl-C leaves the host in an undefined state. Not caught in `cli.run`.

**Confirmed issue — crash/restart does not recover or record in-flight remediations.** There is no journal, lockfile, or action id.

**Likely risk — `input()` in non-interactive automation.** EOF raises `EOFError` (not `RemediationError`), another uncaught traceback. CI or MDM wrapper cannot safely call `remediate`.

**Confirmed issue — no retries/backoff, and none are needed for local scans if commands are given timeouts and return-code handling.** Do not add retry-on-FDE-enable.

### Performance and Scalability

This is a per-endpoint CLI. Throughput/scaling of a server is **not applicable**. Avoid premature optimization.

**Confirmed issue — unbounded log file.** `logging.basicConfig` to a single file, no `RotatingFileHandler`. Long-lived scheduled use (README “cron / Task Scheduler”) would grow `logs/endpoint.log` without bound. Current file is 1569 bytes.

**Likely risk — `process_iter()` + `name()` on every process** is acceptable for an interactive scan; it is the wrong primitive if this is later looped at high frequency. Not a v1 blocker.

**Confirmed issue — blocking I/O on subprocess and stdin** is expected for a CLI; missing timeouts make it a reliability issue, not a performance issue.

**Assumption — memory is bounded** because there are no caches or queues. The concatenated process-name string is O(number of processes). Fine for a workstation.

### Testing and QA

**Confirmed issue — zero tests.** No `tests/` directory, no `test_*.py`, no `pytest.ini`, no CI workflow. README lines 149–157 list pytest, mocks, CLI tests, and linting as future work.

**Confirmed issue — current code is hostile to unit tests.** Import creates `logs/` and writes two INFO lines. Scanners print. Remediations call `input()` and real OS tools. `cleanup_temp` would be catastrophic if accidentally invoked against a real `/tmp` in a privileged CI runner.

**Production behaviors with no automation today:**

- Disk threshold classification
- Windows vs Darwin vs other encryption parse
- Security process matching and AccessDenied resilience
- CLI routing, help, exit codes
- `require_admin` on Windows vs Unix
- `confirm_action` accept/reject/EOF
- Remediation **must not** run against a real host in CI (need dry-run or injected runner)

**Confirmed issue — no lint/format/type/static config.** No ruff, flake8, mypy, pyright, pre-commit. `ReadLints` was not used (no edits to application files). Static review found unused `platform` import, `RunTimeError` typo, trailing space in `disk.py` line 2, and the indent bugs above — none of these are gated in CI.

**Flakiness:** if tests were added naively against live `psutil` and `/`, they would vary by host. Any real-`/tmp` test would be non-deterministic and dangerous.

### Observability and Operations

**Confirmed issue — logs are not an audit trail.** Only two import-time INFO strings. No hostname, argv, target, result, user, euid, return code, or correlation/request id. Encryption and security scans do not log. Remediations do not log.

**Confirmed issue — log format is not structured.** `%(asctime)s - %(levelname)s - %(message)s` (`logger.py` line 10). No JSON, no `extra` fields.

**Confirmed issue — no metrics, tracing, health, readiness, or liveness.** Appropriate **until** someone turns this into a daemon. For a CLI, the substitutes are: non-zero exit codes, machine-readable `--json`, and an audit log line per invocation.

**Confirmed issue — operator cannot alert on scan WARNING.** `check_disk` returns `status: WARNING` but `cli.run` always exits 0 on success. Fleet jobs cannot gate on disk/security findings.

**Confirmed issue — committed `logs/endpoint.log` is a stale development artifact** (dates 2026-02-04). It will confuse operators and pollute clones.

### Configuration and Environment Management

**Confirmed issue — no environment or config module.** No `os.getenv`, no file, no `--config`, no feature flags. Dev and prod are the same: live remediations if the user types `remediate`.

**Confirmed issue — hardcoded production-impacting values:**

| Value | Location |
|---|---|
| Disk path `"/"` | `scanner/disk.py` line 8 |
| Threshold `85` | `scanner/disk.py` line 11 |
| Process name list | `scanner/security.py` lines 17–24 |
| Temp dirs `/tmp`, `/var/tmp` | `remediation/disk.py` line 9 |
| BitLocker target `c:` | `remediation/encryption.py` line 12 |
| Log dir `logs` relative to CWD | `reporting/logger.py` lines 4–8 |

**Confirmed issue — secrets separation is unused and unplanned.** No credentials today. If ITSM/API keys are added later, there is no pattern (env, keyring, or file mode) to follow.

**Confirmed issue — silent unsafe default.** Remediation is one subcommand away with only a yes prompt. README tells the reader the opposite.

**Open question — Python version support.** Bytecode and host are 3.14. Enterprise images are more often 3.11/3.12. **Recommended default:** declare `requires-python = ">=3.11"` and CI the matrix; do not require 3.14.

### Build / Packaging / Deployment / CI-CD

**Confirmed issue — the project cannot be installed or pinned.** No `pyproject.toml`, `setup.cfg`, `setup.py`, `requirements.txt`, `Pipfile`, `poetry.lock`, or `uv.lock`. No `console_scripts` entry point. Usage is `python3 main.py` from a clone, which is not a release mechanism.

**Confirmed issue — no CI.** No `.github/workflows`, no other pipeline files.

**Confirmed issue — no container/image/infrastructure.** None required for a CLI; also none for reproducible smoke tests.

**Confirmed issue — no version, changelog, or promotion path.** `prog="endpointctl"` in argparse but there is no `__version__` and no `--version`.

**Confirmed issue — bytecode and logs are in the clone.** Without `.gitignore`, `__pycache__` and `logs/endpoint.log` will keep being committed. That is not a hermetic artifact.

**Assumption — deployment model, if this goes to production, is per-endpoint install** (pipx, signed wheel, or MSIX/pkg), not a central server. Rollback = previous package version. There are no migrations.

**Open question — distribution channel** (pipx from a private index vs internal pkg vs git clone). **Recommended default:** `pyproject.toml` + wheel + `pipx install`; pin `psutil` and `rich` with a lockfile generated in CI. Do not clone `master` onto endpoints.

### Documentation and Maintainability

**Confirmed issue — README is the only doc and it is wrong in material ways.**

| README claim | Code |
|---|---|
| Structure includes `endpointctl/__init__.py`, `tests/`, `venv/` (lines 36–52) | Those paths are absent |
| Remediation folder labeled “(Planned)” (line 46) | `remediate` is implemented and routed |
| “No remediation actions are performed by default” (line 124) | True only if nobody runs `remediate`; the command is advertised by argparse help |
| “Platform-specific commands are wrapped safely” (line 126) | No timeout, no returncode, Windows admin skipped |
| Features list OS info as a scan (lines 63–68) | Not a `scan` target |
| Testing strategy “Planned” (lines 149–157) | Still zero tests |
| Next steps include approval-flag remediations (line 193) | Remediations already run after `yes` |

**Confirmed issue — no operations runbook, no API doc, no CONTRIBUTING, no LICENSE, no troubleshooting, no support matrix.** Disclaimer (README lines 184–186) says educational/demo and “never execute remediations in production without validation.” That conflicts with the rest of the README framing the tool as production-like infrastructure.

**Confirmed issue — comments are scarce; the one that exists has a typo** (`privilage`). No module docstrings.

### Dependencies and Technical Debt

**Confirmed issue — undeclared runtime dependencies.** `psutil` and `rich` are required to import the CLI. On this Fedora 43 host, `rich` is missing; `psutil` 7.0.0 happens to be a system package. A clean venv would miss both.

**Confirmed issue — no lock, no hashes, no SBOM.** Any install instructions would float latest PyPI.

**Do not upgrade `psutil` or `rich` “because a newer version exists.”** There is no pin to upgrade. When adding a manifest, choose current stable versions that support the declared Python range; justify the pin by compatibility with 3.11+ and the APIs already used (`disk_usage`, `process_iter`, `Console`, `rule`, `print`).

**Confirmed issue — committed `__pycache__` and `logs/`.** Dead weight and noise.

**Confirmed issue — dead / broken symbols:** unused `platform` in `security.py`; `RunTimeError` in `enable_encryption`; `scan_os` return value unused; README `venv/` and `tests/` placeholders.

**No TODO/FIXME/HACK markers** in Python sources. Debt is in behavior and missing engineering files, not tagged comments.

### User / Developer Experience

**Confirmed issue — CLI ergonomics.**

- No `--help` on bare invocation (subcommand not required).
- No `--version`, `--json`, `--verbose`, `--quiet`, `--dry-run`, `--yes` / `--assume-yes`, `--config`.
- `scan all` prints OS via a different style than other scans.
- Disk scan prints twice.
- Errors are either silent (bare `main.py`) or stack traces (`RemediationError`).
- `prog="endpointctl"` but the only documented invocation is `python3 main.py` (README lines 96–116). There is no `endpointctl` console script.

**Confirmed issue — local development setup is undocumented in a runnable way.** README lists Python 3, `psutil`, `rich`, argparse. No create-venv commands, no `pip install -e .`, no how to run a single module test.

**Confirmed issue — debugging.** Because logs do not include results or exceptions (except encryption scan’s `error` string in the return dict), an operator debugging a failed encryption check only has Rich-printed dicts. Remediation stderr is printed only if the command returns.

**Likely risk — first-run surprise: `logs/` created in whatever CWD the user happened to be in**, not next to the package.

## 4. Prioritized Findings

### P0 — Release Blockers

These block any production or even “safe lab default” release because a normal CLI invocation can destroy data or change encryption state without adequate controls. Priority is justified by **host impact**, not by polish.

#### P0-1 — Live remediations are destructive and under-gated

- **Problem:** `remediate disk` recursively deletes `/tmp` and `/var/tmp` children. `remediate encryption` enables BitLocker or FileVault. Gates are only Unix root (skipped on Windows) and an interactive `yes`. No dry-run, no preflight, no return-code handling, no audit log, no recovery-key escrow, no timeout. Linux encryption path raises `RunTimeError` (NameError). Exceptions during delete are swallowed.
- **Evidence:** `endpointctl/cli.py` 29–34, 63–70; `endpointctl/remediation/disk.py` 5–29; `endpointctl/remediation/encryption.py` 5–24; `endpointctl/remediation/base.py` 7–16.
- **Production impact:** Data loss, broken hosts, user lockout, false “success” after a failed OS command, CI/operator accidents. README will cause people to underestimate this.
- **Proposed implementation:** Treat remediations as **experimental and off**. For v1 production: remove `remediate` from the default parser **or** require a compile-time/env flag (e.g. `ENDPOINTCTL_ENABLE_REMEDIATION=1`) **and** `--dry-run` default with `--apply` to execute. Replace wipe-all temp with an age-based, allowlisted cleaner behind a preview plan. Do not call `manage-bde -on` / `fdesetup enable` at all until a separate design for escrow exists (see Open Questions). Catch `RemediationError` and `EOFError` in `cli.run`. Log every planned/applied action.
- **Affected files:** `endpointctl/cli.py`, `endpointctl/remediation/*`, `README.md`.
- **Design decisions:** **Recommended default — scan-only v1; keep remediation modules but do not register them unless the flag is set.** Alternative: delete remediation commands until rewritten (simpler, loses demo surface).
- **Dependencies / prerequisites:** Decision on whether FDE enablement is ever in-scope (Q1). Privilege check fix (P0-2) if any apply path remains.
- **Tests / verification:** Unit tests that the default CLI parser has no `remediate` (or that `remediate` without flag errors). Dry-run tests with a fake filesystem and fake subprocess runner. **Never** run apply against a real `/tmp` or real FDE in CI.
- **Acceptance criteria:** Default install cannot delete temp dirs or enable FDE. Any apply path prints a plan, requires `--apply` plus `yes` (or `--yes` only in tests), records audit fields, and fails closed on non-zero OS return codes. Linux unsupported OS returns a typed error, not `NameError`.
- **Risks:** README/demo scripts that already show `remediate` will break — update docs in the same change.
- **Rollout:** Ship the gate first, even before nicer temp cleanup. If a private fork already uses `remediate`, communicate the flag.
- **Docs:** Rewrite Safety section to match the gate. Document that FDE enablement is out of scope until escrow exists.
- **Why P0:** A single mistaken command is irreversible. No amount of scan quality makes this shippable.

#### P0-2 — Windows privilege check is a no-op

- **Problem:** `require_admin` returns immediately when `platform.system() == "Windows"`. Combined with P0-1, Windows is the least protected platform for the most dangerous command (`manage-bde -on c:`).
- **Evidence:** `endpointctl/remediation/base.py` 7–10; Windows branch in `enable_encryption` at `remediation/encryption.py` 11–12. Contrast `check_security` line 9, which also fails open/false on Windows instead of using an elevation API.
- **Production impact:** Unelevated users can *attempt* FDE enablement; the CLI will not stop them. If the OS command succeeds in some contexts, lockout. If it fails, the CLI still returns stdout/stderr as a completed action.
- **Proposed implementation:** Implement a real elevation check: on Windows, `ctypes.windll.shell32.IsUserAnAdmin()` (or equivalent token check); on Unix, keep `os.geteuid() == 0`. Use one helper for both remediation preflight and the security “admin_privileges” finding. Fail closed if the check cannot be evaluated.
- **Affected files:** `endpointctl/remediation/base.py`, `endpointctl/scanner/security.py` (share helper), tests.
- **Design decisions:** Fail closed if `IsUserAnAdmin` is unavailable. Do not treat “not Windows” as the only privileged platform.
- **Dependencies:** P0-1 (even a disabled remediate path should use the same helper when re-enabled).
- **Tests:** Monkeypatch `platform.system` and the Windows/Unix primitives. Assert Windows non-admin raises `RemediationError`.
- **Acceptance criteria:** Windows non-admin never reaches `subprocess.run` for remediations. Security scan `admin_privileges.enabled` is true only when actually elevated on that OS.
- **Risks:** `IsUserAnAdmin` false negatives for some split-token cases — document “must run elevated”.
- **Rollout:** Same release as the remediation gate.
- **Docs:** State required privileges per command.
- **Why P0:** Privilege bypass on the destructive path. Not an enhancement.

### P1 — Production Critical

These do not wipe a disk by themselves, but they make the tool **unsafe to trust** for operations or **impossible to ship** reproducibly. Justified by wrong security posture, undeployable artifacts, or operator deception.

#### P1-1 — Encryption scan results are wrong on Windows and untrustworthy elsewhere

- **Problem:** Substring `"on"` / `"encrypted"` on full stdout. No `returncode`, no `timeout`, no stderr handling, no Linux LUKS/dm-crypt. Success payload omits `status`.
- **Evidence:** `endpointctl/scanner/encryption.py` 8–38.
- **Production impact:** Compliance or “is this laptop encrypted?” answers will be **true on typical BitLocker-off output**. That is a false sense of security.
- **Proposed implementation:** Parse documented fields. Windows: run `manage-bde -status C:` (or each fixed drive) and require `Protection Status: Protection On` (or equivalent structured parse), not a substring of `Protection`. macOS: exact/regex `FileVault is On.` / `Off.`. Linux: return `UNSUPPORTED` until a dedicated LUKS detector (P3) or implement `lsblk`/`findmnt` carefully. Always set `timeout` (e.g. 30s), capture stderr, set `status` to `OK|WARNING|ERROR|UNSUPPORTED`, and treat non-zero return as `ERROR` unless a known “not elevated” code is mapped. Do not return raw stdout by default (too noisy; keep `--verbose`).
- **Affected files:** `endpointctl/scanner/encryption.py`, CLI renderer, tests with recorded fixtures (not live `manage-bde`).
- **Design decisions:** **Recommended:** fixture-based parsers; do not call real FDE tools in CI. Volume selection via config (`encryption.volumes`) defaulting to system volume.
- **Dependencies:** Shared result schema (P2-1) should land in the same change or immediately before.
- **Tests:** Fixtures for BitLocker on/off/unknown, FileVault on/off, missing binary, timeout, non-zero exit. Assert off-but-typical Windows text is `encrypted: false`.
- **Acceptance criteria:** Documented samples produce documented booleans. No substring-of-`protection` bug. Timeout expires the scan, not the operator.
- **Risks:** Locale-specific `manage-bde` text. Prefer exit codes / `/Protection Status/` with a documented English fallback and `status: ERROR` on unrecognized output rather than guessing `True`.
- **Rollout:** Bugfix; no migration.
- **Docs:** Document supported tools and locales; say Linux is unsupported until P3-2.
- **Why P1:** A security product that reports encrypted-when-not is worse than no product.

#### P1-2 — Disk and security scans are platform-incorrect and can crash

- **Problem:** Disk always `"/"` and 85%. Security uses Unix euid on a `getuid` hasattr check, concatenates process names, and can raise from `p.name()`. Unused `platform` import.
- **Evidence:** `scanner/disk.py` 8–18; `scanner/security.py` 1–38.
- **Production impact:** Windows disk “health” is meaningless. Security baseline `WARNING`/`OK` is a coin flip. `scan all` can die mid-run on process access.
- **Proposed implementation:** Disk: use configurable paths (default: `/` on POSIX, `C:\\` on Windows) or iterate `psutil.disk_partitions(all=False)` and skip tmpfs/cdrom. Return percent, total, used, free, mountpoint, threshold, status. Security: `process_iter(["name"])` with per-process `try/except (psutil.Error, ProcessLookupError)`. Match **exact normalized names** (or regex anchors) against a config list, not a giant substring. Share admin helper with P0-2. Remove unused import.
- **Affected files:** `scanner/disk.py`, `scanner/security.py`, future `endpointctl/config.py`.
- **Design decisions:** Default keep a small built-in agent name list; allow config override. Do not claim “XDR present” from a substring.
- **Dependencies:** Config module (P2-2) can be a small dict in-module first if it unblocks tests.
- **Tests:** Fake `disk_usage` / `disk_partitions`; fake process iterator that raises `AccessDenied` on one pid; Windows/Unix admin helpers.
- **Acceptance criteria:** `scan security` always returns a dict (never raises from a single inaccessible process). Windows disk default is not `"/"`. Threshold is not a magic number in the function body.
- **Risks:** enumerating all partitions may include network drives — default to local only.
- **Rollout:** Behavior change for Linux if switching from only `/` to all local mounts; document it.
- **Docs:** What “WARNING” means; which agents are detected.
- **Why P1:** Fleet decisions on disk/security would be wrong or interrupted.

#### P1-3 — Project is not installable or reproducible

- **Problem:** No build manifest, no pins, no entry point. `rich` missing on the audit host’s Python 3.14. README implies `venv/` exists.
- **Evidence:** repository listing; imports in `cli.py` 2, `os_info.py` 3, `disk.py` 1–2; site-packages check (`psutil` yes, `rich` no).
- **Production impact:** Two machines will not run the same code the same way. Endpoints cannot be updated or rolled back as a versioned artifact.
- **Proposed implementation:** Add `pyproject.toml` (setuptools or hatchling) with `project.name = "endpointctl"`, `requires-python`, `dependencies = ["psutil", "rich"]` pinned to versions tested in CI, `[project.scripts] endpointctl = "endpointctl.cli:run"`. Add `endpointctl/__init__.py` with `__version__`. Add a lockfile via the team’s existing tool (uv or pip-tools) **once** — do not add Poetry plus pip-tools plus uv. Keep `main.py` as a thin wrapper for source checkouts.
- **Affected files:** new `pyproject.toml`, lockfile, `endpointctl/__init__.py`, `main.py` (unchanged behavior), README install section.
- **Design decisions:** **Recommended: hatchling or setuptools + uv.lock.** Console script name `endpointctl` to match `argparse.prog`.
- **Dependencies:** None. Can proceed in parallel with P0 if remediations are gated first.
- **Tests:** CI job `pip install .` and `endpointctl --help` (after P2-1 makes `--help` on bare command work).
- **Acceptance criteria:** Clean venv: `pip install .` provides `endpointctl`. Declared Python versions match CI. No instruction to copy a `venv/` directory.
- **Risks:** Name clash on PyPI if ever published; use a private index or a more specific name if needed (`endpoint-automation` vs `endpointctl`).
- **Rollout:** Install method change only.
- **Docs:** Replace “python3 main.py” as the primary interface after the script exists; keep it as a fallback.
- **Why P1:** You cannot “release” a pile of unpinned scripts to endpoints.

#### P1-4 — No automated tests and no CI

- **Problem:** Every bug in this audit would have shipped. There is no pipeline to prevent the next one.
- **Evidence:** no `tests/`, no `.github/`, README 149–157.
- **Production impact:** Regressions in encryption parsing or a re-enabled wipe will not be caught.
- **Proposed implementation:** `tests/` with pytest. Layers: (1) parser/schema unit tests, (2) scanner tests with fixtures/mocks, (3) CLI tests via `parser.parse_args` or `runpy` with `capsys`, (4) a CI workflow on GitHub Actions: lint + pytest on 3.11/3.12/3.13 (3.14 optional). Forbid tests from calling real `cleanup_temp` / `enable_encryption` apply. Add a tiny `FakeCompletedProcess` helper.
- **Affected files:** new `tests/**`, `.github/workflows/ci.yml`, `pyproject.toml` optional deps `[project.optional-dependencies] dev`.
- **Design decisions:** pytest only. Do not add tox unless the matrix in GHA is insufficient. Lint: ruff is enough to start; mypy optional in P2.
- **Dependencies:** P1-3 packaging so CI can `pip install -e ".[dev]"`. Safer if P0-1 lands first so a mistaken test cannot see `remediate` apply.
- **Tests:** the suite *is* the deliverable. Include at least one test that fails if Windows encryption fixture-off is reported encrypted (locks P1-1).
- **Acceptance criteria:** PR CI red on test failure. Local `pytest` documented. Coverage of scanners + `require_admin` + CLI routing. No job SSHes to real endpoints.
- **Risks:** Flaky host-dependent tests if someone uses real `psutil` without mocks — ban that in review.
- **Rollout:** CI on this branch before any release tag.
- **Docs:** README Testing section becomes actual commands.
- **Why P1:** Production readiness without regression detection is theater.

#### P1-5 — Documentation contradicts safety-critical behavior

- **Problem:** Operators and future agents will follow README and enable remediations or trust scan output.
- **Evidence:** README 46, 123–129, 149–157, 192–195 vs `cli.py` 29–70 and modules above.
- **Production impact:** Social-engineering the operator via our own docs.
- **Proposed implementation:** Rewrite README to: what the tool actually does; supported OS; scan-only default; how to install; how to run; exit codes; config; explicit **non-goals** (no FDE enablement, no `/tmp` wipe). Add `docs/operations.md` with failure modes and what logs should contain after P2-3. Add LICENSE (see Q5).
- **Affected files:** `README.md`, new `docs/operations.md`, optionally `docs/architecture.md`.
- **Design decisions:** Keep the README short; move enterprise narrative below install/safety. Disclaimer stays, aligned with code.
- **Dependencies:** Should land in the same PR as P0-1 so docs and flags match.
- **Tests:** None required beyond link/path sanity. Optional: a test that README contains the current flag name.
- **Acceptance criteria:** A new engineer can install, run `scan disk`, and cannot find an ungated destructive command. Structure diagram matches the tree.
- **Risks:** Over-promising “enterprise” again — review language.
- **Rollout:** Docs-only after or with the safety gate.
- **Docs:** this task *is* documentation.
- **Why P1:** Mismatched safety docs are an operational incident waiting to happen.

#### P1-6 — CLI has no operational contract (exit codes, errors, invocation)

- **Problem:** Bare invocation exits 0 and prints nothing. Findings do not affect exit status. Uncaught remediations. No `--json` for automation. OS scan omitted from choices.
- **Evidence:** `cli.py` 14–70; `scan_os` print-only.
- **Production impact:** Cron/MDM cannot detect WARNING. Scripts cannot parse output reliably. Looks like a hung or no-op tool.
- **Proposed implementation:** `subparsers.required = True`. Map findings to exit codes (recommended: 0 = all OK/INFO, 1 = usage/user cancel, 2 = WARNING findings, 3 = ERROR/unsupported-required, 4 = unexpected). Catch `RemediationError`, `KeyboardInterrupt`, `EOFError`. Add `--json` that prints one object and suppresses Rich (requires scanners to stop printing — P2-1). Add `scan os`. `--version` from `endpointctl.__version__`.
- **Affected files:** `endpointctl/cli.py`, scanners (stop printing), `main.py` (`sys.exit(run())` if `run` returns a code).
- **Design decisions:** **Recommended exit scheme above.** Do not use only 0/1 if WARNING must be automatable.
- **Dependencies:** P2-1 result schema makes exit-code aggregation straightforward. Can ship `required=True` + exception handling first.
- **Tests:** `parse_args([])` should error; JSON mode tests; exit code for a WARNING disk fixture.
- **Acceptance criteria:** `endpointctl` with no args prints help and non-zero. `scan disk` JSON is one object. WARNING → non-zero.
- **Risks:** Anyone scraping Rich text will break when `--json` becomes the automation path — document that.
- **Rollout:** Exit-code change is a compatibility break; there are no known downstream consumers in-repo.
- **Docs:** table of commands and exit codes.
- **Why P1:** Without a contract, the tool cannot be operated in production even if scans are fixed.

### P2 — Production Important

Justified as things that will cause recurring operational pain or slow every later change. Not “the host is wrong/destroyed today” by themselves.

#### P2-1 — Introduce a single scan/remediation result schema and move I/O out of scanners

- **Problem:** Inconsistent dicts, printers inside scanners, CLI duplication, poor testability.
- **Evidence:** `scan_os`, `check_disk` print; return shapes differ; `cli.py` 38–70.
- **Production impact:** Every new check repeats the same bugs. JSON/exit codes stay fragile.
- **Proposed implementation:** `endpointctl/models.py` with a small dataclass or TypedDict: `name`, `status` (`OK|WARNING|ERROR|INFO|UNSUPPORTED`), `message`, `data`, `error`. Scanners only return it. CLI/Rich renderer and JSON renderer consume it. `scan all` returns a list plus aggregate status.
- **Affected files:** all scanners, `cli.py`, new `models.py`, tests.
- **Design decisions:** Keep Rich as presentation-only. Do not add Pydantic unless validation pain appears (stdlib dataclasses are enough).
- **Dependencies:** P1-1, P1-2, P1-6 should use this schema; implement together to avoid thrash.
- **Tests:** one renderer test, one aggregate-status test.
- **Acceptance criteria:** No `Console` in `scanner/` or `remediation/`. `scan all --json` is valid JSON with a stable key set.
- **Risks:** Over-abstracting four functions — keep the model to one file.
- **Rollout:** Internal only.
- **Docs:** document the JSON schema in README or `docs/cli.md`.
- **Why P2:** Enables P1 automation but is a design change, not a host-safety defect by itself.

#### P2-2 — Configuration module and removal of magic literals

- **Problem:** Thresholds, volumes, agent names, temp paths, log path are hardcoded.
- **Evidence:** table in §3 Configuration.
- **Production impact:** Cannot tune per OS image without forking.
- **Proposed implementation:** `endpointctl/config.py` loading optional `endpointctl.toml` or `ENDPOINTCTL_*` env vars, with safe defaults. Validate types at startup (threshold 1–99, paths must be absolute). Do not read config from the working directory only — search XDG / `%APPDATA%` / `--config`.
- **Affected files:** new config module, scanners, logger, CLI `--config`.
- **Design decisions:** **Recommended: TOML + env override.** Fail startup on invalid config (no silent clamp).
- **Dependencies:** P1-2 wants threshold/path config. Can land a minimal version in that PR.
- **Tests:** invalid threshold rejected; env override works.
- **Acceptance criteria:** Changing disk threshold does not require editing `disk.py`.
- **Risks:** cwd-relative config surprise — document search order.
- **Rollout:** defaults preserve current 85% and POSIX `/` until P1-2 Windows default changes.
- **Docs:** config reference.
- **Why P2:** Needed for real deployments; not a current data-loss bug.

#### P2-3 — Real audit logging and invocation records

- **Problem:** Import-time logs; CWD-relative file; no rotation; remediations silent; committed `logs/endpoint.log`.
- **Evidence:** `reporting/logger.py` 4–11; `os_info.py` 21; `disk.py` 20; `logs/endpoint.log`.
- **Production impact:** After an incident, there is no record of who ran what. Log file growth if scheduled.
- **Proposed implementation:** Initialize logging in `cli.run`, not at import. Default log under `XDG_STATE_HOME` or `--log-file`. `RotatingFileHandler`. One structured line per invocation: timestamp, version, argv, uid/euid, os, command, aggregate status, errors. Never log full FDE tool stdout at INFO. Delete tracked `logs/endpoint.log` and ignore `logs/` (P2-4).
- **Affected files:** `reporting/logger.py`, `cli.py`, scanners (remove module-level info).
- **Design decisions:** JSON-lines audit file plus optional stderr human logs. Correlation id = UUID per invocation (enough; no distributed trace).
- **Dependencies:** P0-1 should log if apply is ever used. P2-4 gitignore.
- **Tests:** importing `scanner.disk` does not create `logs/`. A CLI test writes one audit line.
- **Acceptance criteria:** Import is side-effect-free. Each run produces exactly one summary audit record. Old committed log gone.
- **Risks:** home-directory paths — stay inside documented locations; do not write to `/var/log` without being root.
- **Rollout:** operators lose the meaningless import logs (good).
- **Docs:** where logs live; what is never logged.
- **Why P2:** Essential operations, but current tool is not in fleet yet.

#### P2-4 — Repository hygiene: `.gitignore`, drop bytecode and logs

- **Problem:** No `.gitignore`. `__pycache__` and `logs/endpoint.log` are in the tree.
- **Evidence:** directory listing; no `.gitignore` file.
- **Production impact:** Dirty diffs, accidental secret logging later, non-reproducible checkouts.
- **Proposed implementation:** Add `.gitignore` for `__pycache__/`, `*.py[cod]`, `venv/`, `.venv/`, `logs/`, `.pytest_cache/`, `dist/`, `*.egg-info/`. Remove tracked pyc and `logs/endpoint.log`. Keep `.cursor/production-readiness-plan.md` if the team wants the plan in git (this audit created it).
- **Affected files:** new `.gitignore`; git rm of pyc/logs (implementation phase).
- **Design decisions:** Do not ignore all of `.cursor/` if this plan should remain versioned.
- **Dependencies:** none.
- **Tests:** none.
- **Acceptance criteria:** Fresh clone has no `__pycache__` or `logs/`. `git status` clean after a local run (once logging is not CWD-`logs/`, or `logs/` is ignored).
- **Risks:** none material.
- **Rollout:** one cleanup commit.
- **Docs:** mention in contributing.
- **Why P2:** Hygiene; not user-facing correctness.

#### P2-5 — Subprocess timeouts and explicit OS-tool errors on remaining scan commands

- **Problem:** Even after P1-1, any new tool call can hang. There is no shared runner.
- **Evidence:** two raw `subprocess.run` sites today (`scanner/encryption.py` 20–24, `remediation/encryption.py` 18).
- **Production impact:** Stuck MDM jobs; hung terminals.
- **Proposed implementation:** `endpointctl/process.py` with `run_os_tool(argv, timeout=30)` returning stdout/stderr/returncode, never `shell=True`, always a timeout, argv logged at DEBUG. Scanners/remediations use only this helper.
- **Affected files:** new helper, encryption modules.
- **Design decisions:** Default 30s scan timeout; remediation (if any) should be even more explicit and cancellable.
- **Dependencies:** P1-1 can include the helper.
- **Tests:** fake runner; a test that timeout surfaces as `status: ERROR`.
- **Acceptance criteria:** No direct `subprocess.run` outside the helper (grep-enforced in review or a lint test).
- **Risks:** too-short timeout on slow disks — make it configurable (P2-2).
- **Rollout:** internal.
- **Docs:** timeout defaults.
- **Why P2:** Reliability hardening; P1-1 already requires it for encryption.

#### P2-6 — Package completeness and small correctness nits

- **Problem:** Missing package `__init__` files; `RunTimeError`; unused import; trailing whitespace; `scan_os` naming vs `check_*`.
- **Evidence:** tree listing; `remediation/encryption.py` 16; `security.py` 1, 8; `disk.py` 2.
- **Production impact:** Confusing errors (`NameError` on Linux remediate); sloppy package layout.
- **Proposed implementation:** Add `__init__.py` to `endpointctl`, `reporting`, `remediation`. Rename `RunTimeError` → `RuntimeError` or, better, raise `RemediationError`. Unify function names. Enable ruff in CI (P1-4).
- **Affected files:** those modules.
- **Design decisions:** Prefer `RemediationError` for unsupported OS so CLI handling is one type.
- **Dependencies:** P0-1 may delete the Linux raise path from the CLI entirely.
- **Tests:** ruff clean; Linux unsupported path.
- **Acceptance criteria:** `python -c "import endpointctl"` works after install. Ruff has no unused-import / undefined-name on these files.
- **Risks:** none.
- **Rollout:** with packaging PR.
- **Docs:** none.
- **Why P2:** Quality and installability, not a current Windows lockout.

#### P2-7 — Versioning, LICENSE, and support matrix

- **Problem:** No version, no license, no stated OS/Python support. Bytecode implies 3.14-only practice.
- **Evidence:** no `LICENSE`; no `__version__`; pyc `cpython-314`.
- **Production impact:** Legal/distribution blocker for some orgs; no way to ask “what is on this endpoint?”.
- **Proposed implementation:** Add `LICENSE` (Q5), `__version__`, `--version`, `CHANGELOG.md`, README support table (Windows / macOS / Linux scans; Python >=3.11).
- **Affected files:** new license/changelog, `endpointctl/__init__.py`, README, CLI.
- **Design decisions:** See Q5. Version 0.1.0 until P0/P1 close, then 1.0.0 when checklist passes.
- **Dependencies:** P1-3, P1-6.
- **Tests:** `--version` prints the same string as `__version__`.
- **Acceptance criteria:** Support matrix is explicit. Version is queryable.
- **Risks:** choosing a license without the author — decision required.
- **Rollout:** tag after checklist.
- **Docs:** README header.
- **Why P2:** Release mechanics; not a functional outage.

### P3 — Enhancements

Do these after P0–P2. Do not start API/ITSM work to “look production.”

#### P3-1 — Machine-export formats and severity model

- **Problem:** README planned JSON/CSV and INFO/WARNING/CRITICAL. JSON is already required for ops in P1-6; CSV and a richer severity (CRITICAL vs WARNING) can wait.
- **Evidence:** README 137–140.
- **Production impact:** Nice for SIEM ingest; not required if `--json` exists.
- **Proposed implementation:** `--output json|csv|text`; optional `CRITICAL` for e.g. encryption off on a required-OS. Keep the enum in `models.py`.
- **Affected files:** renderer, models.
- **Design decisions:** Do not invent a scoring system (0–100) without a consumer.
- **Dependencies:** P2-1.
- **Tests:** CSV header stability.
- **Acceptance criteria:** CSV of `scan all` is documented.
- **Risks:** severity inflation.
- **Rollout:** additive flags.
- **Docs:** examples.
- **Why P3:** Additive after a working JSON contract.

#### P3-2 — Linux disk-encryption detection (LUKS / dm-crypt)

- **Problem:** Linux returns `UNSUPPORTED` (`scanner/encryption.py` 13–18). Development logs and this audit host are Linux, so the most used platform cannot answer the headline question.
- **Evidence:** else branch in `check_encryption`; `logs/endpoint.log` produced on a non-Windows/non-Darwin-looking workflow (import-only, but host is Fedora).
- **Production impact:** Linux fleets get no encryption signal.
- **Proposed implementation:** Read-only checks: `/sys/block` + `lsblk -J -o NAME,FSTYPE,MOUNTPOINT,TYPE` or `findmnt -J /` and detect `crypt`/`crypto_LUKS`. Timeout + parse JSON. Still detect-only.
- **Affected files:** `scanner/encryption.py` or `scanner/encryption_linux.py`.
- **Design decisions:** Prefer `lsblk --json` over `cryptsetup status` (latter often needs root). If tools missing → `ERROR` with a clear message, not silent `False`.
- **Dependencies:** P1-1 parser architecture, P2-5 runner.
- **Tests:** lsblk JSON fixtures (root on LUKS, root on ext4).
- **Acceptance criteria:** Fedora-like fixture → encrypted true/false correctly; no subprocess shell.
- **Risks:** privilege and tool presence vary — document.
- **Rollout:** additive for Linux.
- **Docs:** support matrix update.
- **Why P3:** Important for *this* repo’s likely runtime, but current code already admits UNSUPPORTED rather than lying (unlike Windows). Do after the Windows lie is fixed.

#### P3-3 — Scheduling, REST API, Web UI, ITSM

- **Problem:** README 141–145, 192–195 list cron, FastAPI, ServiceNow/Jira, orchestration.
- **Evidence:** no such code.
- **Production impact:** None today. Adding them now multiplies P0/P1 bugs across a network surface (authn, SSRF, secret storage).
- **Proposed implementation:** Defer. If scheduling is needed, document systemd timers / Task Scheduler calling `endpointctl scan all --json`. If API is needed later, design auth first.
- **Affected files:** none now.
- **Design decisions:** **Recommended: out of scope until checklist passes.**
- **Dependencies:** entire P0–P2.
- **Tests:** n/a.
- **Acceptance criteria:** n/a for v1.
- **Risks:** scope explosion.
- **Rollout:** n/a.
- **Docs:** README next-steps should say “after scan-only v1.”
- **Why P3:** No production value before the CLI is truthful and safe.

#### P3-4 — Health/metrics/tracing for a future daemon

- **Problem:** No health endpoints or metrics. Correct for a CLI.
- **Evidence:** no server.
- **Production impact:** None until someone daemonizes this.
- **Proposed implementation:** If a long-running agent is added: `/healthz` liveness, last-scan timestamp readiness, counters for scan_ok/scan_fail, OpenTelemetry only if a collector already exists.
- **Affected files:** none now.
- **Design decisions:** Do not add Prometheus to a one-shot CLI.
- **Dependencies:** product decision to run a service.
- **Why P3:** Premature for the current process model.

#### P3-5 — Signed releases and fleet distribution

- **Problem:** No artifacts, checksums, or signing.
- **Evidence:** no `dist/`, no release workflow.
- **Production impact:** Cannot do integrity-checked promotion.
- **Proposed implementation:** After P1-3/P1-4: CI builds wheels, publishes checksums, optional sigstore/GPG. Internal pkg repo.
- **Dependencies:** P1-3, P1-4, P2-7.
- **Why P3:** Needed for *mature* fleet, not for first internal production use of a scan-only CLI via pipx on a pinned hash.

## 5. Detailed Implementation Plan

### Phase 1 — Safety freeze (P0, start P1-5)

**Goal:** A checkout of this branch cannot destroy temp data or enable FDE through the default CLI. Docs no longer claim the opposite.

**Order:**

1. **P0-1 Remediation gate** (do this first; blocks accidental harm during later test work).
   - Unregister `remediate` or require env flag + `--apply`.
   - Catch `RemediationError` / `EOFError` / `KeyboardInterrupt` in `cli.run`.
   - Stop importing remediation modules until the subcommand is selected (optional but recommended).
   - Leave module files in place; do not rewrite temp cleanup yet except to make apply unreachable.
2. **P0-2 Shared privilege helper** (same PR if remediations can still be imported; otherwise immediately after).
3. **P1-5 README/safety rewrite** in the same PR as the gate so help text and docs match.

**Can combine:** P0-1 + P0-2 + P1-5 = one “safety” PR.

**Must not combine:** do not rewrite all scanners in this PR.

**Exit of phase:** `endpointctl scan --help` works after packaging *or* `python3 main.py scan disk` still runs; `remediate` is absent or refuses without the flag; README safety section matches.

### Phase 2 — Truthful scans and an operational CLI (P1-1, P1-2, P1-6, P2-1, P2-5)

**Goal:** Scan results are parseable and not systematically wrong.

**Order:**

1. **P2-1 models + stop printing inside scanners** (foundation).
2. **P2-5 process runner** (small, used by encryption).
3. **P1-1 encryption parser + fixtures**.
4. **P1-2 disk + security** (can parallelize with P1-1 after models exist).
5. **P1-6 CLI contract** (`required=True`, `--json`, exit codes, `scan os`, `--version` placeholder until P1-3 version exists).

**Can combine:** P2-1 + P2-5 + P1-1 in one PR; P1-2 in a second; P1-6 in a third. Or one “scan contract” PR if the team wants a single review — still keep remediations untouched.

**Must separate from:** packaging/CI can start in parallel but JSON tests need pytest (Phase 3) to lock behavior.

**Exit of phase:** Fixture tests (even if run locally) prove Windows-off ≠ encrypted. `scan all` returns one schema. WARNING affects exit code.

### Phase 3 — Ship mechanics (P1-3, P1-4, P2-4, P2-6, P2-7, start P2-2, P2-3)

**Goal:** Installable, tested, ignore junk files, real logs, config for thresholds.

**Order:**

1. **P2-4 `.gitignore` + remove pyc/logs** (trivial; do immediately so CI is not noisy).
2. **P1-3 pyproject + lock + `__init__.py`** (P2-6 inits in the same PR).
3. **P1-4 pytest + GHA** with mocks; add ruff.
4. **P2-3 logging init in CLI** + drop import side effects.
5. **P2-2 config** (minimum: disk threshold/path and security process list).
6. **P2-7 version/LICENSE/changelog** once the author answers Q5.

**Can combine:** P2-4 + P1-3 + P2-6; P1-4 follows once install works; P2-3 can ride with P1-4.

**Parallelism:** Phase 3 packaging can overlap Phase 2 if people accept rebasing tests onto the new schema.

**Exit of phase:** `pip install -e ".[dev]"`; `pytest` and ruff in CI; `endpointctl --version`; import does not mkdir `logs`.

### Phase 4 — After v1 (P3)

Linux LUKS (P3-2) is the only P3 with clear value for this repo’s Linux development host. Then CSV/severity (P3-1). Defer API/ITSM/daemon/signing (P3-3, P3-4, P3-5) until a real consumer exists.

**Explicitly out of scope for the first production cut:** FastAPI, ServiceNow, Jira, scheduled engine inside the process, rewriting the tree into a hexagonal architecture, adding retry/circuit-breakers on local subprocess, or enabling FDE from this CLI.

## 6. Testing and Validation Strategy

There are **no existing tests to extend**. Build a suite that would have failed on today’s code.

**Unit (required for v1):**

| Area | How | Locks |
|---|---|---|
| Encryption parsers | `CompletedProcess` fixtures from real English `manage-bde` / `fdesetup` samples stored under `tests/fixtures/` | P1-1 false-positive |
| Disk classification | fake `disk_usage` namedtuple | 85% / path / Windows default |
| Security | fake processes + one `AccessDenied` | no crash; no substring blob |
| `require_admin` | mock `platform.system`, `geteuid`, `IsUserAnAdmin` | P0-2 |
| `confirm_action` | `monkeypatch` stdin `yes` / `no` / EOF | cancel vs apply |
| CLI parser | `parse_args` | no default `remediate`; `required` subcommand |
| Process runner | mock `subprocess.run` to raise `TimeoutExpired` | P2-5 |

**Integration (required for v1):**

- `pip install .` in CI, then `endpointctl scan disk --json` (or `python -m endpointctl` if you add `__main__.py`) with psutil allowed **only** for disk of the CI runner, **or** inject fakes via an env `ENDPOINTCTL_TESTING=1` hook. Prefer fakes so CI is deterministic.
- Assert `--json` is `json.loads`-able and has the model keys.

**Forbidden in CI:**

- Calling `cleanup_temp` apply against the runner.
- Calling `enable_encryption` apply.
- Running `fdesetup` / `manage-bde` for real.

**Failure / boundary cases to encode:** missing binary, non-zero return, empty stdout, unrecognized output → `ERROR` not `encrypted: True`, timeout, non-tty stdin, unwritable log dir (after P2-3).

**Security tests:** Windows admin skip cannot regress; `shell=True` grep test; argv for remaining remediations (if any) is a fixed list.

**Concurrency:** not applicable beyond “two CLI processes could wipe /tmp” — addressed by disabling apply.

**Lint / type / format (v1):** ruff check + format in CI. mypy optional once models have types.

**Manual / host verification (not a substitute for CI):**

- Linux: `scan all --json` on Fedora; encryption `UNSUPPORTED` or LUKS after P3-2.
- Windows VM: BitLocker off → `encrypted: false`; disk on `C:\`.
- macOS VM: FileVault off/on parse.
- Confirm default CLI cannot remediate.

**Diagnostics this audit could not run** (`py_compile`, `pytest`, import) must be run in the implementation phase and recorded.

## 7. Deployment and Rollback Considerations

**What you are deploying:** a versioned CLI on each endpoint, not a server. There is no migration and no central state.

**v1 deploy path (recommended):**

1. Tag `v0.1.0` only after Phase 1 (safety). Tag `v1.0.0` after the checklist.
2. Build a wheel in CI (Phase 3/P3-5).
3. Install with `pipx install` / internal package manager from a **pin** (hash or exact version).
4. Invoke `endpointctl scan all --json` from existing cron/Intune/Jamf/systemd — do not build a scheduler inside the app.

**Rollback:** reinstall the previous wheel. Scans are read-only after P0-1, so rollback is not a data-restore problem **unless** someone ran apply remediations. There is **no rollback** for BitLocker/FileVault enablement or a `/tmp` wipe — another reason those stay off.

**Startup / health:** CLI should validate config and dependencies at the beginning of `run()` and exit 3 with a clear message if `psutil`/`rich` missing (should not happen after install). No long-running health port.

**Promotion:** `dev/production-readiness` is **not** on the remote today. Push only when asked. Promote via PR into `master` after CI exists. Do not treat `master` at `4c80a954` as production.

**Integrity:** after P3-5, publish SHA256. Until then, pin git SHA or wheel hash in the internal installer.

**If remediations are ever enabled in a later version:** require a staged flag, canary hosts, recovery-key escrow proof, and a runbook for lockout. That is a new production review, not a toggle.

## 8. Production Readiness Checklist

Concrete exit criteria. Check only with evidence (command output, PR, or file).

**Functionality**

- [ ] Default CLI has no ungated `remediate` apply path (P0-1).
- [ ] Windows BitLocker-off fixture → `encrypted: false` (P1-1).
- [ ] FileVault on/off fixtures parse correctly (P1-1).
- [ ] Linux without a detector → `UNSUPPORTED` or a tested LUKS result, never a substring guess (P1-1 / P3-2).
- [ ] Disk scan default path is OS-correct; threshold configurable (P1-2, P2-2).
- [ ] `scan security` survives `AccessDenied` on a process (P1-2).
- [ ] `scan os` is a first-class command; `scan all` includes it (P1-6).
- [ ] Bare invocation prints help and exits non-zero (P1-6).

**Security**

- [ ] `require_admin` enforces elevation on Windows and Unix (P0-2).
- [ ] No `shell=True`.
- [ ] FDE enablement not callable in the production extra/entry point (P0-1, Q1).
- [ ] Audit log does not record FDE stdout at INFO (P2-3).
- [ ] README safety section matches the binary (P1-5).

**Tests**

- [ ] `pytest` exists and is green in CI on at least two Python versions (P1-4).
- [ ] Fixtures cover encryption false-positive case that today’s line 26 would fail.
- [ ] CI does not run apply remediations.

**Build / lint / type / static**

- [ ] `pyproject.toml` + lockfile; clean venv install works (P1-3).
- [ ] ruff (or equivalent) in CI (P1-4, P2-6).
- [ ] `python -m py_compile` / import of `endpointctl` succeeds in CI (blocked in this audit; must be run later).

**Reliability**

- [ ] All OS tool calls go through a timeout helper (P2-5).
- [ ] Non-zero tool status → `ERROR`, not fake success (P1-1).
- [ ] CLI catches user cancel and EOF (P0-1, P1-6).
- [ ] Importing scanner modules does not write files (P2-3).

**Observability**

- [ ] One audit record per invocation with argv, user, aggregate status (P2-3).
- [ ] WARNING/ERROR affect exit codes (P1-6).
- [ ] `--json` for automation (P1-6).

**Configuration / secrets**

- [ ] Thresholds/paths/agent lists not hardcoded in scan functions (P2-2).
- [ ] Invalid config fails startup (P2-2).
- [ ] No `.env` committed; no secrets in repo (true today; keep it).

**Deployment / rollback**

- [ ] Versioned wheel or equivalent; `--version` works (P1-3, P2-7).
- [ ] Documented install + rollback (reinstall previous version) (P1-5, §7).
- [ ] `dev/production-readiness` not used as an unpinned `git pull` on endpoints.

**Docs / operations**

- [ ] README tree, commands, safety, install, support matrix match the code (P1-5, P2-7).
- [ ] Operations note: log location, exit codes, what to do on `ERROR` (P1-5).
- [ ] LICENSE present (Q5).

**Performance**

- [ ] Log rotation configured (P2-3).
- [ ] No new unbounded collections or background threads without review.

**Known-risk disposition**

- [ ] P0-1, P0-2 closed or explicitly accepted in writing (do **not** accept P0-1).
- [ ] P1 items closed or waived with owner + expiry.
- [ ] P3 items parked with “not in v1” in README.
- [ ] Q1–Q5 decided.

## 9. Open Questions / Decisions Required

Only questions that actually block design. Recommended defaults included.

### Q1 — Are remediations in v1 scope?

**Tradeoff:** Keeping `remediate` looks like the README “platform.” Enabling FDE or wiping `/tmp` without escrow/MDM is operationally indefensible.

**Recommended default:** **No apply remediations in v1.** Keep code behind a flag for demos or delete the CLI surface. FDE enablement stays out until a written escrow design exists.

### Q2 — Official support matrix?

**Tradeoff:** README says Windows and macOS; development artifacts and this audit are Linux. Supporting three OSes without CI runners for each means mocks only.

**Recommended default:** **Scans: Linux + Windows + macOS.** Document Linux encryption as unsupported until P3-2. CI: Linux real + Windows/macOS fixtures. Do not claim macOS/Windows are “tested on hardware” until they are.

### Q3 — Python versions?

**Tradeoff:** 3.14-only matches current `__pycache__` but will not exist on most endpoints.

**Recommended default:** **`>=3.11,<3.15`** (or `>=3.11`) with CI on 3.11 and 3.12. Fix any 3.14-only accidents if they appear when tests run.

### Q4 — Distribution channel?

**Tradeoff:** git clone is what exists; pipx/wheel is extra work (P1-3) but is the minimum real release.

**Recommended default:** **Internal wheel + pipx (or the org’s standard pkg).** Not PyPI until the name/license are decided. Not raw git on endpoints.

### Q5 — License?

**Tradeoff:** No `LICENSE` means default all-rights-reserved; some orgs cannot adopt it.

**Recommended default:** Author (README: Novrus Shehaj) picks explicitly. MIT if the intent is portfolio/demo; a more restrictive license if this becomes internal-only IP. **Do not invent a license in a later coding pass without the owner.**

### Q6 — Should `scan all` fail the run when one scanner errors?

**Tradeoff:** fail-fast vs best-effort report.

**Recommended default:** **Best-effort:** always return the other results; aggregate status `ERROR` if any child is `ERROR`; exit 3. Do not hide the failed child.

No further open questions are required to start Phase 1.

## 10. Recommended Implementation Order

1. **P0-1 + P0-2 + P1-5** — safety gate, Windows admin, honest docs. One PR.
2. **P2-4** — `.gitignore`, drop `__pycache__` and `logs/endpoint.log`. Tiny PR; do it early.
3. **P2-1 + P2-5 + P1-1** — result model, subprocess helper, fix encryption parse + fixtures.
4. **P1-2** — disk + security correctness.
5. **P1-3 + P2-6** — packaging, package inits, lockfile.
6. **P1-4** — pytest + ruff + GitHub Actions.
7. **P1-6** — CLI contract, `--json`, exit codes, `scan os` (if not already done with P2-1).
8. **P2-3 + P2-2** — audit logs, config.
9. **P2-7** — version, changelog, license after Q5.
10. **Re-run the §8 checklist.** Only then consider P3-2 (Linux LUKS), then P3-1. Leave P3-3/4/5 parked.

Do not implement API, ITSM, or “orchestration” on this codebase until steps 1–9 are done. Do not “just pin newer dependencies.” Do not re-enable FDE or `/tmp` wipes as part of cleanup refactors.

---

### Appendix A — Command log (this audit)

| # | Command | Outcome |
|---|---|---|
| 1 | `ls -la` repo root, `endpointctl/**`, `logs/`, `.git/` | Success. Tree documented in §2. |
| 2 | `ls` `__pycache__` dirs | Success. `cpython-314` bytecode present. |
| 3 | `ls /usr/bin/python3 /usr/bin/git /usr/bin/gh` | Success. Python 3.14, git, gh installed. |
| 4 | `ls` `/usr/lib/python3.14/site-packages` and `/usr/lib64/python3.14/site-packages` | Success. `psutil` 7.0.0 present; `rich` absent. |
| 5 | Read `psutil-7.0.0.dist-info/METADATA` | Success. Version 7.0.0. |
| 6 | Read all application sources, README, `logs/endpoint.log`, git HEAD/config/reflogs/packed-refs | Success. |
| 7 | Grep TODO/FIXME/subprocess/except/config | Success. No TODO/FIXME in `.py`. |
| 8 | `git status`, `git log --oneline`, `git ls-files`, `git rev-parse` | **Blocked.** Branch/SHA taken from `.git` files instead. |
| 9 | `python3 --version`, `/usr/bin/python3 --version`, `python3 -m py_compile` on all modules | **Blocked.** Syntax reviewed by reading sources only. Runtime import not executed. |
| 10 | `/usr/bin/strings` on git pack; `/usr/bin/wc -l` on sources | **Blocked.** Line references come from the Read tool. |
| 11 | `find` of repository | **Blocked.** Tree taken from `ls` + glob. |
| 12 | Web search of `github.com/NovrusShehaj/endpoint-automation` | **Rejected.** No extra GitHub metadata. |
| 13 | pytest / ruff / mypy | **Not present** in-repo. No `/usr/bin/pytest`. Not run. |
| 14 | Dependency install / `pip` / live `scan` / live `remediate` | **Not run** (out of scope and unsafe). |

### Appendix B — Limitations of this audit

- Git commit message and full history for `4c80a95477f691df077e0ad4b29d4edc752edfac` were not retrieved.
- Application imports and CLI help were not executed; `rich` is absent from the audit host’s Python 3.14 site-packages, so a live import would likely fail even if the interpreter were usable.
- No Windows or macOS host was available; BitLocker/FileVault findings are from source plus typical vendor command output, labeled **confirmed** for the predicate bug and **likely** for interactive `fdesetup enable` hang behavior.
- Working-tree cleanliness after this write could not be confirmed with `git status` (blocked). Directory listing after write must show only the new `.cursor/production-readiness-plan.md` plus the pre-existing tree.
- This file is the only authorized repository modification from the audit.
