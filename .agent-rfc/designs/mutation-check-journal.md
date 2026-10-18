---
status: done
scope:
  - scripts/mutation_check.py
  - scripts/test/test_mutation_check_journal.py
---
# A killed mutation run undoes itself

## Problem

`scripts/mutation_check.py` rewrites the files it mutates and puts each one back. It already covers
the interruptions it can catch: `_install_restore_handlers` restores on `SIGINT`/`SIGTERM`, and
`run_suite`'s `finally` restores after any exception. What it cannot catch is `SIGKILL` — and for
that case its backstop is **the next run refusing**, in `_dirty_catalogue_files`:

> "Refusing to start on a dirty file covers both: it protects work in progress, and it is what
> surfaces the residue of a previous crashed run."

That backstop has two holes, and the second one let a mutation sit in this repository for hours on
2026-10-16:

1. **`--allow-dirty` skips it entirely.** The flag exists for the author's own case — you cannot
   mutation-test a fix before you commit it — so it is what you pass whenever your own files are
   uncommitted, which is most of the time while fixing something. With it, a previous run's residue
   is waved through with the rest.
2. **The refusal asks the human to judge a diff they did not write.** Its message ends "If you did
   not edit these, a previous run was killed before it could restore one — check the diff before
   discarding it." Nothing on disk says which file a killed run was holding, or what it wrote
   there, so the reader has to recognise a mutant by reading code.

**What happened, as evidence.** `agentsmith gates run` invokes this harness; the run was cancelled
from the IDE (a kill the handlers do not see). The tree's dirty files were mine and none of them
was a catalogue file, so nothing refused, and `scripts/rules_port.py` was left with `_ours(...)`
dropped from its placement check — a live mutation, in a gated file, in the working tree. It was
found only because a later review read `git status` closely; two subsequent runs with
`--allow-dirty` said nothing. A `git commit -a` or `git add -A` would have committed it, and the
only test that would have caught it is the one the mutation exists to defend.

The pristine copies `--allow-dirty` saves are no help here: they go to a fresh `mkdtemp` whose path
is printed once and recorded nowhere, so a later run cannot find them.

## Approach

**A journal, so the tool knows its own writes.** Before each mutant reaches disk, write
`<git-dir>/agentsmith-mutation-journal.json` (atomically, via a temp file and `os.replace`) holding:
the repository-relative path, the sha256 of the pristine text, the sha256 of the mutant text, a
copy of the pristine text beside the journal, the suite and mutation label, the pid, and a UTC
timestamp. Remove it, and the copy, as soon as the file is restored — in `run_suite`'s `finally`
**and** in the signal handler, which today restores the file but would leave a journal behind.

The git directory is found with `git rev-parse --git-dir` rather than assuming `REPO / ".git"`,
because in a worktree that path is a file — the lesson of
`.agent-rfc/designs/kg-skips-nested-checkouts.md`, one slice earlier.

**Recovery at startup, before anything else** (`_recover_journal`), deciding by content rather than
by guesswork:

| The file on disk | What it means | What happens |
|---|---|---|
| matches the recorded pristine sha | a run restored it and died before clearing | clear the journal, say so, proceed |
| matches the recorded **mutant** sha | unambiguously this tool's residue | restore from the copy, name the file and the mutation, clear, proceed |
| matches neither | edited since the kill | **refuse**, naming the path, the mutation and the pristine copy, writing nothing |
| matches the mutant sha, copy missing | residue, but nothing to restore from | **refuse**, naming the mutation so the diff is readable |

Recording the mutant's own sha is what makes the second row safe to automate: the tool restores only
a file whose contents are byte-for-byte what it wrote.

**The recovery runs regardless of `--allow-dirty`.** The journal is about this harness's writes, not
about the author's uncommitted work, so the flag that exists to permit the latter must not suppress
the former. That is hole 1, and it is the one test that would have caught today's residue.

**Not in scope:** a journal of more than one file. One mutation is live at a time by construction —
`run_suite` writes, tests, restores, then moves on — so a single-entry journal matches the
behaviour. If the harness ever mutates two files at once, the journal becomes a list and this note
is superseded rather than stretched.

## Pillars

- P1 applies — this note (`.agent-rfc/designs/mutation-check-journal.md`) precedes the change; the defect is recorded with its evidence in `.agent-rfc/reviews/kg-skips-nested-checkouts.md` pass 4, where `scripts/rules_port.py` was found mutated.
- P2 n/a — no dependency added; `hashlib`, `json`, `os` and `tempfile` are already imported or standard.
- P3 n/a — a developer and CI tool, not a traced runtime path.
- P4 applies — failing tests first in `scripts/test/test_mutation_check_journal.py`: residue restored, an edited file refused, an already-restored file only clearing the journal, `--allow-dirty` not skipping recovery, a missing pristine copy refusing, and a completed `run_suite` leaving no journal.
- P7 applies — `_journal_path`, `_write_journal`, `_clear_journal` and `_recover_journal` are annotated like the rest of `scripts/mutation_check.py`, and the journal is JSON through `gm`-free plain `json` as the file already uses.
- P8 n/a — no telemetry; the harness reports to stdout and its exit code.
- P9 n/a — no orchestration.
- P10 n/a — no model calls.
- P11 applies — the journal is a file this tool wrote, but it is read back as untrusted data: paths are resolved under `REPO` and rejected otherwise, and contents are compared by sha256, never executed or trusted to be well-formed (a corrupt journal refuses rather than acting).
- P12 n/a — no credentials. The journal holds source text that is already in the repository.
- P13 applies — this protects gate integrity rather than touching a gate: a mutation left in `scripts/process_gate.py` or `scripts/gate_shell.py` is a silently weakened gate, which is what happened to `scripts/rules_port.py`. `_recover_journal` is the check, and `test_allow_dirty_does_not_skip_the_residue_check` is the test that fails without it.
- P14 applies — no fixture is involved beyond `.agent-rfc/fixtures/knowledge_graph.json`, regenerated because `scripts/mutation_check.py` gains symbols.
- P15 applies — "the author's uncommitted work" and "a killed run's residue" were one signal (a dirty file in `_dirty_catalogue_files`); `_recover_journal` separates them by hash, and "edited since" is a third answer rather than being folded into either — `test_an_edited_file_is_never_silently_overwritten` pins that it refuses instead of restoring, and `test_a_file_already_put_back_only_clears_the_journal` pins the quiet case.
- P16 applies — this slice *is* a recovery path, in `_recover_journal`, and it fails closed: no journal means proceed (`test_no_journal_is_the_normal_case`), a journal it cannot parse or reconcile means refuse (`test_a_corrupt_journal_refuses_rather_than_acting`, `test_a_missing_pristine_copy_refuses_rather_than_guessing`), and the restore itself is the recovery proven by `kill9_proof.sh` against `scripts/send_dev_record.py`.

## Deviations

none

## Dependencies

None added.

## Levers

- `when-the-fallback-fails` — the existing fallback (refuse on a dirty catalogue file) fails under `--allow-dirty`; this is the rung below it.
- `guards-must-be-able-to-fail` — the residue guard has a test that fails without it, under the flag that disabled the old one.
- `ambiguous-signals` — a dirty file meant two things; a journal entry with two shas means exactly one.
- `irreversible-needs-confirmation` — automatic restore only where attribution is byte-exact; anything else refuses and hands the human both versions.
- `early-exit-keeps-the-record` — the signal handler restored the file but left no record cleared; both paths now clear the journal.
- `declared-vs-enforced` — the docstring claiming the dirty check "surfaces the residue of a previous crashed run" is made true, or narrowed to what it does.
