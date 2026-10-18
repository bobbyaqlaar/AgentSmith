# Review — a killed mutation run undoes itself

Design: `.agent-rfc/designs/mutation-check-journal.md`. Owner's instruction, 2026-10-17: "make
mutation_check interrupt-safe", after a cancelled `gates run` left a live mutation in the tree the
day before.

**Built evidence (2026-10-17):**

- **What was already there, read before writing anything.** `_install_restore_handlers` restores on
  `SIGINT`/`SIGTERM`, `run_suite`'s `finally` restores after an exception, and `--allow-dirty` saves
  pristine copies to a fresh `mkdtemp`. So the slice is **not** "add signal handling"; it is the two
  holes those leave: a `SIGKILL`, whose backstop is the *next* run refusing on a dirty catalogue
  file, and `--allow-dirty`, which skips that backstop entirely.
- **Tests first**, `scripts/test/test_mutation_check_journal.py`: 9 of 9 failing before the change
  (the functions did not exist), 12 passing after.
- **Proven end to end with a real kill**, not only by unit tests
  (`kill9_proof.sh`, kept in the session scratchpad): a `send_dev_record` run was `kill -9`ed while
  a mutant was on disk; `git status` showed ` M scripts/send_dev_record.py` and the journal naming
  the file and the mutation; the next invocation printed
  `♻️ restored scripts/send_dev_record.py — a previous run was killed while testing: send_dev_record:
  redirects are followed …`, cleared the record, and left the tree clean.
- **Hand mutants: 8 of 8 caught**, each reverted — `--allow-dirty` skipping recovery, `main`
  dropping the refusal, restoring without checking the mutant hash, no path-escape check, a corrupt
  journal proceeding, the `finally` not clearing, the journal written after the mutation, and a
  missing copy restoring silently.

## Pass 1 — findings: 1

- `implemented-not-invoked` — **finding:** `_recover_journal` was called just before the dirty-file
  check, which sits **after** `--list`'s early return, so `mutation_check.py --list` walked straight
  past a mutation the tool had left in the tree. Found by the `kill -9` proof — the unit tests call
  `_recover_journal` directly and structurally cannot see where `main` calls it. Moved to
  immediately after `parse_args`, ahead of `--list` and suite selection, with the reason in a
  comment: repairing its own residue is the inverse of the damage it did, not a side effect a caller
  opts into. `test_even_listing_the_suites_repairs_residue` pins it.

## Pass 2 — findings: 4

The first mutant run reported **3 of 8 caught**. Every survivor was a real hole in my tests, and one
was a bad mutant of mine:

- `test-that-cannot-fail` — **finding:** nothing asserted the journal is written **while** the
  mutant is on disk, so a mutant deleting the whole `_write_journal` call survived: every other test
  checks the journal is *absent* afterwards, which is also true if it was never written. Added
  `test_the_record_exists_while_the_mutant_is_on_disk`, which inspects the journal from inside the
  suite run, at the one moment it matters, and asserts the recorded mutant hash equals the file on
  disk.
- `test-the-contract` — **finding:** no test asserted `main` **returns** the refusal rather than
  merely calling recovery. `test_main_stops_when_recovery_refuses` now does.
- `fixture-truth` — **finding:** `test_a_journal_naming_a_path_outside_the_repo_refuses` passed for
  the wrong reason. Its escaping path did not exist, so the refusal came from "that path is not
  there now" and a mutant deleting the escape check survived. The test now creates a real file
  outside the repository holding the mutant text, and asserts it is still untouched afterwards.
- `guards-must-be-able-to-fail` — **finding, in my own mutant:** "corrupt journal proceeds" was
  written as `return 0 or refuse(...)`, which is `refuse(...)` — a no-op mutation that can never
  survive and therefore proves nothing. Rewritten as `return 0 if exc else refuse(...)`.

## Pass 3 — findings: 1

- `test-that-cannot-fail` again, and this one invalidated a whole mutant run — **finding:** after
  pass 2 the mutants reported **8 of 8 caught while one of my own tests was red**
  (`test_the_record_exists_while_the_mutant_is_on_disk`). A failing test makes every mutant look
  caught: the run is not evidence, it is noise. The cause was the test's fake `_pytest` returning
  failure for the **baseline** call too, and `run_suite` abandons a suite whose baseline fails
  (`BASELINE ALREADY FAILING`), so nothing was ever mutated. The fake now passes the baseline and
  fails the mutant, as a real run does, and asserts it was called at least twice. Both run_suite
  tests were fixed the same way. Re-run with a green suite: **8 of 8 caught**, and that number now
  means something.

## Pass 4 — findings: 0

- `when-the-fallback-fails` — the rung below the dirty-file check exists and is tested under the
  flag that disabled it.
- `early-exit-keeps-the-record` — the signal handler clears the journal as well as restoring the
  file; without that, a Ctrl-C would leave a record pointing at a file that is already correct, and
  the next run would spend a refusal on it (covered by the handler path's `_clear_journal`).
- `validate-on-the-receiving-side` — the journal is read back as data: parsed in a `try`, path
  resolved and required to be under `REPO`, contents compared by sha256, never executed.
- `minimal-host-dependency` — the git directory comes from `git rev-parse --git-dir`, not
  `REPO / ".git"`, because in a worktree that path is a file; the lesson of the slice committed an
  hour earlier (`a34c79d`).
- `docs-match-behaviour` — the CHANGELOG entry states what is restored automatically and what
  refuses; `docs/PRODUCT_BACKLOG.md`'s "two agents in one checkout" row carries today's recurrence,
  which is what its own trigger asked for, and notes that the recorded pid makes the deferred lock a
  small step. The owner's 2026-09-16 decision to defer that lock is not reopened here.
- Checked and declined: a lock file, per that decision; a multi-entry journal, because `run_suite`
  holds one mutation at a time by construction and a list would be speculation (said in the design,
  with what would supersede it).

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked — a run that cannot be trusted is the defect
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_mutation_check_journal.py — new, 12 tests (9 failing first,
                          3 added by passes 1-2); the two run_suite fakes corrected in pass 3
Mutation-checked:          8 hand mutants, 8 caught, each reverted — and the first two runs
                          were discarded: one had 5 survivors (pass 2), one was taken while a
                          test was red (pass 3), which makes every mutant look caught
Live proof:                a real run kill -9'ed mid-mutation, residue shown in `git status`,
                          repaired by the next invocation, tree clean after
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:2ea636ad0366
Gates run locally:         six by name, all passing — the process gate itself, commit
                          guardrails, ruff, py_compile, --check-kg, bash -n/zsh -n — plus 187
                          tests over the suites this change can reach: the new journal file,
                          mutation scope/sharding, the bare-except sweep over every tracked
                          Python file (this slice adds two `except` clauses), the documented
                          env-var sweep, the shell gate and the knowledge graph.
                          NOT run: the full `gates run`, whose curated-mutation step is
                          unsharded locally and ran four hours yesterday; CI shards it four
                          ways. Running THIS harness's own curated suites over a change to
                          the harness would also have it mutating itself mid-run
Declared gaps:             two concurrent runs in one checkout still share one journal — the
                          owner deferred that lock on 2026-09-16 and the backlog row now
                          carries today's recurrence plus the pid that makes it cheap. A
                          SIGKILL between the mutant's write and the journal's write is not
                          possible in that order, but a SIGKILL between the restore and the
                          journal clear leaves a record whose file is already correct; that
                          case is the "clear and proceed" row, not a refusal
```
