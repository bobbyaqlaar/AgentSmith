---
status: active
scope:
  - scripts/test/**
  - runtime/test/**
---
# Three tests that would have passed while checking nothing

## Problem

A full review across `docs/review-levers.md`, asked for with emphasis on
`every-line-earns-its-place`. The LOC lever found nothing to cut — the
2026-09-24 sweep had already taken it:

- **No dead code.** An AST scan of every function in `runtime/` and `scripts/`
  against every mention anywhere in the repository returns **zero** never-referenced
  functions.
- **No stray wrappers.** 17 pure pass-throughs exist and all are load-bearing:
  `scripts/security/runners/delegating.py` is the SEC-control dispatch table, and
  `run(control, ctx)` is an interface the harness calls by name.
- **No bloat in the recent work.** Comment-to-code across the seven files added in
  the last four slices is **0.47** against a repository norm of **0.44**.

`test-that-cannot-fail` found three real ones. Each sweeps a list built from the
filesystem and asserts **only inside the loop**, so an empty list is a pass:

1. `runtime/test/test_provider_dispatch_cloud.py` — walks the cloud adapters and
   asserts each delegates to a shared parser. It visits four today. Rename
   `parse_response`, or move those classes, and it visits none and passes — at the
   moment an adapter stopped being checked. Its own docstring counts on the four:
   "applied once and missed four times".
2. `scripts/test/test_no_hardcoded_model_ids.py` — globs `workflow-templates/*.yml`
   for a pinned judge model. Rename the directory and it certifies nothing. The
   neighbouring test proves the *detector* works on a synthetic probe, which is a
   different guarantee from the glob having matched.
3. `scripts/test/test_scratch_tenants.py` — walks the scratch apps asserting none
   carries a generated path. `test_every_app_is_the_scenario_it_claims` would
   catch an empty `APPS`, but a test that holds only because a sibling holds stops
   holding as soon as either is moved or skipped.

## Approach

One assertion each, outside the loop, on the size of what was swept — and a
comment saying why it is there, because the next reader's instinct is to delete
it as redundant.

The count is pinned to something that means something, not to a magic number:
four adapters because the docstring's history is four; more than five templates
because the directory holds six families; exactly `len(SCENARIOS)` apps because
that registry is what the scratch tenants are.

`runtime/test/**` joins the scope: the adapter sweep lives there, and the defect
is one class, not one tree.

## Pillars

- P1 applies — this design before the edit; scope `scripts/test/**` and `runtime/test/**`, reviewed in `.agent-rfc/reviews/vacuous-sweep-guards.md`.
- P2 applies — three assertions added to three existing tests in `runtime/test/test_provider_dispatch_cloud.py`, `scripts/test/test_no_hardcoded_model_ids.py` and `scripts/test/test_scratch_tenants.py`; no helper, no new file, no dependency. The detector that found them is an AST sweep run in this review, not code being kept.
- P3 n/a — test assertions; no execution path that should emit a span.
- P4 applies — the guard in `test_every_cloud_adapter_delegates_to_a_shared_parser` was proven by renaming `parse_response` in `runtime/provider_dispatch.py` and watching the test fail, then restoring; before the guard that same rename passed. The other two are the same shape against a directory rename, which is not safely reversible in-tree and is argued from the first.
- P7 applies — Python, `ast` and `pathlib` as the surrounding tests already use; no new idiom.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 n/a — no untrusted content; these read this repository's own tracked files.
- P12 n/a — no credential read or written.
- P13 applies — nothing gets weaker: three checks that could pass without looking now cannot. `scripts/test/test_no_hardcoded_model_ids.py` keeps its own `test_the_guard_actually_catches_a_hardcoded_id`, so the detector and the sweep are now both proven, which they were not before.
- P14 applies — no fixture or golden changes; `.agent-rfc/fixtures/knowledge_graph.json` re-pinned with `map_codebase.run_map(force=True)` and `scripts/test/test_kg_drift_gate.py` re-run.
- P15 applies — the defect is the signal itself: a green tick meaning "found no offenders" and one meaning "looked at nothing" were the same tick. Each assertion's message says which it is — `only found {checked}`, `only {len(templates)} templates`, `expected {len(SCENARIOS)} apps`.
- P16 applies — when a sweep finds less than it should, the test now fails with the count and the names it did find: `test_every_cloud_adapter_delegates_to_a_shared_parser` prints which adapters it reached, `test_ci_templates_do_not_pin_a_judge_model` how many templates it globbed, and `test_apps_carry_nothing_provisioning_generates` which apps it walked. The reader learns the sweep broke rather than that `runtime/provider_dispatch.py` regressed, which is the recovery the old form denied them.

## Deviations

none

## Dependencies

none

## Levers

- `test-that-cannot-fail` — the lever this slice is: a loop over an empty collection, three times.
- `every-line-earns-its-place` — swept first and found nothing to cut; the three lines added here are the review's only output, and each buys a check that was not running.
- `ambiguous-signals` — "no offenders" and "no files" were one green tick.
- `guards-must-be-able-to-fail` — the adapter guard was proven to fail by breaking the thing it guards.
- `check-that-fires-on-everything` — a sweep that fires on nothing is the degenerate case of one that fires on everything.
