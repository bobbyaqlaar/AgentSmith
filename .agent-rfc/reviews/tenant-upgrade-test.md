# Review: tenant-upgrade-test

Step 2 of the owner's list of 2026-11-09: a test that moves a tenant from the last release forward, and a fix for whatever it finds.

## Pass 1 — findings: 5

Against `docs/review-levers.md`, driven by a prototype run of the upgrade in the sync workflow's own environment.

1. **`sync` could lower a tenant's pin** (`v4.0.1` to `v3.0.0`), from a stale package record in this checkout. Fixed: `plan_sync` refuses, comparing only released versions of AgentSmith's own setup step.
2. **`sync` dropped what `tenant init` declared:** the eval warnings and the telemetry `emitter`. Already in 4.0.x. Fixed: `_keeping_declared`, and a profile still loses the warnings because `with_profile_ports` runs after.
3. **`sync` wrote a design without redrawing the graph,** so a created tenant's `kg check` failed on its sync pull request. Fixed.
4. **`tenant adopt` drew the graph before its records.** Fixed: drawn after them, and the manifest rewritten so the graph's hash is right.
5. **`docs/DESIGN.md` did not list the new script.** Found by `test_design_tree_drift.py`. Fixed.

Two results looked like defects and are not. Going on the profile is refused under `Review: n/a: framework sync`, because it needs a real design with the profile's extra pillars; the gate is right. An adopted tenant's evals are red after a sync, because it never declared the warnings a new repository gets.

## Pass 2 — findings: 0

- `scripts/check_tenant_upgrade.sh v4.0.1` passes on the staged tree, by `tenant init` and by `tenant adopt`, using only what the sync workflow installs.
- Six hand mutants, one per fix and direction, each fail a named test. With the declarations dropped, or the graph not redrawn, the upgrade check itself fails.
- `framework_sync`, `tenant_adopt` and `vendoring_retired` mutation suites run against the commit, so a target these edits moved is found before CI.
- A tenant that did not ask for the profile gets nothing of it, and a second sync changes nothing.

Left alone: `framework_version()` still prefers an installed package record, which is how a real install reports itself. The stale `agentsmith_runtime.egg-info` in the owner's checkout is local and ignored by git.

## Sign-off

Group 1 · DRY & shared code — [x] checked — the script reuses the release-install check's shape; the graph is drawn by the one mapper.
Group 2 · Quality / safety — [x] checked — a malformed declaration is not comparable and is left alone; a mapper failure is said.
Group 3 · Architecture / hygiene — [x] checked — no new dependency; both trees come from `git archive`, so nothing untracked answers.
Group 4 · Process — [x] checked — prototype first, then design; CHANGELOG, backlog and the repository tree updated.
Group 5 · Intuitive UI — [x] n/a — no screen changes.
Group 6 · Signal integrity — [x] checked — a crash in any port fails; a scaffold's expected red is told apart from no answer.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code; the check runs with an empty `HOME`.

Tests added: eleven cases in `scripts/test/test_framework_sync.py`; `scripts/check_tenant_upgrade.sh` as a Self-Test gate.
Mutation-checked: yes, by hand; six mutants, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `test_framework_sync.py`, `test_tenant_adopt.py`, `test_sync_workflow.py`, the related suites and `test_design_tree_drift.py`; ruff; mypy; the upgrade check; the process gate, knowledge-graph check and three mutation suites against the commit.

Levers reviewed: `implemented-not-invoked`, `failure-is-not-a-result`, `grep-for-siblings`, `test-that-cannot-fail`.

KG query: kg:8b5f1634ec34
