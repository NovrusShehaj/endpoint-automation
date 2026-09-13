# Contributing

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Before opening a pull request

```bash
ruff check .
ruff format --check .
mypy
pytest
```

CI runs exactly these, plus a wheel build and a clean-virtualenv smoke test.

## Rules that are enforced by tests

These are not style preferences; each one exists because the corresponding bug
shipped once already.

* **No `shell=True`, and no `subprocess` outside `endpointctl/process.py`.**
  Every OS-tool call needs a fixed argv and a timeout.
* **No delete calls in `endpointctl/remediation/`.** v1 ships no apply path.
* **Scanners return `ScanResult` and never print.** Rendering belongs to
  `reporting/render.py`.
* **Importing a module must not touch the filesystem.** Logging is configured in
  `cli.main`.
* **Every package directory has an `__init__.py`.**

## Testing an OS-specific code path

Never call a real OS tool from a test. Record its output under
`tests/fixtures/` and drive the parser with it, as
`tests/test_scanner_encryption.py` does. Tests must not depend on the host's
real disks, processes or encryption state — mock `psutil` and `run_os_tool`.

Tests must never invoke an apply path, delete a file outside `tmp_path`, or
write outside the pytest temporary directory. The autouse fixture in
`tests/conftest.py` redirects `HOME`, the XDG directories and the audit log
accordingly.

## Changing behaviour that operators depend on

Exit codes, the `--json` key set and configuration keys are a contract. Update
`README.md`, `docs/operations.md` and `CHANGELOG.md` in the same pull request.
