# Review: coding-agent-tokens

The build half of the token goal and gap 6, after the owner's instruction of 2026-11-10 to do the token items first, for AgentSmith's own build and for coding agents building tenants.

## Pass 1 — findings: 4

Against `docs/review-levers.md`, and against this repository's own transcript.

1. **The first count was inflated about 2.5 times.** One response spans several transcript lines that repeat its usage, so summing lines read 10.8 billion cached tokens where the true figure is 4.3 billion. Fixed: counted once per response, by message id; a test pins it.
2. **`git interpret-trailers` matches keys by prefix,** so adding `Agent-Tokens` replaced the `Agent:` line, in the module test and in the real hook path. Fixed: the trailers are written directly, replacing only themselves.
3. **A subject-only message (`docs: notes`) looked like a trailer line,** so the trailers would have joined the subject. Fixed: a trailer block is a paragraph after the subject.
4. **Nothing proved the stop and session-start hooks record the session;** the tests called the recorder directly, and a hand mutant removing the hook call survived. Fixed: a test drives `process_gate.py stop` and `session-start` with a real payload.

## Pass 2 — findings: 1

1. **The session-start budget test wrote into this repository's own ledger.** It ran the hook against the real checkout with a made-up transcript path. The commit after it showed the cost: `Agent: claude-code` and, correctly, no token trailer, because nothing could be read. Fixed: the test sends no transcript path. The stray ledger was removed.

## Pass 3 — findings: 2

Found on the first real trailer, this repository's own commit `555cfc5`.

1. **A session's first measured commit claimed "since this session's previous commit"** while counting the whole session. Fixed: it says "this session so far: its first commit".
2. **Billions printed as millions** ("5276.6M"). Fixed: "5.3B".

## Pass 4 — findings: 0

- `scripts/test/test_agent_tokens.py`: counting once per response, incremental reads that leave a half-written line for next time, the context size, other agents and missing transcripts recording nothing, a new session starting from zero, the note once per step, trailers only from Claude Code's shell and only what was spent since the session's previous commit, placement in the message, and a real commit through an adopted tenant's own hooks, with and without an agent.
- `scripts/test/test_context_budget.py`: every rule file a tenant gets, for three stacks, under 3,000 tokens (estimated); the token-discipline block in all five instruction files; the session-start message under 1,200 tokens. The largest rule file is about 2,600.
- Ten hand mutants, all caught.
- The related suites (process gate, rules contract, sync, gate table, repository tree, environment variables): 367 passed; ruff and mypy clean.

Left out on purpose, and documented: Cursor, Codex, Gemini CLI, Copilot and Antigravity get no trailer until their hook payloads are confirmed (gap 11). Showing the tokens in the portal comes with the run-side token work.

## Pass 5 — findings: 3

CI on PR #113 failed where the local targeted runs had passed; each was checked in code.

1. **Two empty `except` blocks in `scripts/process_gate.py`** (`_remember_session`, `_context_note`) had no `# fail-open:` reason, so the bare-except tree test failed. Fixed: each says why it fails open.
2. **The session-start budget test ran the hook through `.githooks/process-gate`**, which looks for an installed environment a CI runner lacks. Fixed: it runs `scripts/process_gate.py` with the test's own interpreter.
3. **`test_context_budget.py` loaded the generator with its own `importlib` spec loader**, a second script loader the tree test forbids. Fixed: `load_script("generate-ide-config")` from `_shared`.

The lesson, kept for the next slice: run the whole `scripts/test` suite in a clean environment (no install on PATH, no `AGENTSMITH_DIR`, no `CLAUDECODE`) before pushing, not only the related suites.

## Pass 6 — findings: 0

- The whole `scripts/test` suite in a clean environment, with ruff and mypy.

## Earlier sign-off (after Pass 6; superseded by the sign-off at the end)

