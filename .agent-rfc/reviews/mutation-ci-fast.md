# Review — curated mutations: only what a pull request can affect, in parallel

Design: `.agent-rfc/designs/mutation-ci-fast.md`. Owner request, 2026-10-14: "Why taking so long? Can
this not be optimised"; approach approved the same day, to be built after the 3.0.0 release.

**Built evidence:**
- **`scripts/mutation_check.py`:**
  - `triggers(suite)`: a suite's `watch`, the files its mutations edit, its tests,
    `imported_by(test)` (direct repository imports, from the syntax tree), and `SHARED_TRIGGERS`;
  - `select_suites` narrows every suite by them;
  - `shard(suites, k, n)` deals by `MINUTES`, measured on run 38470842052;
  - `--shard K/N`;
  - a new `scratch_build` suite.
- **`.github/workflows/self-test.yml`:**
  - a `mutations` job, a four-way matrix with `fail-fast: false`, narrowed only on a pull request;
  - weekly and manual triggers;
  - the required "Python scripts/runtime/examples" job `needs: mutations`, runs `!cancelled()`,
    and its last step fails unless the shards' result is `success`.
- **`scripts/gate_steps.py`:** locally, a pull request's base is the merge-base, and `matrix.shard`
  is empty, so one process runs every shard.
- **Tests:**
  - `test_mutation_check_scope.py` rewritten (37): selection by triggers, imports read from real
    test files, the guarantee over the real catalogue, shard coverage and balance, bad shard
    specs, an empty shard, and the workflow's wiring;
  - `test_gate_steps.py` (+1);
  - `test_framework_python_env.py` names the jobs that install the lock.

## Pass 1 — findings: 7

Found while building, each checked before it was changed:

1. `failure-mode-visibility` — **The first shard weights, mutations × test files, dealt 14.4 minutes
   to one shard and 7.2 to another**, measured against the minutes each suite took on #54.
   **Fix:** shards are dealt by those minutes (`MINUTES`); a stale value costs balance, never a
   result. The four shards come to 10.2, 10.1, 10.0 and 10.0 minutes; `framework_sync` alone is
   10.0, the floor.
2. `declared-vs-enforced` — **`pyproject.toml` and `scripts/requirements-*.txt` were shared
   triggers.** Replaying #57's real change set, a version bump and docs, ran all 32 suites. pytest
   reads `pytest.ini` here; `pyproject.toml` is packaging, ruff, mypy and mutmut. The mutation job
   installs `requirements.lock`, not the gate's requirements. **Fix:** both left out; #57 now runs
   `installed_machine` alone, for its installer change.
3. `run-the-gates-ci-lists` — **The mutation step stopped running locally.** Its base became the
   pull request's alone and its shard a matrix value, neither of which `gate_steps` could resolve,
   so `agentsmith gates run` would have skipped it. **Fix:** locally the base is the merge-base and
   the shard empty, and the step's script passes `--shard` and `--changed-since` only when set.
4. `run-the-gates-ci-lists` — **The shard verdict was untagged, and a blocking CI step must carry
   the tag** (`test_every_blocking_check_in_this_repos_ci_carries_the_tag`). **Fix:** tagged.
   Locally it is skipped by name: `${{ needs.mutations.result }}` has no local answer, as
   `runnable` reports.
5. `test-that-pins-a-defect` — **`test_self_test_installs_the_lock_at_the_pinned_version` counted
   two lock installs**, a number, not the property. **Fix:** it names the three jobs that run the
   framework's Python and asserts each installs the lock.
6. `declared-vs-enforced` — **`scratch_build`'s test builds from `.github/scratch-tenants/`, which
   it runs rather than imports**, so its triggers missed the apps. **Fix:** the suite watches them.
7. `every-line-earns-its-place` — **A helper named `test_imports` in the runner reads as a test.**
   **Fix:** `imported_by`.

## Pass 2 — findings: 0

- **Replayed on the real change sets of the merged C9 fixes and the release:**
  - a fix touching the scratch test runs `tenant_adopt` and `scratch_build`;
  - one also touching the Python template adds `vendoring_retired`;
  - the release runs `installed_machine`.

  Every suite's own mutated files and tests trigger it, over the real catalogue.
- **The new suite catches:** the `scratch_build` mutation is caught by the runner, and the tree is
  clean after it.
- **The plan, from the CLI in a Python 3.11 venv holding only `requirements.lock`:** each shard
  prints the suites it was dealt. The changed tests pass there (82).
- **The gate holds:** the required check's name and meaning are unchanged (`main`'s required
  contexts read on 2026-10-14). A failed, cancelled or skipped shard fails it, and `fail-fast:
  false` keeps one shard's failure from hiding another's.
- **Not run:** `actionlint` (not installed). This pull request changes the runner, a shared
  trigger, so its own CI runs all four shards in full, the first real run of the new wiring.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one selection (`select_suites`) for the CLI and CI; triggers derive from the files a suite already names, not a second hand-kept list.
Group 2 · Quality / safety — [x] checked — `test_mutation_check_scope.py` (37), `test_gate_steps.py` (+1), the lock test; the `scratch_build` mutation caught; the changed tests run in CI's environment.
Group 3 · Architecture / hygiene — [x] checked — no dependency added (`ast` is the standard library); the required check keeps its name and meaning, so no branch-protection change.
Group 4 · Process — [x] checked — design before code with the owner's approval; CHANGELOG Unreleased; the generated gates table in `docs/validation-checklist.md`.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — every skip is named, each shard prints its share, an empty shard says so, and a failed shard's verdict names it.
Group 7 · Auth & session integrity — [x] n/a — no credential handling; the workflow reads commit SHAs only.

Tests added: `scripts/test/test_mutation_check_scope.py` (rewritten, 37), `test_a_sharded_pull_request_step_runs_here_as_one_whole_change`; `test_self_test_installs_the_lock_at_the_pinned_version` now names its jobs.
Mutation-checked: `scratch_build` 1/1.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: full `pytest` on the staged tree (2379 passed, 10 skipped); the changed tests again in a Python 3.11 venv holding only `requirements.lock` (82); every gate of the self-test's Python job that runs here — the repo-tree check, `ruff`, `mypy` (1.14.1, Python 3.11 with `requirements.lock`), py_compile, redaction for both profiles, `--check-hooks`, `--check-kg`, the delivery evidence pack — and the workflow parsed as YAML; `actionlint` not run (not installed).

Levers reviewed: `gate-integrity`, `declared-vs-enforced`, `failure-mode-visibility`, `ambiguous-signals`, `test-the-contract`, `run-the-gates-ci-lists`.

KG query: kg:b4f077ff7e4e
