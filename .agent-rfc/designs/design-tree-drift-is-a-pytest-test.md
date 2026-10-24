---
status: active
scope:
  - scripts/test/test_design_tree_drift.py
  - .github/workflows/self-test.yml
---
# The repo-tree drift check belongs in pytest, not in a workflow step

## Problem

`PR #66` went red on `Python scripts/runtime/examples`, step *"docs/DESIGN.md
repo-tree drift check (top level + key sub-trees)"*:

```
missing from docs/DESIGN.md tree (second level): ['docs/agentic-42001-coverage.md']
```

The full local suite had just passed — 2423 tests — because the check is 60
lines of Python inlined in `.github/workflows/self-test.yml` (lines 150–227) and
nothing runs it outside GitHub Actions. "pytest is green" therefore does not
imply "CI is green", and the gap is invisible: there is no local command whose
absence a developer would notice. To run it this session I had to extract the
step's script out of the YAML with a regex into a scratch file — which is itself
the evidence that the logic is in the wrong place.

It is also unreachable by every tool the repository points at its own code:
`pytest` cannot collect it, `ruff` and `mypy` do not lint it (`dict[str, set]`
inside a heredoc is checked by nothing), and `scripts/mutation_check.py` cannot
mutate it. A 60-line checker with four distinct failure directions has no test
of its own precisely because it is not reachable as code.

## Approach

**Move the logic to `scripts/test/test_design_tree_drift.py` and leave the
workflow step as a one-line invocation of it.** The step keeps its name, its
`# agentsmith:gate` tag and its place in the job, so `agentsmith gates list`,
the generated table in `docs/validation-checklist.md` and the required check
`Python scripts/runtime/examples` are all unchanged — what changes is that the
step now says `pytest scripts/test/test_design_tree_drift.py -q` instead of
carrying the program. `pytest` is already installed in that job by
`pip install --require-hashes -r requirements.lock` (`pytest==8.4.2`), two steps
earlier, so the step needs no new install.

**One assertion per drift direction, instead of one exit code.** The inline
script printed all four lists and exited 1, so a drift in any direction read as
one failure with three empty lines of noise around it. Each direction becomes
its own test — top-level missing, top-level ghost, second-level missing,
second-level ghost — because they have different causes and different fixes (a
file added without a tree entry; a tree entry for something deleted).

**A fifth direction, added in review: a wildcard entry must still match
something.** The ghost direction skips any entry containing `*`, since a
pattern has no single path to test for. That leaves the one kind of tree line
that can describe nothing at all and never be reported — delete every
`fixtures/*_judge_criteria_base.json` and the entry sits there claiming they
exist. `test_every_wildcard_tree_entry_still_matches_something` matches forward
instead. All four wildcards in the tree today match (3, 2, 3 and 4 tracked
files), so this closes a hole rather than reporting one.

**Parsing stays byte-identical.** The tree regex, the ` / ` splitting, the
`rstrip("/").split("/")[0]` first-component rule, `DEEP_DIRS`, `IGNORE_SECOND`,
`ignore`, the `fnmatch` wildcard match and the `"*" in name` ghost skip are
carried over unchanged, and `git ls-files` stays `git ls-files` — the index, so
a staged file is checked before it is committed, and an untracked scratch file
is not. `--others --exclude-standard` is deliberately NOT adopted here, unlike
`scripts/test/test_ts_runner_invocations.py::_candidate_files`: that sweep must
see a call site at push time, whereas this one must return the same verdict as
the CI step, and `--others` would fail the suite over any untracked file in the
working tree.

**And the checker gets the test it never had**, against a fixture tree rather
than against the repository, so each of the four directions is proved to fail
and the parser is pinned form by form (nesting depth, trailing comment, ` / `
pairs, a wildcard entry, a path-valued entry).

## Pillars

- P1 applies — this note precedes the edit; the failing CI line and the step's location (`.github/workflows/self-test.yml` lines 150–227) are quoted in `## Problem`.
- P2 applies — the logic moves from YAML into `scripts/test/`, where the repository already keeps this kind of sweep (`scripts/test/test_ts_runner_invocations.py`, `scripts/test/test_design_and_validation_docs.py`). No new module or package.
- P3 n/a — a pytest guard over two tracked files; no traced runtime path.
- P4 applies — the new file is the test. Beyond it, the port is verified by mutating `docs/DESIGN.md` four ways (delete a second-level entry, delete a top-level entry, add an entry for a path that does not exist, add a second-level entry for a missing file) and confirming the matching test fails and the other three do not; plus a parity run of the old inline script and the new test on the same tree, which must agree.
- P7 applies — `pytest` is already present in that job via `requirements.lock` (`pytest==8.4.2`), so the step needs no install; `scripts/gate_steps.py` reads the `# agentsmith:gate` tag and the step's `run:` value, and `scripts/generate-ide-config.py --gates` regenerates the table in `docs/validation-checklist.md` that `scripts/test/test_gate_steps.py::test_the_checklist_holds_the_generated_table` pins.
- P8 n/a — no telemetry; `scripts/test/**` emits no spans.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the test reads `docs/DESIGN.md` and the output of `git ls-files`, both from this checkout, and parses them with `re` and `fnmatch`. Nothing is executed and no path from either source is opened except through `pathlib.Path(...).exists()`.
- P12 n/a — no credentials.
- P13 applies — this moves a required check, so the ways it could be weakened are named and checked: the step keeps its `# agentsmith:gate` tag (so `agentsmith gates list` still reports it and `test_the_frameworks_own_workflow_tags_its_gates` still counts it), the generated table in `docs/validation-checklist.md` is regenerated in the same commit, and `scripts/test/test_gate_steps.py` is run to confirm the committed table matches the tags. The check also now runs a second time, in `pytest scripts/test/` inside the `Python runtime behaviour tests (Postgres-backed)` job, so it gates merges from two required checks rather than one.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated and re-pinned because tracked files change; `agentsmith gate kg check` is the control. The new test's own fixture tree is a literal in the test file, not a file under `fixtures/`, so it cannot drift from a committed baseline.
- P15 applies — the inline script's single exit code conflated four different drifts; `scripts/test/test_design_tree_drift.py` splits them into one test per direction (five, with the wildcard check) so the failure names which direction drifted and therefore which fix applies. Verified: each of the four tree mutants fails exactly one test, named in the review record.
- P16 applies — if `docs/DESIGN.md` loses its `### Repository Structure` block entirely, the parse returns nothing; `test_the_tree_parse_found_the_repository` fails on that rather than letting the four sweeps pass over empty sets, which is the way this check could silently stop checking.

## Deviations

none

## Dependencies

None added. `fnmatch`, `re`, `subprocess` and `pathlib` are stdlib and already used by the inline script.

## Levers

- `implemented-not-invoked` — a checker only a CI runner can invoke is a checker the people changing the thing it checks cannot run.
- `environment-parity` — the same verdict locally and in CI, from the same code, rather than from a copy that lives in YAML.
- `test-that-cannot-fail` — the parse is pinned so the four sweeps cannot pass over an empty tree.
- `ambiguous-signals` — four drift directions, four tests, four messages.
