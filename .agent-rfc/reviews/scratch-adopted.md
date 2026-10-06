# Review — scratch-adopted

Design: `.agent-rfc/designs/scratch-adopted.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 2

- **A tenant receives `.githooks/`, and nothing rebuilt the scratch tenants when it changed.** The
  workflow's path list named what the hook vendors (`hooks/**`, `scripts/**` …) but not the launcher
  and gate hooks an adopted tenant copies. Added — and `process-gates.json`'s CHANGELOG paths with it,
  which a test keeps equal to that list, so a change to the gate hooks now needs a CHANGELOG entry
  (every tenant receives them). Design amended.
- **The docs said "five" in two places** (`docs/scratch-tenants.md`'s opening and the token setup);
  the token's repository selection in particular must now include the sixth, or the job fails at
  checkout. Both say six, and when the sixth was added.

## Pass 2 — findings: 0

Proved on GitHub before the job existed: `adopt.sh` run here at `main`'s commit, pushed to
`agentsmith-scratch-adopted` — its "AgentSmith gates" run (the provider installed through
`setup-agentsmith@<sha>`, the gate's `ci` event, the rules check) and its own "CI" both succeeded;
the adoption commit passed its contract-3 commit gate and its `pre-push` sweep on the way out.
Locally: the three new tests (the adoption passed the gate, refs pinned, the tenant's CI untouched,
the gates armed; a second build starts from a clean history; the job waits on both workflow names
and pins `$GITHUB_SHA`), the scratch and process-gate suites, every `git ls-files` test, ruff, the
tree check, `bash -n adopt.sh`, the script tracked executable.

## Sign-off

Group 1 · DRY & shared code — [x] checked — `adopt.sh` drives the real `tenant adopt` and copies its source the way `build.sh` does; the job reuses the install step and the wait pattern.
Group 2 · Quality / safety — [x] checked — three new tests; the path ran green on GitHub before the job existed.
Group 3 · Architecture / hygiene — [x] checked — the scratch source is a plain library (no allowlist entry needed); no framework code changes.
Group 4 · Process — [x] checked — design before code; owner-approved repository and force-push; backlog item closed, new findings logged; CHANGELOG entry.
Group 5 · Intuitive UI — [x] checked — the job summary lists each of the tenant's two workflows with its run and conclusion.
Group 6 · Signal integrity — [x] checked — the job fails unless both workflows succeed, and names the failing job and step.
Group 7 · Auth & session integrity — [x] checked — `SCRATCH_TENANTS_TOKEN` by name; the owner adds the new repository to its selection.

Tests added: three in `scripts/test/test_scratch_tenants.py`.
Mutation-checked: n/a — CI configuration and a build script; each test asserts a property the build could lose.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` regenerated (the self-test's freshness check), and again after rebasing onto main (#37 and #39 merged), with the CHANGELOG entries of both kept.
Gates run: the scratch and process-gate suites and every `git ls-files` test on the staged tree (188 passed); `ruff check .`; the tree check; `verify_system.py --check-kg`; `bash -n adopt.sh`; the adopted tenant built and its CI run on GitHub.

Levers reviewed: `declared-vs-enforced`, `test-the-contract`, `run-the-gates-ci-lists`.

KG query: kg:f81d5e052b3c
