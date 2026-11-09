# Review: supply-chain-audits-unpinned

The owner chose on 2026-11-09 to scan an app with no lock file rather than require one.

## Pass 1 — findings: 1

Against `docs/review-levers.md`.

1. **The helper in the new tests re-imported `os` and `subprocess`,** which the file already imports. Removed.

Checked and sound: a lock still takes precedence and keeps the exact-pin mode, the SBOM step is unchanged and still lock-only, and a scanner failure stops the step under `bash -e` because the command is no longer followed by `exit $?`.

## Pass 2 — findings: 0

- The tests run the shipped step from the template, under `bash -e`, against a fake `pipx`, in all four cases: a lock, ranges with no lock, no file, and a failing scan.
- Four hand mutants all caught: requirements put back in exact-pin mode; a scanner failure swallowed; the lock ignored; no file still scanning.
- `pip-audit==2.9.0 -r` on the `python-dubai-gov` tenant's real `requirements.txt` resolves it and reports no known vulnerabilities.
- `scripts/test/test_compliance_checks.py` and `scripts/test/test_compliance_port.py`: all pass after the rebase on `main`.

A tenant on an older release keeps the old step until `agentsmith sync` brings this one.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one step changed; the tests read the template rather than copy it.
Group 2 · Quality / safety — [x] checked — the tool stays pinned; a finding still fails the job.
Group 3 · Architecture / hygiene — [x] checked — no new file in the template and no new dependency.
Group 4 · Process — [x] checked — design first; CHANGELOG updated for a path tenants receive.
Group 5 · Intuitive UI — [x] n/a — no screen changes.
Group 6 · Signal integrity — [x] checked — an audit that could not run fails the step; no requirements file says so and scans nothing.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: five cases in `scripts/test/test_compliance_checks.py`.
Mutation-checked: yes, by hand; four mutants, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the two test files above; ruff; YAML parse; a real `pip-audit` run; the process gate and knowledge-graph check against the commit.

Levers reviewed: `failure-is-not-a-result`, `test-that-cannot-fail`, `implemented-not-invoked`.

KG query: kg:295c32fad7db
