# Review: scratch-dates-and-worktree-tokens

Each fix has a test that fails without it: `test_the_profiles_evidence_is_dated_when_the_tenant_is_built` and
`test_build_dates_the_profile_through_the_one_script` in `scripts/test/test_scratch_tenants.py` (the script did not
exist; the fixture's dates would have been kept). (Before the rebuild a third test,
`test_a_commit_in_a_linked_worktree_carries_its_sessions_tokens`, covered P2-R4; that half was dropped for `main`'s
#119, see Pass 3.)

## Pass 1 — findings: 1

Against `docs/review-levers.md`.

1. (On the P2-R4 code, dropped in the rebuild.) **`--path-format=absolute` needs git 2.31.** On an older git, `rev-parse` fails, the ledger path is `None`, and
   every commit would quietly lose its trailer again. Changed to plain `--git-common-dir`, joined to the checkout when
   git answers relatively (`.git` from the main checkout, an absolute path from a worktree); both forms checked by
   hand, and a mutant that skips the join is killed.

## Pass 2 — findings: 0

- Six hand mutants: signatures not dated, drills not dated, `expires_at` set to now, `build.sh` skipping the script,
  and, on the P2-R4 code dropped in the rebuild, the per-worktree directory and the relative path not joined. All
  killed.
- `scripts/test/test_scratch_tenants.py` (35) and `scripts/test/test_agent_tokens.py` with
  `scripts/test/test_context_budget.py` (34): pass. ruff clean. `bash -n` on `build.sh` and `date-fixtures.sh`.
- Siblings: no other fixture under `.github/scratch-tenants/` carries a date a check reads (`adopt.sh` names a date in a
  comment; `uv.lock` holds upload times). `attestations.jsonl` stays as written; only the copy in the built tenant is
  dated, and `expires_at` stays null so the catalogue's period decides.
- Not run: `build.sh` end to end. It needs `install-ai-stack.sh` from this commit, which would replace the owner's
  machine install, and the Scratch tenants workflow runs on `main` and on its weekly schedule, not on pull requests. The
  first run after merging is the end-to-end check.

## Pass 3 — findings: 0

Rebuilt on `main` `cdf04e1` (2026-11-23, PR #117 rebuilt with the owner's approval). `main`'s #119 fixed P2-R4 its own way, so this commit's `scripts/agent_tokens.py` and `scripts/test/test_agent_tokens.py` hunks conflicted and were dropped for `main`'s; its CHANGELOG bullet for P2-R4 was dropped too (`main`'s bullet says it). `test_a_commit_in_a_linked_worktree_carries_its_sessions_tokens` is not added: `main`'s `test_a_real_commit_from_a_linked_worktree_carries_the_tokens` and `test_a_linked_worktree_reads_the_sessions_ledger` hold the same behaviour through the real hooks. The P2-R24 half is unchanged. The scope was recomputed on the rebuilt graph, below. (Second rebuild, 2026-11-26,
after #117's independent review, 117-R6: this commit's message, design and the lines below now describe P2-R24 only.)

## Sign-off

Group 1 · DRY & shared code — [x] checked — one dating script for the drill and the signatures; the inline loop is gone.
Group 2 · Quality / safety — [x] checked — the dating script fails loudly; the production verdict is still asserted.
Group 3 · Architecture / hygiene — [x] checked — one new script beside `build.sh`.
Group 4 · Process — [x] checked — design first; CHANGELOG and backlog updated.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — a fixture's evidence is dated when used, so Scratch tenants cannot fail from the calendar.
Group 7 · Auth & session integrity — [x] n/a — no auth code.

Tests added: two in `scripts/test/test_scratch_tenants.py` (the worktree test is `main`'s, see Pass 3).
Mutation-checked: yes, by hand; six mutants, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; ruff; `bash -n`; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `grep-for-siblings`, `fixture-truth`, `test-that-cannot-fail`

KG query: kg:01a1215a344a
