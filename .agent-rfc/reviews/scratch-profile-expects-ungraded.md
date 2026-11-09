# Review: scratch-profile-expects-ungraded

The owner chose option A on 2026-11-09, after the first GitHub run of the `python-dubai-gov` scratch tenant.

## Pass 1 — findings: 3

Against `docs/review-levers.md`, and the tenant's finished run on GitHub.

1. **`SEC-MOD-001` failed for a reason nothing expected.** The tenant's hook imported `agentsmith`, undeclared in its `requirements.txt`. Fixed in the fixture: the hook declares its own result type. Without this the new check would, correctly, have stayed red.
2. **A run or job log that could not be read had no test,** though the design claims that case fails. Fixed: two tests.
3. **A passing job's summary still said `failure`** for that workflow, with nothing saying it was expected. Fixed: a summary row names the refusal.

## Pass 2 — findings: 0

- The parser, run on the three real GitHub logs, finds `fairness golden hallucination`, which is the matrix entry.
- The hook passes the same smoke `SEC-MOD-001` runs, and the tenant's test passes, in an environment holding only its `requirements.txt`.
- Five hand mutants all caught: any failure counted as refused; the set comparison dropped; an unreadable log ignored; the gates workflow also excused; the matrix dropping a suite.
- `scripts/test/test_scratch_tenants.py`: 29 passed.
- Left out on purpose: the tenant's `Supply chain` workflow failed because `pip-audit --no-deps` refuses an unpinned `requirements.txt`. The build does not wait on it, and it is a question about a shipped template, reported to the owner.

Not proven until this reaches `main`: the scratch job runs there and not on a pull request.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one script, called from the one job that needs it.
Group 2 · Quality / safety — [x] checked — `set -uo pipefail`; a job name is printed and never evaluated.
Group 3 · Architecture / hygiene — [x] checked — sits beside `build.sh`; a matrix field opts in, other tenants are untouched.
Group 4 · Process — [x] checked — design first, CHANGELOG and both documents updated.
Group 5 · Intuitive UI — [x] n/a — no screen changes.
Group 6 · Signal integrity — [x] checked — passes only on the exact set, judged from each job's log; unreadable means failed.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code; the token stays in the environment.

Tests added: eight in `scripts/test/test_scratch_tenants.py`.
Mutation-checked: yes, by hand; five mutants, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `scripts/test/test_scratch_tenants.py`; ruff; `bash -n`; YAML parse; the process gate and the `scratch_build` mutation suite against the commit.

Levers reviewed: `failure-is-not-a-result`, `test-that-cannot-fail`, `implemented-not-invoked`.

KG query: kg:0ec2f7db1960
