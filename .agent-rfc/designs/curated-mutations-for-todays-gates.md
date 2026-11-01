---
status: done
scope:
  - scripts/mutation_check.py
  - scripts/test/test_vendoring_retired.py
---
# The three gate fixes of 2026-10-30 get curated mutations

## Problem

Four slices landed on 2026-10-30 and 2026-10-31 that changed gate code — code
whose whole job is to fail when something is wrong:

| slice | code | on main |
|---|---|---|
| `kg-check-sees-tracked-guardrails` | `_kg_shape` in `scripts/verify_system.py` | `60e0cf0` |
| `scaffold-graph-knows-its-own-records` | `init_tenant`'s tail in `runtime/cli.py` | `7c74caf` |
| `gate-base-is-the-base-branch` | `_merge_base` in `scripts/gate_steps.py` | `c4ed3a5` |

Each slice's review record claims mutation evidence, and that evidence is real —
I ran the mutants by hand and every one failed a test. But `scripts/mutation_check.py`
has no entry for any of them, so **CI re-runs none of them**. The evidence exists
once, in a review record, in prose. The next edit to any of these three functions
can quietly remove the guard and the suite stays green — which is exactly the
failure the curated catalogue exists to prevent, and exactly the failure
`_kg_shape` itself was fixed for: `beeb838` committed a graph missing a Guardrail
node, the check reported no drift, and 11 checks passed over it.

Worse, two of the three are *gates*. A gate whose own guard is unasserted is the
`guards-must-be-able-to-fail` lever turned on the framework itself.

There is also a gap inside the third slice. `init_tenant`'s mapper call is
wrapped in `if framework is not None:` because **mypy** caught `None / "scripts"`,
not because a test did. No test scaffolds a tenant with no installed framework,
so a mutation removing that guard would survive — which means it cannot honestly
be added to the catalogue (the module's rule: every entry must have failed a test
at the moment it was added).

## Approach

Add two new suites and extend one, then close the one gap that blocks an honest
entry.

**New suite `kg_drift_gate`** — tests `scripts/test/test_kg_drift_gate.py`,
mutations in `scripts/verify_system.py`. Five mutations, one per property the
guardrail half of `_kg_shape` holds:

1. guardrails leave the shape entirely (the `beeb838` regression, reproduced)
2. a guardrail's title stops being compared
3. a guardrail's pillar stops being compared
4. the trackedness filter is dropped, so generated and absolute-path guardrails
   are compared again — the churn that made the gate a false positive
5. `created_at` joins the shape, making the comparison depend on a clock

**New suite `gate_steps`** — tests `scripts/test/test_gate_steps.py`, mutations in
`scripts/gate_steps.py`. Three mutations, one per link of `_merge_base`'s chain:

1. the base is the branch's own remote again (`@{upstream}`) — the original defect
2. `origin/HEAD` unset yields no base instead of `origin/main`
3. a one-commit branch with no merge base yields no range instead of `HEAD~1`

**Extend `vendoring_retired`** with three mutations in `runtime/cli.py`:

1. the mapper never runs, so a scaffolded tenant is born stale
2. the mapper runs *before* `write_scaffold_records`, the original ordering bug.
   Expressed as a reorder of the two statements, which means the entry's `before`
   spans the explanatory comment between them. That is deliberate: the comment is
   the reason for the order, and an edit that rewrites it should force the
   evidence to be re-confirmed, which is what a stale target means here.
3. the `framework is not None` guard is removed

Mutation 3 needs a test first: `test_a_scaffold_without_an_installed_framework_still_completes`,
which monkeypatches `_framework_dir` to `None` and asserts `init_tenant` returns
written files rather than raising. `seed_tenant_data` and `_provision_governance`
already handle `framework is None`, so the guard is the only unprotected use.

Suites go at the end of `CATALOGUE`, in the order the slices landed. No `watch`
globs: every mutation edits a file the suite's tests import, which the trigger
computation already follows.

## Pillars

