---
status: active
scope:
  - runtime/cli.py
  - scripts/test/test_vendoring_retired.py
---
# A scaffolded tenant's graph knows the records the scaffold wrote

## Problem

`scripts/test/test_vendoring_retired.py::test_kg_check_fails_a_stale_graph_and_passes_once_regenerated`
asserts a freshly scaffolded, committed tenant passes `kg check`. It does not,
once `.agent-rfc/designs/kg-check-sees-tracked-guardrails.md` makes the gate
compare tracked `Guardrail` nodes. Two causes, found by bisecting the scaffold:

**1. A stale machine install (not a code defect; fixed by re-installing.)**
`~/.agent-framework/scripts/map_codebase.py` matched commit `7854bd1`,
predating `6fafbd0` *"map what git tracks, by repository-relative path"*. It
wrote absolute `source_file` paths, which the refreshed install no longer does.
Re-running `install-ai-stack.sh` from this checkout took the scaffold from 17
absolute paths to 0.

**2. The mapper runs before the records it should map.** In `init_tenant`:

| order | step | effect |
|---|---|---|
| 1 | `_provision_governance(...)` | runs `scripts/map_codebase.py` and writes the graph |
| 2 | `seed_tenant_data(...)` | |
| 3 | `write_scaffold_records(...)` | writes `.agent-rfc/001-scaffold.md` and `.agent-rfc/designs/scaffold.md` |

So the graph is built, two tracked rfc documents are created after it, and
nothing rebuilds it. Measured on a fresh scaffold: the init graph holds **17**
guardrails and no `rfc:` node; the same mapper, same flags, same cwd, run again
a moment later holds **19**, including `rfc:001-scaffold.md` and
`rfc:designs/scaffold.md`. A tenant's graph has therefore been stale from birth,
and nothing reported it because `_kg_shape` compared no guardrails at all.

The line numbers mislead here — the mapper call sits at `runtime/cli.py:746`
and the records are written from `runtime/cli.py:436`, but 746 is inside
`_provision_governance`, which `init_tenant` calls first.

## Approach

**Build the graph last.** `_provision_governance` keeps writing an empty
placeholder graph when there is no code to map — a missing file is a gap the
governed check reports forever, which is why it is there — and `init_tenant`
re-runs the mapper after `write_scaffold_records` has written everything a
scaffold writes. The mapper is idempotent and rewrites in place, so the second
run replaces the first result rather than adding to it.

Rejected: moving `write_scaffold_records` before `_provision_governance`.
Provisioning writes `.agenticframework/process-gates.json`, which the records
step reads to decide what is gated; reversing them makes the records depend on a
file that does not exist yet.

Rejected: leaving it and having `tenant init` print "run `kg build` and commit".
A scaffold that asks for a follow-up command to be correct is a scaffold that is
wrong, and the gate would be red on the tenant's first push.

## Pillars

- P1 applies — this note precedes the edit; the ordering is tabulated in `## Problem` from `runtime/cli.py`, and the 17-versus-19 measurement is the evidence it is wrong.
- P2 applies — no new module. The mapper invocation moves from `_provision_governance` to the end of `init_tenant` in `runtime/cli.py`; the empty-graph placeholder stays where it is, because its reason (a missing file is a permanent gap) is independent of when the real graph is built.
- P3 n/a — no traced runtime path; this is scaffold-time tooling.
- P4 applies — `scripts/test/test_vendoring_retired.py` gains `test_the_scaffolded_graph_knows_the_scaffold_records`, asserting the init-time graph holds a `Guardrail` for every `.agent-rfc/*.md` and `.agent-rfc/designs/*.md` the scaffold wrote. It fails before this change (`rfc: []`) and passes after. `test_kg_check_fails_a_stale_graph_and_passes_once_regenerated` is the end-to-end control and must return to green.
- P7 applies — the mapper is invoked as a subprocess of `sys.executable` with `cwd=root` and `--quiet`, exactly as `_provision_governance` does it today, so the installed copy under `_framework_dir()` stays the one that runs and nothing about path resolution changes.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the mapper reads the tenant's own freshly written files; no input comes from outside the directory `init_tenant` was pointed at, and the records it now sees are ones the scaffold itself wrote.
- P12 n/a — no credentials.
- P13 applies — this makes a required check pass that currently fails, so the risk is making it pass for the wrong reason. The gate itself is untouched: `scripts/verify_system.py::_kg_shape` is not in this slice's scope, and `test_the_scaffolded_graph_knows_the_scaffold_records` asserts the graph's **contents** rather than the gate's verdict, so a gate that stopped comparing guardrails would not make it pass.
- P14 applies — this is fixture drift at its source: the scaffold's committed `.agent-rfc/fixtures/knowledge_graph.json`. AgentSmith's own graph is regenerated and re-pinned as usual, verified by node-id diff.
- P15 applies — "the graph exists" was read as "the graph is current". `_provision_governance`'s comment says an empty graph is a fact and a missing file is a gap, which is true and was taken to settle the question of when the real one is built. The two are now separate: the placeholder answers existence, the final run answers currency.
- P16 applies — if the mapper fails on the second run, `init_tenant` keeps the behaviour it has for the first: it prints `! map_codebase.py did not complete: …` to stderr and the scaffold still completes, leaving a graph the tenant's own `kg build` fixes. The scaffold is not aborted over a graph.

## Deviations

none

## Dependencies

None added.

## Levers

- `implemented-not-invoked` — the mapper was invoked, just before the thing it was supposed to map.
- `ambiguous-signals` — "a graph exists" and "the graph is current" were one question.
- `fixture-truth` — a committed fixture that never matched, in every tenant the framework has ever scaffolded.
