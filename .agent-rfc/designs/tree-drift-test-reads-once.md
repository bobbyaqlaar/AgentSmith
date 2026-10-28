---
status: done
scope:
  - scripts/test/test_design_tree_drift.py
---
# The drift test reads the repository once, and states its filter once

## Problem

Asked whether the review covered redundancy, I measured
`scripts/test/test_design_tree_drift.py` (shipped in `beeb838`) and found two
things the review passes did not:

- **One rule, two copies.** "The second-level names tracked under this
  directory" is written at line 230 as a set comprehension minus
  `IGNORE_SECOND`, and again at line 280 inlined into an `any(...)` — where it
  silently drops `IGNORE_SECOND`. Today that subtraction cannot change the
  wildcard verdict, because no `IGNORE_SECOND` member (`__init__.py`,
  `.gitignore`) contains `*` or could match a pattern that a real file does not
  also match. So it is not a live defect — it is the same rule stated twice,
  already differing, which is how one becomes a defect.
- **The repository read seven times.** `_design_entries()` has 7 call sites and
  `_tracked_paths()` has 4, so a run re-parses `docs/DESIGN.md` seven times and
  spawns `git ls-files` four times. `scripts/test/test_gate_steps.py` uses
  `@pytest.fixture` for precisely this, so the idiom was available and I did not
  look for it.

The review's Group 1 line — *"checked — the logic exists once, in the test"* —
answered whether the PORTED logic was duplicated against the YAML it came from.
It did not audit the new file against itself, and said so in a way that reads as
if it had.

## Approach

**One module-scoped fixture per input, and one helper for the filter.**

- `tracked` and `entries` become `@pytest.fixture(scope="module")`, matching
  `test_gate_steps.py`'s use of fixtures for shared inputs. Seven reads become
  one, four subprocesses become one, and the eleven call sites become eleven
  parameters — which also makes each test's inputs visible in its signature.
- `_tracked_second(directory, tracked)` returns the set, `IGNORE_SECOND`
  subtracted, and both the missing-side and wildcard-side tests call it. The
  wildcard test gains the subtraction it was missing.

**What is deliberately NOT consolidated.** The three `for directory in
DEEP_DIRS` loops stay three loops. They assert different things and produce
different messages, and `every-line-earns-its-place` says a removed line must
not move its cost into the reader: one parameterised loop with a mode flag would
be shorter and worse. Same for the five per-direction tests — splitting them was
the point of the slice they came from.

## Pillars

- P1 applies — this note precedes the edit; both findings are quoted with their line numbers in `## Problem`, and the measurement that produced them is in `.agent-rfc/reviews/tree-drift-test-reads-once.md`.
- P2 applies — no new module; two fixtures and one helper inside `scripts/test/test_design_tree_drift.py`, the shape `scripts/test/test_gate_steps.py` already uses.
- P3 n/a — a pytest guard, no traced runtime path.
- P4 applies — the ten tests in `scripts/test/test_design_tree_drift.py` are the control: the four `docs/DESIGN.md` mutants from the previous slice are re-run and must still fail exactly one named test each, and `_tracked_second` is proved to subtract `IGNORE_SECOND` by a direct assertion rather than inferred from the sweeps.
- P7 applies — `@pytest.fixture(scope="module")` memoises per module, which is correct here because both inputs are read-only and no test mutates them; `pytest` is already this job's test runner via `requirements.lock` (`pytest==8.4.2`).
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — unchanged: the test reads `docs/DESIGN.md` and `git ls-files` from this checkout and parses them with `re` and `fnmatch`; moving the reads into fixtures does not add a source.
- P12 n/a — no credentials.
- P13 applies — this touches a required check, so the risk is a fixture that makes a sweep examine less than before. `DEEP_DIRS`, `IGNORE_TOP`, `IGNORE_SECOND` and every assertion are unchanged; `test_the_tree_parse_found_the_repository` still fails if the parse returns nothing, and the four tree mutants are re-run to prove the verdicts did not move.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated and re-pinned, with `agentsmith gate kg check` as the control. Noted: that check reported green over a fixture missing a `Guardrail` node earlier today, so it is a weak control and the re-pin is verified by diffing the node ids as well.
- P15 applies — `IGNORE_SECOND` present in one copy of the filter and absent in the other is exactly an ambiguous rule: a reader cannot tell which copy is intended. One helper, one answer.
- P16 applies — if a fixture were to return something empty, `test_the_tree_parse_found_the_repository` (floor of 20 top-level entries, every `DEEP_DIR` non-empty) fails rather than letting the five sweeps pass over nothing.

## Deviations

none

## Dependencies

None added. `pytest` is already imported by this file.

## Levers

- `no-copy-paste` — one rule, one place, including the part the second copy forgot.
- `search-before-writing` — the fixture idiom was next door in `test_gate_steps.py`.
- `every-line-earns-its-place` — and its second half: the three DEEP_DIRS loops and five per-direction tests stay, because collapsing them moves cost into the reader.