- P1 applies — this design, scope-limited to `scripts/mutation_check.py` and
  `scripts/test/test_vendoring_retired.py`, the one test file that gains a case. The three gate files are *edited transiently by the tool*,
  never committed changed, so they are not in scope.
- P2 applies — searched the catalogue first (`--list`, 33 suites): `vendoring_retired`
  already owns `test_vendoring_retired.py` and already carries one `_kg_shape`
  mutation, so the `runtime/cli.py` entries extend it rather than start a rival
  suite; `knowledge_graph` owns `map_codebase.py` and keeps the absolute-path and
  gitignore mutations. Two genuinely new test files get two new suites. No
  dependency added. Knowledge-graph impact: none — no new file, no new import.
- P3 n/a — adds no execution path. `mutation_check.py` is a developer and CI
  tool; the gate spans it already emits are unchanged.
- P4 applies — `scripts/mutation_check.py` is itself the P4 answer for three
  earlier slices. Each of its 11 new entries must fail at least one named test
  before it is committed,
  verified by running `python3 scripts/mutation_check.py kg_drift_gate gate_steps vendoring_retired`,
  which applies and reverts each edit itself. The one new test fails before the
  guard exists and passes after.
- P7 applies — Python: `from __future__ import annotations` already at the top of
  both files, frozen dataclasses for entries, no `Any`. The new test takes
  `monkeypatch` and `tmp_path` like its neighbours.
- P8 n/a — emits no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — calls no LLM.
- P11 applies — the `Mutation` entries in `scripts/mutation_check.py` are literal
  source text matched against this repository's own tracked files (`scripts/verify_system.py`,
  `scripts/gate_steps.py`, `runtime/cli.py`); nothing here reads untrusted input. The one new
  test reads only paths it creates under `tmp_path`.
- P12 n/a — touches no credential. No entry's `before`/`after` carries a secret.
- P13 applies — `scripts/verify_system.py`, `scripts/gate_steps.py` and
  `runtime/cli.py` hold the three guards this serves, moving each from
  *declared* (prose in a review record) to *enforced* (re-run by CI). Nothing gets
  weaker. The declared half that remains: `scripts/mutation_check.py` proves a mutation is
  *caught*, not that the catalogue is *complete* — mutmut's non-blocking job is the
  exhaustive half, and this adds nothing to it.
- P14 applies — makes no fixture stale. Entry 2 of the `runtime/cli.py` group pins
  a comment's text as part of its `before`, so rewriting that comment makes the
  target stale; the module's documented remedy applies (re-point and re-confirm,
  do not delete). No golden or baseline file changes.
- P15 applies — a surviving mutation makes `scripts/mutation_check.py` print the
  entry name and the suite, and exit 1; "target absent" is reported as a distinct, documented outcome from
  "survived", so a refactor that moves the code does not read as a passing check.
  Both are already implemented in the runner; the new entries inherit them.
- P16 applies — the runner keeps pristine copies outside the repo (`_backup_dir`)
  and restores on exit, including on SIGINT. If a run is killed harder than that,
  the mutated file is a tracked file with a one-line diff, recovered with
  `git checkout --`. The new entries add no new recovery path.

## Deviations

none

## Dependencies

none

## Levers

- `guards-must-be-able-to-fail` — the point of the change. Three guards had no
  re-runnable proof that they can fail.
- `implemented-not-invoked` — hand-run mutants are not invoked by anything. An
  entry in the catalogue is.
- `test-that-pins-a-defect` — each of the 11 mutations reproduces the specific
  defect its slice fixed, not a generic break.
- `gate-integrity` — two of the three targets are gates; an unasserted gate guard
  is the worst case of this lever.
- `no-copy-paste` — `vendoring_retired` is extended rather than cloned, because
  it already owns that test file; the two new suites exist only because their
  test files have no owner.
- `one-catalog` — the curated entries live in `CATALOGUE` alone; no second list.
- `expect-re-review` — entry 2 will go stale if the comment it spans is rewritten,
  and that is the intended signal.
