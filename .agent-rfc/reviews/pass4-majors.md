# Review: pass4-majors

The fourth review's three majors, each fixed at the cause it names and tested through the entry point that failed:
P4-R1 by evaluating `if:` conditions and through the `SEC-CIAGENT-001` runner
(`scripts/test/test_gha_expression.py`, `scripts/test/test_agent_workflow_injection.py`); P4-R4 through
`process_gate.py ci` on three history shapes, an approved merge, a merge-base case and a config weakening in a merge
(`scripts/test/test_declaration_ratchet.py`); P4-R8 by an edit sequence compared with a build of a fresh copy and by
`check_kg_fresh` on an invented edge (`scripts/test/test_knowledge_graph.py`). Each new test was run against the
unfixed code first and failed (9 for P4-R1, 2 shapes for P4-R4, 5 for P4-R8).

## Pass 1 — findings: 3

Against `docs/review-levers.md`, by ten hand mutants (each applied alone, the named tests run, the file restored) and
a grep for siblings.

1. **The range rule's config half was untested.** Replacing the `policy_transitions` call in `range_transitions` with
   nothing survived: every new CI test weakened the declaration only. Fixed:
   `test_ci_refuses_a_pillar_policy_turned_down_in_a_merge` (`pillars` from `enforce` to `report` in the merge commit).
2. **The rebuild could drop every edge type and no test noticed.** Removing all edges, not only `IMPORTS`, survived:
   `test_a_production_incident_survives_the_walk` checked the node only, and its incident was injected before the
   file node existed, so no edge was ever made. Fixed: the test walks first and asserts the `CAUSED_INCIDENT` edge.
3. **`always(x)` was a constant.** A mutant answering `True` for `always` with arguments survived. GitHub documents
   `always()` with none, so anything else is not certain. Fixed: `test_always_is_a_constant_only_as_github_writes_it`.

Siblings: no other status function or caller treats `success()` as known (`grep` over `scripts/security`); the only
`IMPORTS` writer is `run_map`; the transition rules are called only from `policy_transitions`, `range_transitions` and
`_declaration_change`. The committed graph rebuilt from nothing equals the incremental rebuild edge for edge; against
the old committed graph it lost exactly 94 edges (none to `portal/lib/constantTime.ts` from `portal/proxy.ts` remains)
and gained one, the new test's import of `scripts/verify_system.py`.

## Pass 2 — findings: 0

- The ten mutants again, with pass 1's tests: all killed (range problems not in the exit code; base instead of the
  merge base; `--no-merges` on the range messages; no range starts; no config rule in the range; no edge cleared;
  every edge cleared; the batch never saving; `success()` true; `always(x)` true).
- `process_gate.py ci --base origin/main --head HEAD` on this branch: 15 commits, exit 0 (no false red from the range
  rule).
- The levers in the design re-read against the diff; nothing further.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one `policy_transitions` for a commit and a range; one graph build, from nothing.
Group 2 · Quality / safety — [x] checked — `success()` is unknown; a weakening in a merge fails CI; a stale edge fails `--check-kg`.
Group 3 · Architecture / hygiene — [x] checked — the incremental skip is gone; `force` kept as a no-op for its callers; one batched write.
Group 4 · Process — [x] checked — design first; CHANGELOG bullets name their tests; the head-only limit stated in `docs/process-gates.md`.
Group 5 · Intuitive UI — [x] checked — n/a: no screen; the CI report names the range problem on its own line.
Group 6 · Signal integrity — [x] checked — `KG query:` hashes change once with the rebuilt graph; the edge count in the CHANGELOG corrected.
Group 7 · Auth & session integrity — [x] checked — n/a: no sign-in or session code touched.

Tests added: `test_a_status_function_that_varies_is_unknown`, `test_a_status_function_joined_by_or_never_keeps_an_outsider_out`, `test_always_is_a_constant_only_as_github_writes_it`, three `!success()` spellings in `test_every_spelling_that_lets_an_outsider_through_is_reported`, `test_ci_refuses_a_weakening_however_the_range_is_shaped` (three shapes), `test_ci_allows_a_weakening_in_a_merge_the_owner_approved`, `test_ci_measures_from_where_the_branch_left_not_from_the_base_tip`, `test_ci_refuses_a_pillar_policy_turned_down_in_a_merge`, `test_a_file_that_stops_importing_loses_its_edge`, `test_an_edge_no_file_makes_does_not_survive_a_build`, `test_a_new_file_an_unchanged_file_already_imports_gets_its_edge`, `test_any_edit_sequence_builds_what_a_fresh_tree_builds`, `test_the_check_fails_on_a_committed_edge_no_file_makes`; `test_walker_incremental_skip_and_purge` replaced by `test_walker_rebuilds_every_run_and_purges` (it pinned the removed skip); `test_a_graph_built_by_another_parser_is_parsed_again_whole` no longer asserts the skip.
Mutation-checked: yes, by hand; ten mutants, all killed (three after pass 1's tests).
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` (rebuilt from nothing: 94 stale edges gone; every `KG query:` hash changes once); `.agent-rfc/fixtures/trace_graph.json` (rebuilt with it).
Gates run: the full `pytest` on the staged tree; ruff; `scripts/verify_system.py --check-kg`; `process_gate.py ci` on this branch.

Levers reviewed: `guards-must-be-able-to-fail`, `consistent-auth-gates`, `single-source-of-truth`, `implemented-not-invoked`, `test-that-cannot-fail`, `grep-for-siblings`

KG query: kg:209a44891ed1
