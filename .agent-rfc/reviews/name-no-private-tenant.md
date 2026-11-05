# Review: name-no-private-tenant

## Pass 1 — findings: 2

1. `test-the-contract` — **The first guard test did not call the function it was guarding;** it rebuilt the match inline, so a broken `private_tokens` would have passed it. **Fix:** `private_tokens` takes its digest set as a parameter, and the test drives it with a stand-in token, including a longer token and a different case that must not match.
2. `every-line-earns-its-place` — **Backticked names became backticked "Tenant B"** in eight CHANGELOG lines, which reads as a code identifier. **Fix:** the backticks go with the name.

## Pass 2 — findings: 0

- **Each name is caught:** appending each of the three names to a tracked file fails `test_no_tracked_file_names_a_private_tenant_or_project`, and removing it passes.
- **Every replacement reads:** no compound such as a path or flag was split, and no "a Tenant B" or "the Tenant B" was produced except where the original read the same way.
- **Commands still run as written:** `gcloud` calls take `"$GCP_PROJECT_ID"`, which the manual already tells the reader to set, and the Unix-socket URL shows `PROJECT_ID` as a placeholder.
- **Code changes are comments and docstrings only,** apart from one test lever's name (`tenant-only-lever`), which the test defines and reads itself. The workflow templates a tenant receives change in comments only.
- **History keeps the names.** That is recorded in the design as the owner's decision to make, and not attempted.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one replacement script; one guard test.
Group 2 · Quality / safety — [x] checked — the guard holds names as digests, so it publishes nothing.
Group 3 · Architecture / hygiene — [x] checked — no dependency; no behaviour change.
Group 4 · Process — [x] checked — design first; CHANGELOG; backlog row 11 records the decision.
Group 5 · Intuitive UI — [x] n/a — no interface.
Group 6 · Signal integrity — [x] checked — the guard fails on each name and passes on the tree.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: `scripts/test/test_private_names.py`.
Mutation-checked: n/a — no curated property changes; the guard was proven by reintroducing each name by hand.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `scripts/test` and `agentsmith/test` in the 3.11 CI environment: 2490 passed, 10 skipped, 2 failed. The two failures (`test_the_launcher_moves_past_an_interpreter_that_cannot_run_the_gate`, `test_session_start_says_when_gate_spans_are_not_emitted`) fail identically on a tree without this change and pass in CI, so they come from this machine. Ruff, mypy, the graph check and the process gate are run on the final tree before pushing.

Levers reviewed: `every-line-earns-its-place`, `test-the-contract`.

KG query: kg:d94bca7baf3f
