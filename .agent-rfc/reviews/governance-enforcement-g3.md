# Review — governance enforcement, G3 (the bypass sweep)

Design: `.agent-rfc/designs/governance-enforcement.md` § G3. Each slice keeps its own review
record: one record per change is what the gate checks, and one file for seven slices would
number its passes 1..N across work that shipped months apart.

**Built evidence (2026-09-16):**

- **Failing tests first.** `test_gate_sweep.py` (16) was written before `sweep`, and all 14 of the
  first cut failed at the missing subcommand.
- **Dogfooded here:** the first sweep in this checkout recorded 321 commits of existing history as
  its starting point and checked none of them, as designed.
- **Defects the tests found while building, each fixed:**
  - **a deadlock.** Blocking in `pre-commit`, as the design said, refuses the repair commit too —
    it is a commit, and `pre-commit` runs before the message that would say what it repairs
    exists. `pre-commit` now reports and re-arms; `commit-msg`, which has the message, refuses any
    commit that does not repair what is outstanding; `pre-push` refuses unconditionally. Recorded
    as an amendment in the design.
  - the design's scope did not cover `workflow-templates/**`, which G3 changes; added before editing.
- **Mutation checks (each reverted after):** nine — the sweep reporting no failure, a `Repairs:`
  trailer trusted without resolving it, `commit-msg` ignoring the sweep, `pre-push` never refusing,
  hooks not re-armed, a missing store counting as initialised, only the checked-out branch swept,
  and the drift check allowed to pass on failure again. Eight caught; the ninth is pass 1 below.

## Pass 1 — findings: 5

- `guards-must-be-able-to-fail` — **finding:** the ninth mutation survived. Trusting a `Repairs:`
  trailer without resolving it through git still failed the test that names an unknown sha, because
  an unresolvable token does not match a real one either way. A trailer naming a **short** sha is
  what separates the two: `test_a_repairs_trailer_may_name_a_short_sha` now pins it, and the
  mutation is caught.
- `minimal-host-dependency` — **finding:** the sweep runs at every commit, push, session start and
  turn end, and each commit costs several git calls. A fetched branch of 500 commits would have
  made the next session start a minute of silence. It now takes the oldest `AGENTSMITH_SWEEP_BATCH`
  (200) and says how many remain; nothing is skipped, because an unchecked commit stays unverified.
  Pinned by a test that sets the batch to 2.
- `ambiguous-signals` — **finding:** the verified store caps at 5000 shas and dropped the oldest
  silently, so a repo past the cap would quietly re-check old commits with no explanation. The drop
  is now reported with its consequence.
- `ambiguous-signals` — **finding:** the stop gate printed "Unreviewed gated changes:" above sweep
  findings, which are a different thing — a committed bypass, not an uncommitted edit. The heading
  now names what was actually found.
- `docs-match-behaviour` — **finding:** `agentsmith gates repair` was absent from SPECS.md's command
  table (UserManual.md's was caught by the repo's own test), and the docs did not say that the
  sweep's two blocking hooks live in `.githooks/`, so a repo on the machine-wide template hooks
  gets it only at session start and in CI. Both stated.

Also caught by the repo's own gates while fixing the above: `AGENTSMITH_SWEEP_BATCH` was read by
the code and documented nowhere (`test_documented_env_vars_exist`), and is now in UserManual.md's
runtime-flags table.

## Pass 2 — findings: 2

- `test-that-cannot-fail` — **finding:** nothing pinned the fix for the deadlock. Every test that
  exercised it went through `git commit`, where a failure is the same whether `pre-commit` or
  `commit-msg` refused — so restoring the blocking `pre-commit` would have passed the suite and
  brought the deadlock back. `test_pre_commit_itself_never_refuses_so_the_repair_can_be_committed`
  runs the hook directly and requires exit 0 with the pending commits named; mutating the hook back
  now fails three tests.
- `no-redundant-artifacts` — **finding:** `cmd_stop` walked the working tree twice, calling
  `stop_problems` again just to choose a heading. Once, into a variable.

## Pass 3 — findings: 0

Every lever over the final G3 diff: the sweep and its store, the two hooks, the launcher's argument
forwarding, `commit-msg`'s repair check, `gates repair`, the workflow templates and the docs.
`scripts/test/` and `runtime/test/` 1409 passed with 10 skipped, `ruff check .`, SPECS tree drift,
`--check-hooks`, `--check-kg`, the registry drift check, `bash -n` and ShellCheck on the installer
and all five hooks, and eleven mutations of the new blocking paths, each caught.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_sweep.py (17), test_process_gate.py (+2: the re-armed
                          session start, and the clone that cannot be armed),
                          test_workflow_template_wiring.py (+3: governance steps block)
Mutation-checked:          yes — eleven, each reverted: the sweep reporting no failure, a
                          Repairs: trailer trusted without resolving it, commit-msg ignoring
                          the sweep, pre-push never refusing, hooks not re-armed, a missing
                          store counting as initialised, only the checked-out branch swept,
                          the drift check allowed to pass on failure, pre-commit blocking
                          again (the deadlock), and the batch cap skipping instead of deferring
Fixtures re-pinned:        yes — the gated-repo fixture carries the two new hooks, and is
                          re-exported from scripts/test/conftest.py so both gate suites build
                          one repo shape
Gates run locally:         ruff check . (clean), scripts/test/ + runtime/test/ (1409 passed,
                          10 skipped), SPECS.md tree drift, verify_system.py --check-hooks and
                          --check-kg, generate-ide-config.py --registry --check-only, bash -n
                          and ShellCheck (0 warnings) on the installer and all five hooks, and
                          the sweep against this checkout — it recorded 321 commits of history
                          as its starting point, as designed
Declared gaps:             (1) the Knowledge Graph CI step stays warn-only until G4 provisions
                              the graph; pinned with its reason by a test;
                          (2) the sweep's two blocking hooks are .githooks/; a repo on the
                              machine-wide template hooks gets it at session start and in CI
                              only — stated in docs/process-gates.md;
                          (3) OTS and KYC Sentinel adopt the new hooks when they re-sync (T3);
                          (4) merge commits are not swept, the same rule the CI gate has always
                              used for a pushed range.
```
