# Review: scratch-dates-and-worktree-tokens

Each fix has a test that fails without it: `test_the_profiles_evidence_is_dated_when_the_tenant_is_built` and
`test_build_dates_the_profile_through_the_one_script` in `scripts/test/test_scratch_tenants.py` (the script did not
exist; the fixture's dates would have been kept), and
`test_a_commit_in_a_linked_worktree_carries_its_sessions_tokens` in `scripts/test/test_agent_tokens.py` (it failed on
the old ledger path with `Agent:` alone, the defect as #115's own commits show it).

## Pass 1 — findings: 1

Against `docs/review-levers.md`.

1. **`--path-format=absolute` needs git 2.31.** On an older git, `rev-parse` fails, the ledger path is `None`, and
   every commit would quietly lose its trailer again. Changed to plain `--git-common-dir`, joined to the checkout when
   git answers relatively (`.git` from the main checkout, an absolute path from a worktree); both forms checked by
   hand, and a mutant that skips the join is killed.

## Pass 2 — findings: 0

- Six hand mutants: signatures not dated, drills not dated, `expires_at` set to now, `build.sh` skipping the script,
  the per-worktree directory, the relative path not joined. All killed.
- `scripts/test/test_scratch_tenants.py` (35) and `scripts/test/test_agent_tokens.py` with
  `scripts/test/test_context_budget.py` (34): pass. ruff clean. `bash -n` on `build.sh` and `date-fixtures.sh`.
- Siblings: no other fixture under `.github/scratch-tenants/` carries a date a check reads (`adopt.sh` names a date in a
  comment; `uv.lock` holds upload times). `attestations.jsonl` stays as written; only the copy in the built tenant is
  dated, and `expires_at` stays null so the catalogue's period decides.
- Not run: `build.sh` end to end. It needs `install-ai-stack.sh` from this commit, which would replace the owner's
  machine install, and the Scratch tenants workflow runs on `main` and on its weekly schedule, not on pull requests. The
  first run after merging is the end-to-end check.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one dating script for the drill and the signatures; the inline loop is gone.
Group 2 · Quality / safety — [x] checked — the trailer path works on any git that has worktrees; bookkeeping still never fails a commit.
Group 3 · Architecture / hygiene — [x] checked — one new script beside `build.sh`; one path in `scripts/agent_tokens.py`.
Group 4 · Process — [x] checked — design first; CHANGELOG and backlog updated.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — a measured session's commit carries its measurement; a fixture's evidence is dated when used, so Scratch tenants cannot fail from the calendar.
Group 7 · Auth & session integrity — [x] n/a — no auth code.

Tests added: two in `scripts/test/test_scratch_tenants.py`; one in `scripts/test/test_agent_tokens.py`.
Mutation-checked: yes, by hand; six mutants, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; ruff; `bash -n`; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `grep-for-siblings`, `fixture-truth`, `environment-parity`, `test-that-cannot-fail`

KG query: kg:dd9eb2e34a75
