# Review: declaration-ratchet-and-atomic-test

P2-R12 follows the owner's decision of 2026-11-13: agents may edit the declaration, a weakening needs the owner's
approval, and the action is logged in the audit log. Each part has tests that fail without it, in
`scripts/test/test_declaration_ratchet.py`: fifteen weakenings named, seven strengthenings and placeholder filling not
named, the approval rule, the shell no longer refusing the file, the ratchet in every mode gated or not, and one commit
sequence through the real hooks (declare, refused weakening, approved weakening) that reads the three audit-log entries
back. P2-R16: `test_a_purge_whose_record_fails_in_the_database_deletes_nothing` and
`test_a_stop_or_resume_whose_record_fails_in_the_database_changes_nothing` run against Postgres, in a schema of their
own with a trigger that refuses the record.

## Pass 1 — findings: 2

Against `docs/review-levers.md`, by hand mutants (ten) and with the database tests run.

1. **The ratchet was untested where the declaration is not gated and artifacts are enforced.** That branch returns
   early, and dropping the declaration's errors there survived: the end-to-end repository uses `artifacts: report`. A
   direct `check_change` test now covers both modes, gated and not.
2. **The two database tests interfered.** Both used one schema name; the compliance module caches "tables created" by
   DSN, so the second test's fresh schema never got its tables. Each test now has a schema of its own. Found by running
   the file whole, not the tests one at a time.

## Pass 2 — findings: 0

- The mutants again: the record written after the change commits (the second-pass review's surviving R13 mutant) is
  now killed by the database test; an approval not required; a cited but unrecorded approval accepted; placeholders
  counted as real values; languages ignored; retention read the wrong way; the ratchet only for gated commits; no log
  entry; a refused weakening logged as resolved; the shell refusing the file again. All killed.
- `agentsmith/test` with the database, `scripts/test/test_declaration_ratchet.py`, `scripts/test/test_process_gate.py`,
  `scripts/test/test_compliance_port.py`, `scripts/test/test_gate_shell.py`: 1,212 passed, 10 skipped. The whole of
  `scripts/test`: 2,092 passed. ruff and mypy 1.14.1: clean. The test schemas are dropped after each run.
- Where "the audit log" is: `.agent-history.log`, the repository's gate history, the log the session-start checklist
  reads. An approved weakening is MAJOR and resolved (the approval is the resolution); a refused one is MAJOR and
  unresolved, so the next session start surfaces it. The portal's audit log records run-time actions, not commits, and
  is not written from a commit hook.
- Siblings: the `compliance` key in `process-gates.json` keeps its own ratchet (`compliance_transition_problems`);
  both now cite approvals from the same `approvals.jsonl`. Deleting the declaration is a weakening here and, where the
  profile is enforced, a failing verdict (R24).
- Limits, stated: the rule reads the fields the profile defines today; a field added later needs a line in
  `declaration_weakenings`. CI refuses the same commits but does not write the local log.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one verdict function, used by the hook and by CI; one approvals file for both ratchets.
Group 2 · Quality / safety — [x] checked — a weakening needs the owner's recorded approval; strengthening and filling need nothing.
Group 3 · Architecture / hygiene — [x] checked — the rule sits beside the config ratchet in `gate_pillars.py`; one logging function.
Group 4 · Process — [x] checked — design first with the owner's decision; CHANGELOG, backlog and manual updated.
Group 5 · Intuitive UI — [x] checked — the refusal names each weakened field and says how to approve.
Group 6 · Signal integrity — [x] checked — every change is logged; a refused one stays unresolved until someone resolves it.
Group 7 · Auth & session integrity — [x] checked — only an approval recorded at a terminal unlocks a weakening; an agent cannot write `approvals.jsonl`.

Tests added: thirty-one in `scripts/test/test_declaration_ratchet.py`; two database tests in `agentsmith/test/test_compliance_runtime.py`; the old shell-gate test, which asserted the opposite, removed.
Mutation-checked: yes, by hand; eleven mutants, all killed after pass 1.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above with `COMPLIANCE_TEST_DSN`; the whole of `scripts/test`; ruff; mypy; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `consistent-auth-gates`, `declared-vs-enforced`, `failure-mode-visibility`, `test-that-cannot-fail`

KG query: kg:8183514f8755
