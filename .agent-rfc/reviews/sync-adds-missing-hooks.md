# Review — sync-adds-missing-hooks

Design: `.agent-rfc/designs/sync-adds-missing-hooks.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 2

1. **The scope editor read scope lines differently from the gate.** `extend_design_scope`
   recognised a list item only as exactly `  - path`; the gate's `front_matter` reads any
   indentation (`^\s+-\s+`). On a hand-written design indented otherwise — KYC and OTS armed
   by hand — the editor would see an empty list, append every path again, and leave a
   scope with duplicates and mixed indentation. It now reads items with the gate's own
   pattern and appends at the indentation the list already uses.

2. **The gate's note counted a file it no longer checks.** `vouched_note` says "N gated
   file(s) match scaffold.json"; with the manifest skipped, N still included it — one more
   match claimed than was made (`aggregates-name-their-scope`). It now counts the files
   that were checked.

## Pass 2 — findings: 1

1. **The scope edit was unasserted — a mutation survived.** With
   `extend_design_scope` replaced by `after = before`, every test still passed. The
   stand-in tenant's arming design was rendered by today's `adopt`, so it already listed
   the three hooks and the manifest: there was nothing for a sync to add, and the test
   proved nothing about the case it was named for. KYC's real arming design was older
   and narrower. The fixture now ages it — the hook and manifest lines removed and
   committed, asserting it really narrowed — so the sync commit is refused unless the
   scope edit runs.

Pass 1's two fixes, verified: `extend_design_scope` reads items with the gate's pattern
and appends at the list's own indentation (a 4-space, 3-space-after-dash list is
extended without duplicates); `vouched_note` counts the files it checked, asserted in
`test_scaffold_review.py` and given its own mutation in the `tenant_adopt` suite.

## Pass 3 — findings: 1

1. **`docs/process-gates.md` said a sync adds the gate hooks "and nothing else".** It does
   not: it has always written `providers.json` where it is missing, and
   `write_scaffold_records` writes the manifest, the arming design and an RFC template where
   none exists. The sentence now names the hooks as the one new kind of addition and lists
   the records a sync creates only where they are missing (`docs-match-behaviour`).

Re-read with it: `extend_design_scope` (no front matter, no `scope:` key, an empty list
followed by another key, a hand-indented list — each returns the text unchanged or appends
once, at the list's indentation); the manifest skip and the note's count; the sync branch
of `write_scaffold_records`, which only `sync` reaches (`generated_by` is passed by no other
caller); and nothing in the change adds a path from a tenant into the framework — the scope
lines name the tenant's own copies of the gate hooks, which the gate contract's resolution
runs through.

## Pass 4 — findings: 0

Re-read the docs fix against `runtime/sync.py` and `write_scaffold_records`, and the final
test file. Every claim in `docs/process-gates.md`, the manual's `sync` row and the CHANGELOG
entry matches the code; the CHANGELOG no longer states vendoring as the norm — it separates a
tenant whose CI checks the provider out from one running a vendored copy. The fixture asserts
it narrowed the design, so it cannot silently stop exercising the scope edit.

## Sign-off

Group 1 · DRY & shared code — [x] checked — `install_gate_hooks` and `GATE_HOOKS` remain the one writer and list of hooks; the scope edit sits beside the renderer of that block and reads items with the gate's own pattern; the escape's note and check share `SCAFFOLD_MANIFEST`.
Group 2 · Quality / safety — [x] checked — five sync tests and one gate test; six new mutations across `framework_sync` and `tenant_adopt`, all caught after one survived and was fixed; full suite 2067 passed.
Group 3 · Architecture / hygiene — [x] checked — `runtime/` does not import the gate; the sync branch of `write_scaffold_records` is reachable only by `sync`; nothing adds a path from a tenant into framework internals.
Group 4 · Process — [x] checked — owner decision recorded in the backlog row before the design; design amended twice before the code it named (P2 wording, the test file added to scope); row archived with this change.
Group 5 · Intuitive UI — [x] checked — the plan says `add` beside `stale`, and says what the sweep will now do on commit and push.
Group 6 · Signal integrity — [x] checked — the vouched note counts only what it checked; a refused push after a sync reads as the sweep.
Group 7 · Auth & session integrity — [x] checked — no credentials; the one gate relaxation (the manifest not vouching for itself) is argued in P13 and pinned so nothing else escapes.

Tests added: `scripts/test/test_framework_sync.py` — `test_a_tenant_armed_before_the_sweep_is_planned_the_hooks_it_lacks`, `test_the_hooks_it_adds_go_in_the_manifest_and_a_commit_the_tenants_own_gate_accepts`, `test_a_tenant_with_no_arming_design_gets_one_that_covers_the_whole_commit`, `test_the_scope_edit_appends_only_what_is_missing_and_keeps_the_prose`; `scripts/test/test_scaffold_review.py` — `test_the_manifest_is_not_asked_to_vouch_for_itself_and_nothing_else_escapes`.
Mutation-checked: the six new mutations through `mutation_check.run_suite` (5 in `framework_sync`, 1 in `tenant_adopt`), all caught; the full `framework_sync` run exceeded the 30-minute background limit locally and was stopped with every file verified restored — CI runs it.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` rebuilt with `scripts/map_codebase.py`.
Gates run: `pytest` (2067 passed, 10 skipped); `ruff check .` (0.15.20); `mypy` (1.14.1); `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `implemented-not-invoked`, `declared-vs-enforced`, `gate-integrity`, `test-the-contract`, `test-that-cannot-fail`, `out-of-order-and-repeated`, `failure-is-not-a-result`, `ambiguous-signals`, `aggregates-name-their-scope`, `docs-match-behaviour`.

KG query: kg:76384dfdfd1f
