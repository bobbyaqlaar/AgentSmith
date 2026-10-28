---
status: active
scope:
  - scripts/verify_system.py
  - scripts/test/test_kg_drift_gate.py
  - scripts/test/test_design_tree_drift.py
---
# The drift gate compares tracked Guardrail nodes

## Problem

On 2026-10-26 I committed `.agent-rfc/fixtures/knowledge_graph.json` in `beeb838`
having staged it before writing that slice's review record. The graph therefore
went in without `rfc:reviews/design-tree-drift-is-a-pytest-test.md` — the one rfc
file of 180 with no `Guardrail` node. `agentsmith gate kg check` printed:

```
✅ knowledge_graph.json is up to date with the code
```

and all 11 CI checks passed over it. I found it by diffing node ids by hand, and
have had to do that on every slice since, because the gate's answer cannot be
relied on for this class of staleness.

The cause is explicit in `scripts/verify_system.py::_kg_shape`, which filters

```python
if n.get("node_type") == "CodebaseFile" and n.get("id") in tracked
```

so **every** `Guardrail` node is outside the comparison. The reason recorded
there is real:

> `rfc:fixtures/…` Guardrail nodes from GENERATED, gitignored `.agent-rfc` docs
> (`delivery_evidence.md`), each storing an ABSOLUTE source_file path. … a
> Guardrail stays out of this comparison because an untracked design is still
> one.

Comparing those made the gate fail on every CI run, and a gate that always fails
gets deleted. But the remedy was applied to the whole node type rather than to
the untracked ones: of the 184 Guardrails in the graph today, **184 are
git-tracked**, and all 184 are unchecked.

## Approach

**Filter Guardrails the way CodebaseFiles are already filtered — by
trackedness, not by type.** A Guardrail's `source_file` is the repo-relative
path of the rfc document it came from, so `source_file in tracked` includes
every committed design and review and excludes the generated ones. The
absolute-path case the comment describes is excluded by the same test without a
special case, because `_git_tracked_files()` returns repo-relative paths and an
absolute path is never a member.

**Compare `id`, `title` and `pillar`, not `created_at`.**
`local_knowledge_graph.add_guardrail` sets
`created_at=self._g.nodes.get(rule_id, {}).get("created_at", _iso_now())` — it
preserves an existing node's value and stamps `now()` only for a node that is
new. A new node already differs by its presence, so including the timestamp adds
nothing and makes the shape depend on a clock, which is what `last_modified` was
excluded for.

**What this does and does not catch.** It catches a tracked rfc document added,
removed, renamed, or retitled without regenerating — the case that got through.
It still does not catch an edit to a design's *body* that leaves its title
alone, because the mapper stores no digest of the content; that is a separate
question from this gate and is recorded as a declared gap rather than silently
implied.

## Also in this slice — the follow-up `ts-sweep-runs-once` declared

`.agent-rfc/reviews/ts-sweep-runs-once.md` Pass 1 made
`test_ts_runner_invocations.py`'s `invocations` fixture return a tuple, because
a module-scoped fixture hands every test the same object and a `.sort()` in one
would silently change what the others examine. It recorded that
`scripts/test/test_design_tree_drift.py`'s `tracked` and `entries` fixtures have
the same shape and were left as lists, out of that design's scope — so the two
files now differ for a reason that exists only in a review record.

That is a gap this slice closes rather than leaves: the same one-word change in
the sibling file. It is in scope here because splitting a one-word change into
its own design and review would cost about 150 lines of process for it, and
because "the gap recorded in the last review" is what this slice is for. The
alternative was considered and is recorded in the review.

## Pillars

- P1 applies — this note precedes the edit; the gate's own green verdict over the stale fixture is quoted in `## Problem`, as is the filter in `scripts/verify_system.py::_kg_shape` that causes it.
- P2 applies — no new module; one filter clause and one sorted tuple added to `_kg_shape` in `scripts/verify_system.py`, beside the `nodes` and `edges` blocks it already builds, plus `tuple(...)` on two fixtures in `scripts/test/test_design_tree_drift.py`.
- P3 n/a — a CI gate, not a traced runtime path.
- P4 applies — failing test first, in `scripts/test/test_kg_drift_gate.py`: `test_shape_catches_a_removed_guardrail`, `test_shape_catches_a_retitled_guardrail` and `test_guardrails_are_actually_in_the_shape` all fail against the current `_kg_shape` because the node type is excluded, and pass after — verified before the fix was written (3 failed, 11 passed). `test_untracked_guardrails_are_excluded`, `test_absolute_source_paths_are_excluded` and `test_shape_ignores_guardrail_created_at` pin the rule that replaced the type exclusion. Beyond the unit tests, the original defect is reproduced end to end on the real graph: `rfc:reviews/design-tree-drift-is-a-pytest-test.md` deleted from `.agent-rfc/fixtures/knowledge_graph.json`, after which `agentsmith gate kg check` reports stale, while the previous `_kg_shape` loaded from `HEAD` compares the stale and pristine graphs **equal**. For `scripts/test/test_design_tree_drift.py`, its 11 tests and the five `docs/DESIGN.md` mutants are re-run.
- P7 applies — `scripts/verify_system.py` runs standalone before anything is on `sys.path`, so it keeps using `_git_tracked_files()` and the stdlib only; `scripts/test/test_kg_drift_gate.py` loads it through `_shared.load_script`, which is how that file already reaches it.
- P8 n/a — no telemetry; the gate prints.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the new code reads `.agent-rfc/fixtures/knowledge_graph.json`, already parsed by this function with `json.loads` in a try/except, and `source_file` is used only as a dict key against the set `_git_tracked_files()` returns. No path from the graph is opened.
- P12 n/a — no credentials.
- P13 applies — this strengthens a gate, so the way it could go wrong is the opposite direction: a false positive that fails every CI run, which is what the current exclusion was put in to stop. `test_untracked_guardrails_are_excluded` pins that generated and absolute-path Guardrails stay out, and the full `python3 -m runtime.cli gate kg check` is run on this checkout to confirm it still reports green on a graph that IS current.
- P14 applies — this change IS the fixture-drift control. `.agent-rfc/fixtures/knowledge_graph.json` is regenerated and re-pinned, and for the last time verified by diffing node ids by hand; after this the gate is what verifies it, which the new tests are the evidence for.
- P15 applies — `check_kg_fresh` in `scripts/verify_system.py` printed "✅ knowledge_graph.json is up to date with the code", which meant "up to date in the respects `_kg_shape` compares" and did not say what those were. The message now names them — tracked files, guardrails, edges, and the fields compared — so a green verdict cannot be read as a stronger claim than it is, and `scripts/test/test_kg_drift_gate.py::test_guardrails_are_actually_in_the_shape` pins that the guardrails it claims to have compared are in the shape at all.
- P16 applies — `_kg_shape` returns `None` when git cannot answer or the graph is unreadable, and `check_kg_drift` skips the comparison rather than guessing; both are already pinned by `test_shape_is_none_when_git_cannot_answer` and `test_missing_or_unreadable_graph_is_none`, and the new Guardrail block sits inside that same early return.

## Deviations

none

## Dependencies

None added.

## Levers

- `gate-integrity` — can this check fail? For the staleness that actually occurred, it could not.
- `declared-vs-enforced` — 184 declared Guardrail nodes, 0 enforced.
- `ambiguous-signals` — a green verdict that does not say what it compared reads as a stronger claim than it is.
- `test-that-cannot-fail` — the remedy for a false positive was applied to a whole node type, which removed the true positives with it.