Group 1 · DRY & shared code — [x] checked — one reader for the transcript, used by the hooks, the trailers and the report.
Group 2 · Quality / safety — [x] checked — bookkeeping never fails a hook or a commit; counts only, no text copied.
Group 3 · Architecture / hygiene — [x] checked — one module beside the gate; the ledger lives in the git directory, never committed.
Group 4 · Process — [x] checked — design first; manual, CHANGELOG and repository tree updated.
Group 5 · Intuitive UI — [x] n/a — no screen changes; the note is one line to the person.
Group 6 · Signal integrity — [x] checked — no measurement is no trailer, never zero; a missing trailer reads as not recorded.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: `scripts/test/test_agent_tokens.py`, `scripts/test/test_context_budget.py`.
Mutation-checked: yes, by hand; ten mutants, all killed.
Fixtures re-pinned: `templates/governance.json`, `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; ruff; mypy; the process gate against the commit.

Levers reviewed: `failure-is-not-a-result`, `implemented-not-invoked`, `test-that-cannot-fail`.

Scope at the first sign-off: kg:97882b6bb1df

## Pass 7 — findings: 2

The 4.1.0 release review, verified in the code first.

1. **R3** — the ledger held one session and was reset by any other session's hook, and `commit-msg` advanced the baseline before the commit existed. Reproduced in tests: two sessions in one checkout, a commit a later hook refused, and `--amend`, each failing on `origin/main`. Fixed: one entry per transcript, the committing shell's session chosen by `CLAUDE_CODE_SESSION_ID`, and a pending baseline confirmed by finding its exact trailer line on a landed commit. A sibling: `context_note` read "the" session; it now reads the payload's transcript.
2. **R7** — the backlog said `Agent:` on each commit. Wording fixed in the backlog commit of this PR.

## Pass 8 — findings: 1

1. **The tests read this session's own `CLAUDE_CODE_SESSION_ID`.** Run from Claude Code, two tests chose no session and failed; from a plain shell they would have passed, so the result depended on who ran them. An autouse fixture clears it; tests that mean one name it.

## Pass 9 — findings: 0

- `scripts/test/test_agent_tokens.py`: 28 passed, including the real hook path for a commit and for `--amend`.
- Five hand mutants (always adopt the pending baseline; pick any session; pick the only session when there are two; ignore the amend base; drop the old-ledger reading), all killed.
- No post-commit hook added: `.githooks` has none, and one would chain tenants' post-commit hooks, which can push.

## Earlier sign-off (after the 4.1.0 review, Pass 9; superseded by the sign-off at the end)

Group 1 · DRY & shared code — [x] checked — one `entry()` chooses a session for the trailer, the note and the report.
Group 2 · Quality / safety — [x] checked — bookkeeping still never fails a commit; ambiguity writes no count.
Group 3 · Architecture / hygiene — [x] checked — the ledger is local; the old shape is read.
Group 4 · Process — [x] checked — design addendum first; manual and CHANGELOG updated.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — a trailer is a session's own spend or absent.
Group 7 · Auth & session integrity — [x] n/a — no auth code.

Tests added: six in `scripts/test/test_agent_tokens.py`.
Mutation-checked: yes, by hand; five mutants, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suite above; the knowledge-graph check; the process gate against the commit.

Levers reviewed: `out-of-order-and-repeated`, `failure-is-not-a-result`, `implemented-not-invoked`, `docs-match-behaviour`, `test-that-cannot-fail`.

Pass 9 KG query: kg:a82981f44083

## Pass 10 — findings: 9

Reopened on 2026-11-22: commits `85735d2` and `0298743` on `feat/ruff-s-rules`, made from a linked worktree, carried `Agent:` without `Agent-Tokens:`. The cause: the session's hooks recorded its transcript in the main checkout's git directory, and the commit hook read the worktree's own. The design gains "Worktrees and concurrent sessions". Its tests were written first and failed on the old code (7 failed, 23 passed); the real commit from a worktree came out with `Agent:` alone. An independent reviewer (Opus) read the change; each finding was checked in code.

1. **Blocker — the design lost its `## Pillars` heading.** The new section replaced it, so the gate would refuse the design. Fixed: restored.
2. **Code from before still writes the same file and would replace every other session.** In the main checkout the old path and the new are one file, and a checkout on an older branch runs the old `remember`. Fixed: the new ledger is `agent-sessions.json`; the old `agent-tokens.json` is read for sessions the new one lacks, never written. Test: `test_older_code_writing_its_ledger_drops_no_other_session`.
3. **The gone-transcript test could not fail.** The gone session was also the oldest, so the 32 cap dropped it anyway. Fixed: `test_a_gone_transcripts_session_is_dropped` makes it the newest; the cap has its own test.
4. **Manual and CHANGELOG were stale.** Fixed: both name the new file, one entry per session, `CLAUDE_CODE_SESSION_ID`, and `report` listing every session.
5. **An entry rebuilt mid-session double-counts and calls itself a first commit.** Not changed in code: the trailer says "this session so far", and the routes to it are now rarer (legacy read, separate file). The design names each route under "What still miscounts, and says so".
6. **Nothing tested the stop hook's note scoping.** Fixed: `test_the_stop_hooks_note_is_its_own_sessions` drives `process_gate._context_note`.
7. **An older Claude Code effectively loses the trailer for good.** Without the id, a second recorded session ends it. Fixed in the design and the backlog, which say so plainly; the code keeps refusing to guess.
8. **A malformed `seen` would stop every write.** Fixed: `_seen` reads anything but a number as 0. Test: `test_a_malformed_entry_does_not_stop_the_recording`.
9. **The lock could hang a hook or disable recording.** Fixed: taken without blocking, retried for at most `LOCK_SECONDS` (10), then skipped (no trailer); a filesystem without locks is used unlocked. Tests: `test_a_held_lock_skips_the_bookkeeping_and_never_hangs`, `test_a_filesystem_without_locks_still_records`.

Not verified, and in the design and backlog: whether child or forked Claude Code sessions run the repository's hooks.

Evidence: `scripts/test/test_agent_tokens.py` 37 passed. Twelve hand mutants, all killed: ledger in the worktree's own git directory, session id ignored, a guess among several sessions, no legacy read, gone transcripts kept, no cap, `seen` trusted, an unsupported lock giving up, a held lock proceeding, the note unscoped, never written, every session under one key. The full suite before these fixes, in a clean environment (no `CLAUDECODE`, session id, `AGENTSMITH_DIR` or install on PATH): 2794 passed, 17 skipped.

