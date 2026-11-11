# Review: sovereign-build-side

Step 2 of the owner's plan for the Friday release (2026-11-11): the CI runner as a setting, and honest documentation of what the build side depends on.

## Pass 1 — findings: 1

Against `docs/review-levers.md`.

1. **Three compliance tests fail when `test_vendoring_retired.py` runs before them,** and pass alone and in CI's alphabetical order. Pairing each earlier suite with them isolated it: a leak of state from that file, which this change does not touch. Not fixed here; recorded on the backlog, because CI's order hides it and it predates this change.

## Pass 2 — findings: 0

- All 12 template jobs read `vars.AGENTSMITH_RUNNER`, and `scripts/test/test_runner_setting.py` checks each one. A hand-made hard-wired runner in `ci-go.yml` fails it.
- `${{ … }}` in the templates does not collide with AgentSmith's own `{{PROVIDER_SETUP}}` and `{{AGENTSMITH_REF}}` placeholders, which are replaced by exact token.
- Template wiring, sync workflow, scratch-tenant, vendoring, environment-variable, gate-table and design-document suites: 252 passed, plus the three above in CI's order; ruff clean.
- The manual's new section and the README say exactly what is enforced where, and do not claim edit-time enforcement for the four agents whose hooks are unconfirmed (gap 11, owner's decision).

## Sign-off

Group 1 · DRY & shared code — [x] checked — one expression in every job, held by one test.
Group 2 · Quality / safety — [x] checked — unset is today's behaviour exactly.
Group 3 · Architecture / hygiene — [x] checked — one line per template; no new file in a tenant.
Group 4 · Process — [x] checked — design first; manual, README and CHANGELOG updated.
Group 5 · Intuitive UI — [x] n/a — no screen changes.
Group 6 · Signal integrity — [x] checked — the documentation states the cloud dependencies rather than implying none.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: `scripts/test/test_runner_setting.py`.
Mutation-checked: yes, by hand; a hard-wired runner fails the test.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; ruff; the process gate against the commit.

Levers reviewed: `declared-vs-enforced`, `test-that-cannot-fail`.

Scope at the first sign-off: kg:fedfae0fecd8

## Pass 3 — findings: 1

The 4.1.0 release review, verified first: listed every `uses:` in `workflow-templates/`, read the setup action and the sync workflow, and searched the templates for a mirror or base-URL setting (none).

1. **R8** — the sign-off said "the documentation states the cloud dependencies rather than implying none", and the section named runners and releases only. Rewritten: an air-gapped runner is not supported in 4.1.0; each outside dependency is named with its replacement; the fork pull-request warning added. `scripts/test/test_runner_setting.py` gains a test that every outside action a template uses is named in the section (it failed on `origin/main`'s manual, as did the test for the warning).

## Pass 4 — findings: 0

- `scripts/test/test_runner_setting.py`: 15 passed; the two new tests fail against the old section.
- Read against the templates as they stand after this PR's supply-chain change: `actions/setup-node`, `actions/setup-go` and `pnpm/action-setup` are named.
- Not done, and said in the section and the backlog: a setting to point the templates at a mirror.

## Sign-off (after the 4.1.0 review)

Group 1 · DRY & shared code — [x] n/a — documentation and one test.
Group 2 · Quality / safety — [x] checked — the fork pull-request risk is stated where a team turns self-hosted runners on.
Group 3 · Architecture / hygiene — [x] checked — the test reads the templates, so a new action must be documented.
Group 4 · Process — [x] checked — design addendum first; CHANGELOG updated.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — the manual no longer implies the build side can be kept inside with a mirror alone.
Group 7 · Auth & session integrity — [x] n/a — no auth code.

Tests added: two in `scripts/test/test_runner_setting.py`.
Mutation-checked: the two tests were run against the old manual and failed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suite above; the knowledge-graph check; the process gate against the commit.

Levers reviewed: `docs-match-behaviour`, `minimal-host-dependency`.

KG query: kg:2129972f0839
