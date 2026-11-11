# Review — `sync` refreshes the rule files an older `tenant init` left unrecorded

Design: `.agent-rfc/designs/sync-refreshes-rule-files.md`. Reviewed against `docs/review-levers.md`.

## Pass 1 — findings: 1

1. **Process: the code was edited before the design's pillars were answered.** The skeleton was written first, but `agentsmith/sync.py` was changed (through Bash, which the edit gate does not see) before the pillars were filled. Nothing was committed in between; the design was completed before the tests and the commit. Recorded so the order is visible; no code change follows from it.

Checked, and holding:
- The new condition fires only for a file the manifest never recorded (`theirs`) and the rules port places `whole` while it exists, which is exactly the set `rules check` already holds to the render. A block-placed file and a missing file are unaffected.
- A recorded file the tenant edited is still `edited`: left alone, with its note (new test).
- The refreshed file goes through `written`, so `write_scaffold_records` records its hash and the printed commit carries it (new test asserts the manifest entry).
- If the render fails, `RulesUnavailable` notes it and `plan.generated` stays empty: nothing is refreshed.

## Pass 2 — findings: 0

- `scripts/test/test_framework_sync.py`: the unrecorded-file test fails on the old code and passes on the new; the edited-file test passes on both.
- `scripts/check_tenant_upgrade.sh v4.0.1 <this tree>`: by init and by adopt, rules current after the sync.
- Four hand mutants (drop the `theirs` condition, never fire, invert the existence check, keep `theirs`), all killed by the sync tests.

## Sign-off

Group 1 · DRY & shared code — [x] checked — the rules port's own placement is the signal; no second notion of "generated".
Group 2 · Quality / safety — [x] checked — a tenant's recorded edit still wins; a failed render touches nothing.
Group 3 · Architecture / hygiene — [x] checked — one field on `Plan`, one condition in `plan_sync`.
Group 4 · Process — [x] checked — design written, though answered after the first edit (pass 1); CHANGELOG updated.
Group 5 · Intuitive UI — [x] n/a — no screen; sync's output names each refreshed file as before.
Group 6 · Signal integrity — [x] checked — a file not refreshed still reads as drifted in `rules check`.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: `scripts/test/test_framework_sync.py` (two tests).
Mutation-checked: yes, by hand; four mutants, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the sync tests; the tenant-upgrade check; ruff; mypy; the process gate against the commit.

Levers reviewed: `implemented-not-invoked`, `test-that-cannot-fail`.

KG query: kg:5fa67d1fbe5f
