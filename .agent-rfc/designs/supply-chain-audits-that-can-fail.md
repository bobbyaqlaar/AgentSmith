---
status: active
scope:
  - scripts/compliance_checks.py
  - scripts/test/test_compliance_checks.py
  - workflow-templates/agentsmith-supply-chain.yml
---
# OB-SUPPLY-CHAIN passes only on an audit that can fail, and the template audits every manifest

From the 4.1.0 review's second pass (the owner's local `review-4.1.0-pass2.md`): P2-R8 and P2-R9, siblings of P2-R7,
two minors the owner asked for before the release. Follows `.agent-rfc/designs/review-pass2-majors.md` and
`.agent-rfc/designs/compliance-profile-holds.md` (R12).

## Problem

- **P2-R8.** `_supply_chain_job` passes when a `run:` contains the text `pip-audit`, `npm audit` or `govulncheck` and
  the workflow names `push` or `pull_request`. It passes `pip-audit … || true`, a job with `if: false`, `push:
  branches: [never-a-branch]`, and `echo "govulncheck is for later"`.
- **P2-R9.** The template's audits are gated on `hashFiles('package-lock.json')`, `hashFiles('go.mod')` and the root
  Python files, so they read the repository root only. A Python service at the root and a web client in
  `web/package-lock.json` gets the Python audit, no npm audit, and a green job.

## Approach

- **P2-R8.** The check reads what would actually run and fail:
  - an audit is a command invoked at the start of a line or after `;`, `&&` or `(` (so not inside `echo "…"` or a
    comment), as `pip-audit` (or `pipx run pip-audit…`), `npm audit`, or `govulncheck` (or `go run …/govulncheck@…`);
  - that line has no `||` fallback (other than `|| exit <non-zero>`), and the run has no `set +e`;
  - neither the step nor its job has `continue-on-error: true`; the job has no `if:`; the step's `if:` is not a
    constant false;
  - a `push` or `pull_request` trigger runs on the default branch: no `branches` filter, or a filter naming it (from
    `origin/HEAD`, else `main` and `master`) or a wildcard.
  It stays a reading of the workflow, not a run of it, and says so; what it now refuses are the shapes that read as an
  audit and cannot fail.
- **P2-R9.** Each stack's step finds every manifest in the repository (pruning `.git`, `node_modules`, virtual
  environments and `vendor`), audits each project directory, and writes one SBOM per directory
  (`sbom/<stack>-<dir>.cdx.json`). Steps are gated on `hashFiles('**/…')`. Go's version comes from the root `go.mod`
  when there is one, else the stable release. A test runs the template's own `run:` scripts with stand-in `pipx`, `npm`,
  `npx`, `go` and `python` on `PATH`, on a repository with a root Python project, `web/package-lock.json`, `svc/go.mod`,
  a `pyproject.toml` project, and a manifest under `node_modules` that must be skipped, and holds that each project is
  audited and has its SBOM (which also replaces P2-R7's static test with one that runs).

## Pillars

- P1 applies — P2-R8 and P2-R9 are the requirement; `.agent-rfc/designs/supply-chain-audits-that-can-fail.md` is the plan.
- P2 applies — `scripts/compliance_checks.py` (`_supply_chain_job`) and `workflow-templates/agentsmith-supply-chain.yml` change in place; no dependency.
- P3 n/a — no spans or evaluations.
- P4 applies — `scripts/test/test_compliance_checks.py` holds each refused shape, and runs the template's scripts; hand mutants after.
- P7 applies — `workflow-templates/agentsmith-supply-chain.yml`: Python, npm and Go projects anywhere in the repository.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no routing.
- P11 n/a — no untrusted content reaches a model here.
- P12 n/a — no secrets.
- P13 applies — `scripts/compliance_checks.py`: green needs an audit that can turn the job red.
- P14 n/a — no fixture or baseline.
- P15 applies — `scripts/compliance_checks.py`: the pass message says it read the workflow, and which projects the template covers.
- P16 applies — `CHANGELOG.md`: a tenant's own supply-chain workflow may newly fail the check; `agentsmith sync` brings the template.

## Deviations

none

## Dependencies

none

## Levers

- `gate-integrity` — a check that can be satisfied by text that runs nothing is not a check (P2-R8).
- `aggregates-name-their-scope` — "audits each stack" now means each project in the repository (P2-R9).
- `test-the-contract` — the template's scripts are run, not read.
- `grep-for-siblings` — P2-R7's SBOM, beside the audits and the trigger.
- `test-that-cannot-fail` — hand mutants.