## Pass 11 — findings: 8

A second independent reviewer (Opus) read the change and checked each Pass 10 fix; each finding was checked in code.

1. **A committing session could be pruned straight after its commit, and repeat its spend.** A session known only from a legacy ledger had no `seen`, so the cap dropped it, the legacy copy came back with its older baseline, and the next commit reported the same tokens again. Fixed: a commit marks its session as used (`_stamp`). Test: `test_a_committed_session_outlasts_the_cap`. Pass 10 item 5's text, and the design's, were wrong for this route; the design now names it.
2. **The knowledge graph was stale** (`_git_dir`, `_ledger_path`, `_save` still listed). Fixed: regenerated; `verify_system.py --check-kg-fresh` passes.
3. **Bad arguments printed a docstring paragraph above the usage.** The new paragraph moved the split. Fixed: the usage is the last paragraph. Test: `test_the_usage_is_only_the_commands`.
4. **`load()` is called only by the tests.** Not changed: it is the reading API the tests use to see one session's entry, and existed before this change.
5. **`version` was written and never read.** A later shape would be read and written back as 2, the clash Pass 10 item 2 hit. Fixed: a ledger with a later version is neither read nor rewritten. Test: `test_a_ledger_a_later_version_wrote_is_left_alone`.
6. **The stop command's wiring was not tested.** Fixed: `test_the_stop_command_gives_its_sessions_note` runs `process_gate.py stop` for two sessions. The mutant that passes `{}` instead of the payload survives, and is equivalent: the stop command records its session first, which stamps it the newest, so the unscoped note reads the same entry. The scoping matters only when that record failed, and `test_the_stop_hooks_note_is_its_own_sessions` holds it at the function.
7. **Ties in `seen` fell to dict order,** so the cap test leaned on the clock. Fixed: `_stamp` sets `seen` past every other entry's. Test: `test_sessions_are_ordered_even_when_the_clock_stands_still`.
8. **A run-on sentence in the design's P4.** Fixed.

Evidence: `scripts/test/test_agent_tokens.py` 42 passed. Eighteen hand mutants: seventeen killed; the survivor is item 6's equivalent mutant.

## Pass 12 — findings: 6

A third independent reviewer (Opus) checked the Pass 11 fixes and read the change again; each finding was checked in code.

