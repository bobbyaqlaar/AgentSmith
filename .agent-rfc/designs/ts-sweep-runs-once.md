---
status: done
scope:
  - scripts/test/test_ts_runner_invocations.py
---
# The TypeScript-runner sweep runs once, and states its alias premise once

## Problem

Same audit as `.agent-rfc/designs/tree-drift-test-reads-once.md`, applied to the
file I extended by 250 lines in `aa44e03` and signed off with the Group 1 line
*"one `where` builder, one predicate per rule"* — a claim about the `where`
string, phrased so it read as a claim about the file. Measured, two things:

- **The repository is swept three times.** `_invocations()` runs
  `git ls-files --cached --others --exclude-standard` and then reads every
  tracked `.py`, `.sh` and `.mjs` file. Measured here: **910 candidate paths,
  297 of them read, 53–103 ms warm per call**, and three call sites
  (`test_the_sweep_finds_the_known_invocations:177`,
  `test_every_runner_invocation_passes_the_loader:233`,
  `test_the_exempt_invocations_import_nothing_needing_resolution:331`). Two
  thirds of that is repeated work. The file's wall time swings between `0.24s`
  and `10.91s` across runs, and this sweep is its dominant term.
- **The alias premise is written twice, verbatim.** Lines 289–290 and 339–340
  are character-for-character identical:

  ```python
  aliases = tuple(_alias_prefixes())
  assert aliases, "portal/tsconfig.json declares no path alias — the premise changed"
  ```

  Each call re-reads `portal/tsconfig.json`. Two copies of one premise, which is
  the shape that produced the `IGNORE_SECOND` divergence in the sibling file.

## Approach

**Two module-scoped fixtures, matching what
`scripts/test/test_design_tree_drift.py` now does and what
`scripts/test/test_gate_steps.py` did first.**

- `invocations` — `_invocations()` once per module. Three sweeps become one; the
  three tests take it as a parameter, so each test's inputs are visible in its
  signature.
- `aliases` — `tuple(_alias_prefixes())` with the premise assertion **inside the
  fixture**, so it is stated once and is checked before either test body runs.
  A fixture that asserts is the right home for a premise two tests share: if
  `portal/tsconfig.json` ever declares no alias, both tests error out naming
  that reason rather than one of them quietly comparing against an empty tuple.

**Nothing else moves.** `EXEMPT`, `EXEMPT_INVOCATIONS`, `PROXIMITY_LINES`,
`DEEP_DIRS`-equivalents, every regex and all eight assertions stay exactly as
they are, so no verdict can change.

**Deliberately NOT consolidated:**

- `import sys as _sys` and the two `_sys.path.insert(...)` lines appear in both
  `test_shared_root_matches_runtime_root` and `test_dotenv_parsers_agree`. Both
  predate this session, and the duplication is the *subject* of those tests —
  they exist because `scripts/_shared` and `runtime.config` deliberately mirror
  each other and neither may import the other. Six duplicated lines would become
  a three-line helper plus two calls: no real saving, and it would edit two
  passing tests that nothing is wrong with.
- `test_the_exempt_invocations_import_nothing_needing_resolution` is 36 code
  lines, the largest in the file. It is one premise checked end to end — stale
  exemption, entry point resolved, parse non-empty, offenders — and splitting it
  would re-read the same entry point four times to assert four halves of one
  statement.

## Pillars

- P1 applies — this note precedes the edit; the three call sites and the two duplicated lines are named with line numbers in `## Problem`, and the measurements are recorded in `.agent-rfc/reviews/ts-sweep-runs-once.md`.
- P2 applies — no new module; two fixtures in `scripts/test/test_ts_runner_invocations.py`, the shape `scripts/test/test_design_tree_drift.py` and `scripts/test/test_gate_steps.py` already use.
- P3 n/a — a pytest guard, no traced runtime path.
- P4 applies — the file's eight tests are the control, and the mutants from `aa44e03` are re-run: `_shell_invocations` not splitting, `_specifiers` returning `[]`, `_alias_prefixes` returning `set()`, the entry point dropped from the `where` label, `_needs_resolution` losing each half, `_missing_loader` returning `False`, the loader dropped from the first and last link of `scripts.test`, `db:migrate` renamed, and a relative import added to `portal/scripts/migrate.ts`. Each must still fail, and the same tests as before.
- P7 applies — `@pytest.fixture(scope="module")` memoises per module, correct here because both values are read-only and no test mutates them. The file did NOT import `pytest` — I assumed it did and collection failed with `NameError: name 'pytest' is not defined` — so the import is added; `pytest` comes from `requirements.lock` (`pytest==8.4.2`) and 64 of the 96 files in `scripts/test/` already import it.
- P8 n/a — no telemetry; `scripts/test/**` emits no spans.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — unchanged: the sweep reads `portal/package.json`, `portal/tsconfig.json` and tracked `.py`/`.sh`/`.mjs` files from this checkout, with `json.loads` and regexes, executing nothing. Moving the reads into fixtures adds no source.
- P12 n/a — no credentials.
- P13 applies — this touches a required check, so the risk is a fixture that makes the sweep examine less. `_invocations()` itself is untouched, the fixture returns its list unmodified, and `test_the_sweep_finds_the_known_invocations` still asserts the per-link count against `script.count(RUNNER)` and the absence of duplicate labels — so a fixture that returned a truncated list fails there. The eleven mutants are re-run to prove the verdicts did not move.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated and re-pinned, verified by diffing node ids rather than by `agentsmith gate kg check` alone, which reported green over a fixture missing a `Guardrail` node on 2026-10-26.
- P15 applies — a premise asserted in two places can drift in one of them, which is exactly how the sibling file's wildcard sweep came to be missing its `IGNORE_SECOND` subtraction. The `aliases` fixture gives the premise one home and one answer.
- P16 applies — if either fixture returned something empty, `test_the_sweep_finds_the_known_invocations` fails (it requires `scripts.test` to yield one invocation per link, more than one link) and the `aliases` fixture's own assertion fails before any test body runs.

## Deviations

none

## Dependencies

None added. `import pytest` is new to this file but not to the repository —
`requirements.lock` pins `pytest==8.4.2` and it is the test runner this
directory already runs under.

## Levers

- `no-copy-paste` — two verbatim copies of the alias premise become one fixture.
- `one-verdict` — the sweep is computed once and passed, not re-derived three times.
- `every-line-earns-its-place` — and its second half: two duplications are left in place, with the reason written down, because removing them would cost more than it saves.
