# Review: supply-chain-audits-that-can-fail

Each fix has tests that fail without it. P2-R8: ten shapes in `scripts/test/test_compliance_checks.py`
(`test_an_audit_that_cannot_fail_or_never_runs_does_not_count`) each passed the old check, the review's four among
them. P2-R9: `test_the_template_audits_every_project_in_the_repository` runs the template's own `run:` scripts with
stand-in `pipx`, `npm`, `npx`, `go` and `python`, and failed on the old template (no npm audit for `web/`, no Go audit
for `tools/`). The same test now holds P2-R7 by running it: the `pyproject.toml` project's SBOM is taken from an
environment the project was installed into. The static P2-R7 test it replaces is removed.

## Pass 1 — findings: 0

Against `docs/review-levers.md`, by hand mutants (eleven).

- P2-R8: an audit matched anywhere in a line (so inside `echo`); a fallback allowed; `set +e` allowed; a job-level `if:`
  allowed; `continue-on-error` on the step allowed; branch filters ignored; `|| exit 1` read as a fallback. All killed.
- P2-R9: `node_modules` and virtual environments not pruned for Python; npm at the root only; Go at the root only; the
  `pyproject.toml` project not installed before its SBOM. All killed.
- The shipped template passes its own check (`test_the_shipped_template_passes_its_own_check`), and a failing audit
  inside the new per-project loop still fails the step (`test_a_failing_scan_fails_the_step`, unchanged).
- `scripts/test/test_compliance_checks.py`, `scripts/test/test_runner_setting.py`, `scripts/test/test_scratch_tenants.py`:
  122 passed. ruff clean.
- Stated, in the CHANGELOG: a tenant whose own workflow only appeared to audit now fails; a repository with a
  `requirements.txt` outside the root (documentation builds) now has it audited, which can surface findings that were
  never looked at. Both are the point of the change.
- Not run: the template on a GitHub runner. Its steps ran here under `bash -e` with stand-in tools; the real tools'
  arguments are unchanged from the shipped template apart from the project path.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one discovery pattern per stack; one rule set for what counts as an audit.
Group 2 · Quality / safety — [x] checked — green needs an audit that can fail the job; failures inside the loop still fail the step.
Group 3 · Architecture / hygiene — [x] checked — the check and the template change in place.
Group 4 · Process — [x] checked — design first; CHANGELOG and backlog updated.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — the check's failure message says what an audit must be; the template names every project it scanned in its SBOM files.
Group 7 · Auth & session integrity — [x] n/a — no auth code.

Tests added: eighteen cases in `scripts/test/test_compliance_checks.py` (ten refused shapes, six accepted, the template passing its own check, the template run on a multi-project repository); two expectations updated; the static P2-R7 test removed.
Mutation-checked: yes, by hand; eleven mutants, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; ruff; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `gate-integrity`, `aggregates-name-their-scope`, `test-the-contract`, `grep-for-siblings`, `test-that-cannot-fail`

KG query: kg:57fd0cd9d5d7
