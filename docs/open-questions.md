# Open decisions

Status of the questions raised by the production-readiness audit
(`.cursor/production-readiness-plan.md`, §9). Items marked **owner decision**
are not for an implementer to invent.

## Q1 — Are remediations in v1 scope?

**Decided: no.** Implemented as the audit recommended. The `remediate` command
is not registered unless `ENDPOINTCTL_ENABLE_REMEDIATION=1`, and even then
there is no apply path: `remediate disk` previews, `--apply` is refused, and
`remediate encryption` refuses with guidance toward a managed workflow.

Re-opening this requires a written key-escrow design for full-disk encryption
and a separate production review.

## Q2 — Official support matrix?

**Decided as recommended.** Scans support Linux, Windows and macOS. Linux
encryption detection is `UNSUPPORTED` until LUKS/dm-crypt detection ships. CI
runs the suite on all three operating systems, but Windows and macOS encryption
logic is covered by **recorded fixtures only** — the README says so rather than
claiming hardware testing.

## Q3 — Python versions?

**Decided: `>=3.11,<3.15`.** 3.11 is the floor because the config layer uses
stdlib `tomllib`. CI covers 3.11 through 3.14 on Linux plus 3.12 on Windows
and macOS.

## Q4 — Distribution channel?

**Decided as recommended:** build a wheel in CI, install per endpoint with
`pipx` (or the organisation's package manager) from a pinned version or hash.
`uv.lock` pins the resolved dependency versions. Not published to PyPI — the
package name and the license are both undecided. Never `git pull` onto
endpoints.

## Q5 — License?

**Owner decision — still open.** No `LICENSE` file exists, so the project is
all-rights-reserved by default and cannot be adopted by most organisations.

The audit's guidance was MIT if the intent is a portfolio/demo project, and
something more restrictive if this becomes internal IP. Choosing one is the
author's call; nothing in the implementation depends on it. Add a `LICENSE`
file and the matching `project.license` entry in `pyproject.toml` when decided.

## Q6 — Should `scan all` fail the run when one scanner errors?

**Decided: best-effort.** Every scanner runs; a failing one is reported as an
`ERROR` result rather than aborting the report, and it raises the aggregate
status (exit code 3). No failed child is hidden.

## Deferred work (not in v1)

| Item | Why deferred |
|---|---|
| Linux LUKS/dm-crypt detection | Highest-value next item; needs `lsblk --json` parsing plus fixtures. Today Linux honestly says `UNSUPPORTED` rather than guessing. |
| CSV export, `CRITICAL` severity | `--json` already covers automation; more severity levels need a consumer first. |
| REST API / Web UI / ITSM integration | Would multiply the surface before the scan contract has proven itself, and adds authentication and secret storage. |
| Health/metrics endpoints | This is a one-shot CLI, not a daemon. |
| Signed releases, internal package feed | Needed for a mature fleet rollout, not for the first internal use. |