1. **A legacy session whose transcript is gone came back on every read.** The old ledger is never rewritten, so pruning on write did not reach it; with a Claude Code that sets no session id, a repository with a 4.1.0 ledger then had two sessions forever and no `Agent-Tokens:`. Fixed: the old ledger's session is read only while its transcript exists. Test: `test_a_legacy_session_whose_transcript_is_gone_is_not_read`.
2. **Subagents' tokens are not counted, and a subagent's commit carries its parent's spend.** A subagent's shell has its parent's `CLAUDE_CODE_SESSION_ID`; its usage is in `<id>/subagents/agent-*.jsonl`, which is never read. True before this change too. The design, the manual and the backlog said child sessions were "unconfirmed" with a trigger that could never fire. Fixed in all three: they say what happens. Counting subagents is a backlog row, for the next token slice.
3. **Pass 11 item 6's "equivalent" mutant was not equivalent.** A stopping session the ledger cannot keep (its transcript absent) was lent the previous session's note. Pass 11's claim was wrong. Fixed: `test_the_stop_command_never_lends_another_sessions_note` kills it.
4. **`report` said "no session recorded" for a ledger a later version wrote.** Fixed: it says the ledger is a later release's. Test: `test_report_says_when_a_later_version_wrote_the_ledger`.
5. **The ledger was created mode 0600** (a temporary file's), where the old file kept the umask; on a repository shared between users another user's hook would read it as empty and replace it. Fixed: it takes the lock file's mode. Test: `test_the_ledger_keeps_the_umask_mode`.
6. **`Agent:` was lost when `.git/agentsmith` could not be written.** Fixed: a ledger that cannot be read or saved costs the `Agent-Tokens:` line only. Test: `test_an_unwritable_ledger_still_says_who`.

Evidence: `scripts/test/test_agent_tokens.py` 47 passed. Twenty-two hand mutants, all killed. The full suite on Pass 11's code, clean environment: 2806 passed, 17 skipped. Ruff clean over the tree; `check_bare_except.py` clean; graph regenerated and fresh.

## Pass 13 — findings: 1

A fourth independent reviewer (Opus) checked the Pass 12 fixes and read the change again; the finding was checked in code.

1. **An entry with a field of the wrong type still lost `Agent:`.** `"totals": null`, a string `offset` or a non-list `recent_ids` raised `AttributeError`, `ValueError` or `TypeError`, which the `except OSError` in `trailers` did not catch; a bad `offset` also failed every hook for that session, for good. Same class as Pass 10 item 8. Fixed at the source: `_read` keeps only entries whose fields have the types this code uses (`_whole`), from the ledger and the legacy ledger alike; any other is left out, and the session is read again from its transcript's start. Test: `test_a_malformed_entry_is_read_again_and_the_commit_still_says_who` (two of its first five shapes could not fail; see Pass 14).

Evidence: twenty-three hand mutants, all killed (the new one trusts an entry's shape). Ruff clean over the tree; `check_bare_except.py` clean; graph regenerated and fresh. The full run on Pass 12's code was stopped part-way, because this fix changed the code under it.

## Pass 14 — findings: 3

A fifth independent reviewer (Opus) checked Pass 13's fix, including that every entry this code writes passes `_whole` (it does: `_fresh`, `read_new`, `_spend` and `context_note` each write the checked types); each finding was checked in code.

1. **Two of Pass 13's five test shapes could not fail, and the shapes that do raise were untested.** A string `recent_ids` is still iterable, `context` -1 raises nowhere, and no new line was waiting, so `read_new` never touched `recent_ids`. A mutant dropping the `recent_ids`, `context` or `noted` check survived. Pass 13's record said a non-list `recent_ids` raised; the one tested did not. Fixed: the test appends a line, asks for the note, commits and records, over six shapes (`totals` null, `offset` "x", `recent_ids` 5, `context` "x", `noted` "x", a string in `at_last_commit`); each one's mutant fails it (Pass 15 corrects why).
2. **An offset of the right type past the transcript's end** (a replaced transcript, or 2**63, which `seek` cannot take) still lost the trailer and failed every hook for that session. Fixed: `read_new` reads the transcript again from its start when the offset is past its end. Test: `test_an_offset_past_the_transcripts_end_reads_it_again`.
3. **The design's list of routes that rebuild an entry omitted the two above.** Fixed: it names a wrong-shaped entry and an offset past the end.

Evidence: `scripts/test/test_agent_tokens.py` 55 passed. Twenty-seven hand mutants, all killed (new: each of the `recent_ids`, `context` and `noted` checks dropped alone, and the end-of-file check). The full suite on Pass 13's code, clean environment: 2816 passed, 17 skipped. Ruff clean over the tree; `check_bare_except.py` clean; graph regenerated and fresh.

## Pass 15 — findings: 2

A sixth independent reviewer (Opus) checked Pass 14's fixes; it found the offset reset sound (both callers of `read_new` stamp the entry after it, the reset is made in place so the ledger sees it, and a transcript that only grows never trips it). Each finding was checked in code.

1. **The replaced-transcript case of the offset test could not fail.** With the end-of-file check removed, `seek(10_000)` read nothing and the commit still reported the first line, so only the 2**63 case caught the mutant, and a fix that only stopped the crash would have passed both while leaving a replaced transcript uncounted. Fixed: the test appends a line after the offset is set and asserts it is counted (output 8). New mutant, killed: the crash stopped (`> sys.maxsize`) without reading again.
2. **The malformed-entry test and Pass 14's record said every shape raised; `totals` null does not.** With a line waiting, `read_new` counts it from nothing. Its mutant is still caught (the note and the count differ). Fixed: the docstring and the Pass 14 entry say so.

Evidence: `scripts/test/test_agent_tokens.py` 55 passed. Twenty-eight hand mutants, all killed. Ruff clean over the tree; `check_bare_except.py` clean; graph fresh.

## Pass 16 — findings: 1

A seventh independent reviewer (Opus) checked Pass 15's fixes (both hold) and read the change again; the finding was checked in code and against this project's transcripts.

1. **Blocker — a new session's session-start record was thrown away.** Claude Code writes a new session's transcript just after its SessionStart hook (the hook's record and the file's birth fall in the same second in this project's transcripts; the reviewer measured 0.04–0.21 s after). `_write` dropped every entry whose transcript was not a file, so a session had no entry until its first Stop. A commit in its first turn got `Agent:` alone, where the code before this change gave `Agent-Tokens:`; with no session id it got another session's spend, which the design forbids. No test modelled the real order. Fixed: an entry never read (offset 0) is kept for `UNREAD_SECONDS` (a day) though its transcript is not there yet; one already read is dropped when its transcript goes. Tests: `test_a_session_recorded_before_its_transcript_exists_is_kept`, `test_an_unread_session_is_dropped_after_a_day`, and `test_a_first_turn_commit_from_a_worktree_carries_the_tokens` (session start through `process_gate.py`, then the transcript, then a real commit from a worktree). The design says so.

The fix revived a survivor: the stop command's unscoped-note mutant had been killed only because a session with no transcript was dropped. `test_the_stop_command_never_lends_another_sessions_note` now runs `cmd_stop` with another session's hook run between its record and its note (the two take the lock separately), which is the case the scoping exists for; it kills the mutant.

Evidence: `scripts/test/test_agent_tokens.py` 58 passed. Thirty hand mutants, all killed (new: an unread session dropped, an unread session kept for ever). Ruff clean over the tree; `check_bare_except.py` clean; graph regenerated and fresh.

## Pass 17 — findings: 0

An eighth independent reviewer (Opus) checked Pass 16's fix against every earlier finding it could reopen and found none. Among the checks:
- the no-id fallback, where a never-read entry costs the count for at most a day and never gives another session's spend;
- an empty transcript, the cap and the legacy read, which still needs a live transcript;
- `context_note`, `report`, and fail-open on every commit path;
- the in-process `cmd_stop` test, run against a mutated copy, which it fails.

It also checked that the design, CHANGELOG, manual and backlog match the code.

Evidence:
- `scripts/test/test_agent_tokens.py`: 58 passed.
- The full suite on this code, in a clean environment (no `CLAUDECODE`, session id, `AGENTSMITH_DIR` or install on PATH): 2822 passed, 17 skipped, 0 failed.

## Earlier sign-off (after Pass 17; superseded by the sign-off at the end)

Group 1 · DRY & shared code           [x] checked — one ledger reader and writer (`_ledger`), used by hooks, trailers, note and report; one stamp (`_stamp`); one shape check (`_whole`) for the ledger and the legacy ledger alike
Group 2 · Quality / safety            [x] checked — a hook or commit never fails or hangs on bookkeeping: bounded lock, an unsupported lock used unlocked, a ledger that cannot be read or saved costs only `Agent-Tokens:`, a malformed entry or an offset past the end is read again; whole-file writes by rename, at the umask
Group 3 · Architecture / hygiene      [x] checked — one ledger in the git directory every worktree shares, one entry per session; the old file read, never written, so older checkouts cannot replace other sessions; a later version's ledger left alone; bounded at 32 sessions
Group 4 · Process                     [x] checked — design first (its "Worktrees and concurrent sessions" section); tests first, shown failing on the old code; CHANGELOG, manual and backlog updated; eight passes after reopening, the last at 0
Group 5 · Intuitive UI                [x] n/a — no screen; `report` names every session, and says so when a later release wrote the ledger
Group 6 · Signal integrity            [x] checked — no measurement is no trailer, never zero; a wrong session's count is refused (id matching nothing, several sessions and no id); every remaining miscount route is named in the design; tests that could not fail were fixed (Passes 10, 11, 12) and an "equivalent" mutant claim corrected (Pass 12)
Group 7 · Auth & session integrity    [x] checked — a commit is attributed to the session named by `CLAUDE_CODE_SESSION_ID`, or to none; subagents commit under their parent's id and their own tokens are not counted, said in the design, manual and backlog
Group 8 · Security engineering        [x] checked — counts only, no transcript text copied; the ledger keeps the umask mode, not a private or wider one; git called with an argv list
Group 9 · Regulation & compliance     [x] n/a — no data, evidence or model-governance path changes
Group 10 · Code optimisation          [x] checked — each read is the transcript's new bytes only; the lock is held for that read and one rename; at most 32 sessions

Tests added: `scripts/test/test_agent_tokens.py` — worktree (module and real commit, including a first-turn commit in the real hook order), two sessions, unknown and missing session ids, legacy ledgers (shared and a worktree's own, gone transcripts), the cap and its order, malformed entries (six shapes), an offset past the end, an unwritable or later-version ledger, held and unsupported locks, the umask, the usage text, and the stop command's note (subprocess, and in-process with an interleaved hook).
Mutation-checked: yes, by hand; thirty mutants, all killed (Pass 16); runner at the session scratchpad, recorded per pass above.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` (regenerated; `verify_system.py --check-kg-fresh` passes).
Gates run: full suite, clean environment (2822 passed, 17 skipped); `ruff check .`; `scripts/check_bare_except.py`; `verify_system.py --check-kg-fresh`. mypy's scope is `agentsmith/` only, which this change does not touch.

Levers reviewed: `failure-is-not-a-result`, `implemented-not-invoked`, `test-that-cannot-fail`, `records-name-the-right-actor`, `lock-what-you-decide-on`, `prove-it-fails-first`, `bounded-by-default`.

Pass 17 KG query: kg:0553bf4e1af4

## Pass 18 — findings: 4

The merge of `main` into this branch (PR #119 had conflicts). `main` had fixed R3 separately (`a0ee424`, Passes 7–9 above): one entry per session, a baseline moved only once the commit is seen to have landed, and `--amend`. Its ledger was still in each checkout's own git directory. This pass is the author's, checked in code; an independent pass follows.

1. **Two implementations of the same ledger.** Resolved on R3's module and API (`load`, `entry`, `_settle`, `pending`, the amend base, the fortnight rule), with this branch's worktree fix and hardening carried onto it: the shared git directory and its own file, the lock and atomic write, the shape check (extended to R3's fields: `before_last_commit`, `last_commit`, `session_id`, `pending`), the offset reset, the umask, `Agent:` kept on a write failure, a later version left alone, unread sessions kept. The legacy read takes both old shapes (one session, R3's sessions).
2. **R3's settling could not see a commit made in a worktree.** `_settle` looked for the landed commit with `git log` in the hook's own checkout; a worktree's commit lands on another branch, so the baseline would never move and every later commit would repeat the spend. Fixed: `git log --all`, which takes every ref and every worktree's HEAD. Test: `test_a_linked_worktree_reads_the_sessions_ledger` commits in a worktree, records from the main checkout, and expects no repeat; the mutant without `--all` fails it.
3. **R3's fortnight rule would forget a session of unknown age.** An entry with no `seen` (every legacy entry, or a malformed one) read as age infinity and was dropped on the next write. Fixed: an unknown age is kept while its transcript is there. Test: `test_a_malformed_entry_does_not_stop_the_recording`.
4. **Two rules had no test that could fail:** the fortnight rule itself (R3's) and a malformed `pending` (which made `_settle` raise past `trailers` and lose `Agent:`). Fixed: `test_a_session_unused_for_a_fortnight_is_forgotten`, and `pending` added to the malformed-entry shapes.

The tests are R3's file with this branch's ported onto its API. Two of this branch's commit tests now commit for real, because the baseline moves only on landing. This branch's Passes 7–14 are renumbered 10–17 here, and both earlier sign-offs are relabelled. The CHANGELOG entry is narrowed to what is new beside R3's. The design keeps R3's section and the worktree section, which is updated for the merge.

Evidence:
- `scripts/test/test_agent_tokens.py`: 66 passed.
- Thirty-five hand mutants: R3's five, this branch's, settling without `--all`, and an unknown age forgotten. Thirty-three were killed on the first run; the two survivors are item 4, both now killed.
- Ruff is clean over the tree, `check_bare_except.py` is clean, and the graph is regenerated and fresh.

## Pass 19 — findings: 4

An independent reviewer (Opus) checked the merge against `main`'s module and tests. None of R3's test lines were lost. Its aborted-commit, amend and session-choice behaviour holds, and the four files taken wholesale from `main` carry everything this branch had. Each finding was checked in code.

1. **Sessions in the legacy ledger escaped R3's fortnight rule.** The rule ran only on write, and the old `agent-tokens.json` is never rewritten, so a session unused for twenty days came back on every read. With no session id, that second session then stopped every trailer, where R3's code would have dropped it. Fixed: the legacy read applies `_kept`, the write's rule. Test: `test_a_legacy_session_unused_for_a_fortnight_is_not_read`. Its own transcript check then looked redundant, because its mutant survived, so it was removed and the combined mutant (no rules on the legacy read) killed. Pass 20 shows it was not redundant.
2. **A non-finite `pending.at` passed the shape check.** `Infinity` made `_settle` raise `OverflowError` past `trailers`, so `Agent:` was lost. Fixed: `_whole` requires a finite number. Test: a seventh malformed shape.
3. **The blanket rename of the `_tokens` helper renamed five test functions,** which broke one cross-reference in this record, and a docstring kept a pass number from before renumbering. Fixed: the names are restored and the reference and number are corrected.
4. **R3's old-ledger test wrote to the new ledger path,** so it no longer read the real legacy file. Fixed: it writes `LEGACY_LEDGER`.

Evidence:
- `scripts/test/test_agent_tokens.py`: 68 passed.
- Hand mutants: thirty-six, all killed. The surviving mutant was removed with the check (see Pass 20, item 2).
- The full suite on Pass 18's code, in a clean environment: 2911 passed, 17 skipped.
- Ruff is clean, `check_bare_except.py` is clean, and the graph is regenerated and fresh.

## Pass 20 — findings: 2

An independent reviewer (Opus) checked Pass 19's fixes against every legacy shape and offset. Each finding was checked in code.

1. **A number too large for a float still lost `Agent:`, for every session at once.** JSON reads `1` followed by 400 zeros as an int, and `math.isfinite()` on it raises `OverflowError` rather than returning False. That happened inside `_read`, so every hook and commit failed until the file was fixed by hand. `_seen` raised the same way through `_stamp`, which contradicts Pass 11 item 8, and so did showing a count that large. Fixed:
   - `_finite` converts to a float, catching the overflow.
   - Counts must be below 2**63 (`_count`).
   - Tests: three more malformed shapes (a huge `pending.at`, a huge count, a huge `context`) and `test_a_seen_too_large_for_a_float_still_says_who_and_counts`.
2. **Pass 19 item 1 called the legacy read's transcript check redundant; it was not.** An R3 entry written at session start, before the transcript exists (`offset` 0, recent `seen`), is taken from the legacy file only without that check. Taking it is right: it is a second recorded session, so a commit with no session id does not get the first session's spend. The surviving mutant was a missing test, not an equivalent one, which is the pattern Pass 15 item 3 named. Fixed: `test_a_legacy_session_not_yet_written_counts_as_recorded`, which kills the mutant that puts the check back. Pass 19's text says so.

Evidence:
- `scripts/test/test_agent_tokens.py`: 73 passed.
- Thirty-nine hand mutants, all killed. New: the count limit dropped, the overflow uncaught, the unread legacy session not taken.
- The full suite on Pass 19's code, clean environment: 2913 passed, 17 skipped.
- Ruff and `check_bare_except.py` are clean; the graph is regenerated and fresh.

## Pass 21 — findings: 3

An independent reviewer (Opus) checked Pass 20's fixes and confirmed that no number this code writes is rejected. Each finding was reproduced and checked in code.

1. **Medium — in a repository shared between users, another user's transcript broke the ledger.** Claude Code keeps transcripts in 0700 directories. On Python 3.11 and 3.12, which this repository pins and supports, `Path.is_file()` raises `PermissionError` there. Every write failed, so the second user was never recorded and got `Agent:` alone. On 3.13 and later the call returns False, so the first user's session read as gone and was dropped. This was in the branch before the merge. Fixed: `_there` uses `os.stat`; a transcript that cannot be looked at counts as there, and its entry ages out under the fortnight rule. Test: `test_another_users_transcript_is_not_a_gone_one` (a real unreadable directory, so the same on every version).
2. **JSON nested too deep raised `RecursionError` past the read.** That is a `RuntimeError`, not a `ValueError`. On 3.11 a value deep enough to load could also make the ledger's own snapshot raise. Fixed in three ways:
   - `_json` catches it, so the file reads as empty and is replaced.
   - An entry keeps only the fields this code writes (`_FIELDS`); that was top-level only, and Pass 22 completes it.
   - `recent_ids` must hold strings.

   Tests: `test_a_ledger_nested_too_deep_to_read_is_replaced`, at a depth past 3.14's limit as well as 3.11's; `test_an_entry_keeps_only_the_fields_this_code_writes`; and a non-string id as a malformed shape. Python 3.14's C json ignores the interpreter's recursion limit, so the snapshot case itself cannot be shown on the interpreter here; the item rule that prevents it is what is tested.
3. **Counts read from a transcript were not held to the limit.** A count of 2**63 or more was saved and then refused on read. One too large for a float lost `Agent:` where it was shown. Pass 20 item 1's claim covered only counts read from the ledger. Fixed: a usage value that is not a `_count` adds nothing, and totals and context stop below the limit. Test: `test_a_count_no_response_has_adds_nothing`.

These came one input at a time, so the guarantee is now also held at its boundary: `trailers` keeps `Agent:` on any failure while counting, not only an `OSError`. Test: `test_any_failure_in_the_count_keeps_who`.

Evidence:
- `scripts/test/test_agent_tokens.py`: 79 passed.
- Forty-five hand mutants. Forty-three were killed on the first run; the two survivors (the deep-JSON catch, the `recent_ids` item rule) could not fail on 3.14, and are killed after the tests above were strengthened.
- Ruff and `check_bare_except.py` are clean; the graph is regenerated and fresh.
- The full run on Pass 20's code was stopped part-way, because these fixes changed the code.

## Pass 22 — findings: 1

An independent reviewer (Opus) checked Pass 21's fixes. It found `_there` deciding presence everywhere it matters, `_FIELDS` keeping every field R3, 4.1.0 and this branch write, and the wider catch in `trailers` hiding nothing that used to show. The finding was reproduced and checked in code.

1. **Pass 21 item 2 was incomplete: `_FIELDS` dropped unknown keys only at the top of an entry.** These still carried any value into the write:
   - `ide`, which was never type-checked;
   - an unknown key inside a count or `pending`.

   On Python 3.11–3.13, `json.dumps` with `indent` uses the pure-Python encoder, one frame per level. A value that loaded but was too deep to encode made every session's write fail, so no session was recorded and every commit got `Agent:` alone. On 3.12 and 3.13 that band is wide; on 3.11 it is a few levels, because loading shares the same limit (Pass 23). Fixed:
   - `_clean` rebuilds each entry as it is read, from the fields and keys this code writes, at every depth;
   - `ide` must be a string;
   - a non-finite `seen` is dropped there, so `_seen` no longer needs its own overflow guard. Its mutant survived, and it is removed; the mutant that skips the cleaning is killed.

   Tests:
   - `test_an_entry_is_rebuilt_from_what_this_code_writes_at_every_depth` checks the rebuilt keys and fails without the rebuild (its first form, which forced the pure-Python encoder at depth 1,200, could not run on 3.11: Pass 23);
   - a list in `ide` is added as a malformed shape.

   Pass 21's text is corrected.

Evidence:
- `scripts/test/test_agent_tokens.py`: 81 passed.
- Forty-six hand mutants, all killed (new: the entry not rebuilt, `ide` unchecked, `seen` not cleaned).
- Ruff and `check_bare_except.py` are clean; the graph is regenerated and fresh.

## Pass 23 — findings: 1

An independent reviewer (Opus) checked Pass 22's fix and found it sound:
- every read goes through `_clean`;
- nothing either side writes and later reads is dropped;
- no value changes meaning;
- code-written entries come back identical, so there is no repeat write;
- no field can carry depth into `_write` or the snapshot.

The finding was checked in code.

1. **Medium — Pass 22's test could not run on Python 3.11, the interpreter of the gated CI step.** On 3.11 the C scanner shares the interpreter's recursion limit, so `json.loads` of the test's 1,200-deep value raised before the code under test ran. Pass 21's 900-deep value was also within reach of the limit once pytest's own frames count. The fix is version-independent; only the tests and this record's wording were wrong. Fixed: both tests check the rule at a depth that loads on every version (20). The key-set assertions are what kill the mutant that skips the rebuild, and the encoder monkeypatch is gone. The million-deep ledger test stays, because it is past every version's limit. Pass 22's text is corrected.

Python 3.11 is not installed here: this pass's tests run on 3.14, and the gated CI step is the 3.11 check.

Evidence:
- `scripts/test/test_agent_tokens.py`: 81 passed.
- The three affected mutants (the entry not rebuilt, `ide` unchecked, the deep-JSON catch) are still killed.
- The graph is regenerated and fresh.

## Pass 24 — findings: 0

An independent reviewer (Opus) found no defect in the merge. It checked:
- Pass 23's change against Python 3.11 behaviour: json recursion, `os.stat`, int digit limits, annotations, `fcntl`, and git identity in CI.
- That no test from either parent was lost.
- R3's settling, amend base and session choice against `main`'s module.
- Fail-open on every hook and commit path.
- That `_whole` and `_clean` agree field by field.
- That the design, CHANGELOG, manual and backlog match the code.

Noted below its bar, and left as it is: `_settle` reads the 50 newest commits across every ref. If more than 50 newer commits land on other refs between a commit and the session's next hook, the landed commit is missed and its spend reported again. That is the same window R3 had in one checkout, now across refs.

Evidence:
- `scripts/test/test_agent_tokens.py`: 81 passed.
- The full suite on this code, in a clean environment (no `CLAUDECODE`, session id, `AGENTSMITH_DIR` or install on PATH): 2926 passed, 17 skipped, 0 failed.

## Pass 25 — findings: 0

The merge is landed as commits on `main` (1d986d0) instead of a merge commit, which the commit gate refuses: the checklist commit (039cd02) cherry-picked, then this change. The resulting tree is byte-for-byte the tree Passes 18–24 reviewed and the full suite ran on (`git write-tree` matches). Only the staged diff's base moved, so the KG query below is recomputed for it.

## Sign-off

Group 1 · DRY & shared code           [x] checked — one module for both fixes: R3's API (`load`, `entry`, `_settle`), with one reader and writer (`_ledger`), one shape check (`_whole`) and one rebuild (`_clean`) for the ledger and both legacy files
Group 2 · Quality / safety            [x] checked — a hook or commit never fails or hangs on bookkeeping: bounded lock, an unsupported lock used unlocked, `trailers` keeps `Agent:` on any failure while counting, a malformed or oversized entry is left out and read again, whole-file writes by rename at the umask
Group 3 · Architecture / hygiene      [x] checked — one ledger in the git directory the worktrees share; the old file read, never written, with the write's rules applied on read; a later version's ledger left alone; at most 32 sessions, a fortnight unused, unread ones a day
Group 4 · Process                     [x] checked — design first (R3's section and the worktree section, updated for the merge); tests first, each shown failing; both parents' tests kept; CHANGELOG, manual and backlog merged; Passes 18–24 for the merge and 25 for landing it on `main`, the last at 0
Group 5 · Intuitive UI                [x] n/a — no screen; `report` lists every session newest first, and names a later release's ledger
Group 6 · Signal integrity            [x] checked — no measurement is no trailer, never zero; a wrong session's count is refused; a refused commit charges nothing; a commit made in a worktree settles from any checkout (`--all`); claims of redundancy and equivalence were corrected where wrong (Passes 12, 20)
Group 7 · Auth & session integrity    [x] checked — a commit is attributed to the session named by `CLAUDE_CODE_SESSION_ID`, the only session, or none; another user's unreadable transcript is not taken as gone; subagents' tokens are not counted, as the design, manual and backlog say
Group 8 · Security engineering        [x] checked — counts only, no transcript text copied; a parsed ledger cannot carry depth or unknown values into the write; git called with argv lists
Group 9 · Regulation & compliance     [x] n/a — no data, evidence or model-governance path changes
Group 10 · Code optimisation          [x] checked — each read is the transcript's new bytes; the lock is held for that read, one bounded `git log` and one rename

Tests added: `scripts/test/test_agent_tokens.py` — R3's tests kept, and this branch's ported onto R3's API. Added during the merge:
- settling a worktree's commit from the main checkout;
- the fortnight rule, including for legacy sessions;
- an unread legacy session;
- malformed `pending`, counts too large, and `seen` too large;
- another user's unreadable transcript;
- a ledger too deep to read;
- the entry rebuilt at every depth;
- counts no response has;
- any failure while counting keeping `Agent:`.

Mutation-checked: yes, by hand. Forty-six mutants, all killed (Pass 22), covering R3's five and this branch's; the runner is at the session scratchpad.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` (regenerated; `verify_system.py --check-kg-fresh` passes).
Gates run:
- the full suite, in a clean environment (2926 passed, 17 skipped);
- `ruff check .`;
- `scripts/check_bare_except.py`;
- `verify_system.py --check-kg-fresh`.

Python 3.11, the gated CI interpreter, is not installed here; CI is that check. mypy's scope is `agentsmith/`, which this change does not touch.

Levers reviewed: `failure-is-not-a-result`, `implemented-not-invoked`, `test-that-cannot-fail`, `records-name-the-right-actor`, `lock-what-you-decide-on`, `prove-it-fails-first`, `bounded-by-default`, `out-of-order-and-repeated`, `docs-match-behaviour`.

KG query: kg:0553bf4e1af4
