---
status: active
scope:
  - scripts/security/gha_expression.py
  - scripts/process_gate.py
  - scripts/map_codebase.py
  - scripts/local_knowledge_graph.py
  - scripts/verify_system.py
  - scripts/test/**
  - .agent-rfc/fixtures/knowledge_graph.json
  - .agent-rfc/fixtures/trace_graph.json
  - CHANGELOG.md
  - docs/process-gates.md
---
# Pass4 majors

## Problem

The fourth review of 4.1.0 (`.git/agentsmith/review-4.1.0-pass4.md`, local) found three majors on PR #117, each a new
instance of a class an earlier pass had reported:

- **P4-R1.** `scripts/security/gha_expression.py` returned `True` for `success()`. `success()` is false once an earlier
  step failed or the run was cancelled, which an outsider's pull request can cause, so `!success() || <owner test>`
  is true for an outsider on GitHub and was judged definitely false here: the field counted as guarded. Cause: a value
  that varies treated as known (invariant 1 of `.agent-rfc/designs/invariants-not-instances.md`, "unknown unless
  certain").
- **P4-R4.** `scripts/process_gate.py ci` listed the range with `rev-list --no-merges` and judged each commit against
  its parent, so a declaration weakening made in a merge commit, or in a conflict's resolution, passed CI with exit 0
  while the hook refused it. Cause: CI's verdict depended on the shape of the history, not on what the range changes
  (invariant 2, "judge the whole range").
- **P4-R8.** `scripts/map_codebase.py` added a re-parsed file's imports to the edges it had and skipped files whose
  mtime matched, so no edge was ever removed: 94 of the committed 1,294 edges were stale. `verify_system.py
  --check-kg` compared the committed graph with what the same additive walk made of it, so it passed. Cause: the
  graph was added to, not rebuilt (invariant 3, "rebuild, don't add").

## Approach

Each fix is at the cause the review names, and only as far as no pending owner decision (HANDOFF section 3) is needed.
The full invariants design (`invariants-not-instances.md`, uncommitted, its decisions pending) is not built here.

1. **P4-R1.** `_call` returns a definite value for `always()` with no arguments only; `success()` falls through to
   `UNKNOWN` with `failure()` and `cancelled()`. The comment states the rule: a definite value only where GitHub's
   result is certain. A guard of the form `<owner test> && success()` still counts (`UNKNOWN && false` is false).
   The six coercion corners of P4-R2 are minors and out of this slice.
2. **P4-R4.** `ci_verdict` keeps the per-commit loop and adds a range rule: from each merge base of base and head
   (`git merge-base --all`) to the head, `range_transitions` runs the before-and-after rules (the declaration
   ratchet, the pillar policy, the compliance profile) on the two ends, with the hook's approval route (approvals
   recorded at the head; the trailer cited by any message in the range, merges included). The pillar and profile
   rules move into one function, `policy_transitions`, called by `check_change` and by the range rule, so there is
   one implementation. Approval semantics are unchanged (decision 2 is pending); a weaken-then-restore range still
   fails CI through the per-commit loop, as today (decision 4 is pending); a range with no known base stays head-only
   (decision 8 is pending) and is stated in `docs/process-gates.md`.
3. **P4-R8.** `run_map` drops every `IMPORTS` edge, then parses every file and builds every edge from the tree, on
   every run; `force` is accepted and does nothing. Other edge types (`CAUSED_INCIDENT`) are kept. To keep a full
   build fast, `AgentKnowledgeGraph.batch()` writes the file once at the end instead of once per node (about 28 s to
   about 3 s on this repository). `--check-kg` already compares the committed graph with a fresh `run_map`; that
   build is now from nothing, so a stale edge fails it. The committed graph is rebuilt; the stored file times
   (P4-R11) stay, out of scope.

## Pillars

- P1 applies — the fourth review's P4-R1, P4-R4 and P4-R8 are the requirement; this design (`.agent-rfc/designs/pass4-majors.md`) is the plan, written before the code.
- P2 applies — `agentsmith gate kg impact` scoped the change; `scripts/security/gha_expression.py`, `scripts/process_gate.py`, `scripts/map_codebase.py`, `scripts/local_knowledge_graph.py` and `scripts/verify_system.py` change in place; no new module, no dependency.
- P3 n/a — no new command, route, job, hook or LLM call; the CI gate gains a rule inside an existing command.
- P4 applies — failing first, then passing: `scripts/test/test_gha_expression.py`, `scripts/test/test_agent_workflow_injection.py`, `scripts/test/test_declaration_ratchet.py` (through `process_gate.py ci` on three history shapes), `scripts/test/test_knowledge_graph.py` (an edit sequence compared with a build of a fresh copy, and `check_kg_fresh` on an invented edge); hand mutants after.
- P7 applies — Python only, typed as the files around it; `scripts/process_gate.py` keeps its `Reader` and `Config` types.
- P8 n/a — no telemetry changes.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 applies — `scripts/security/gha_expression.py`: a guard over an outsider's event text counts only when it is false for every value a status function can take.
- P12 n/a — no credentials touched.
- P13 applies — nothing weakens: CI gains a rule (`scripts/process_gate.py`), the evaluator answers fewer conditions definitely, the graph check compares with a build from nothing; the head-only limit with no known base is stated in `docs/process-gates.md`, not hidden.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is rebuilt from nothing (94 stale edges gone, every `KG query:` hash changes once) and `.agent-rfc/fixtures/trace_graph.json` with it; two tests that pinned the incremental skip in `scripts/test/test_knowledge_graph.py` are rewritten to the full rebuild.
- P15 applies — `scripts/process_gate.py`: a range problem is reported as its own `❌ range` line and annotation and fails the run; the "✅" line is not printed when one exists.
- P16 n/a — no fallback or repair step is added.

## Deviations

none

## Dependencies

none

## Levers

- `guards-must-be-able-to-fail` — `success()` can be false on GitHub, so it is unknown here, and a guard joined to it by `||` fails.
- `consistent-auth-gates` — the hook and CI reach the same verdict on a weakening whatever the history's shape.
- `single-source-of-truth` — one `policy_transitions` for a commit and for a range; one build of the graph, from nothing.
- `implemented-not-invoked` — the range rule runs inside `ci_verdict`, which CI calls; tested through `process_gate.py ci`.
- `test-that-cannot-fail` — each new test was run against the unfixed code and failed; hand mutants after.
- `grep-for-siblings` — other status functions, other edge writers, other callers of the transition rules.
