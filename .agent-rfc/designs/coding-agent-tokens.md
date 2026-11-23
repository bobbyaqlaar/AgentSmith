---
status: active
scope:
  - scripts/agent_tokens.py
  - scripts/process_gate.py
  - scripts/generate-ide-config.py
  - scripts/gate_models.py
  - templates/agent-rules.yaml
  - templates/governance.json
  - .githooks/commit-msg
  - scripts/test/test_agent_tokens.py
  - scripts/test/test_context_budget.py
---
# Coding agents spend fewer tokens, and every commit says what it cost

The build half of the token goal (the paper's "Using fewer tokens"), and gap 6 (which agent wrote a change), decided together because both are written on the commit.

## Problem

A coding agent's cost is dominated by its own context. This repository's longest session re-read about 4.3 billion cached tokens over its life against 8.4 million output tokens, because each turn re-reads everything before it. AgentSmith adds to that context and measures none of it. Its rule files are read at the start of every session, its session-start message lists the files a change touches, and its stop hook repeats itself. Nothing records which agent made a commit or what it cost.

## Approach

**Measure, from what the agent already writes.** Claude Code writes every response's usage to the session transcript. Its hook payloads name that transcript (`transcript_path`). The session-start and stop hooks record it in `<common git dir>/agentsmith/agent-sessions.json`, one entry per session (see "Worktrees and concurrent sessions"). `scripts/agent_tokens.py` reads only the bytes added since its last read, and counts each response once by its message id, because one response spans several transcript lines. Only Claude Code is read: the other agents' payloads are unconfirmed (gap 11), so they are left out and the documentation says so.

**Write it on the commit.** After the gate allows a commit, the commit hook asks `process-gate agent-trailers` to add:

- `Agent: claude-code`, when the commit is made from Claude Code's shell (`CLAUDECODE` is set). Owner's decision on gap 6.
- `Agent-Tokens:`, the output, new input, cache-read and cache-write tokens the session spent since its previous commit.

The step can never block a commit: any failure adds nothing. A commit with no trailer means "not recorded", never "written by hand".

**Warn when a session grows.** When the context a turn re-reads passes 150,000 tokens, the stop hook tells the person, once per further 50,000 (a Claude Code `systemMessage`, never a block): commit, and start a fresh session for the next slice. The threshold is `AGENTSMITH_CONTEXT_NOTE_TOKENS`.

**Inject less, under a budget.** A test holds each rendered rule file, the session-start message and the stop hook's message to a token budget, estimated as characters divided by four. The rule files gain a short "token discipline" block, rendered into all six from `records.token_discipline`. It covers reading the impact list rather than the tree, searching before reading, reading slices of large files, not printing large outputs, and one slice per session.

## After the 4.1.0 review (2026-11-11)

**R3 — two sessions in one checkout corrupted the trailer**, and so did an aborted commit and `--amend`. The ledger held one session and reset itself whenever another session's hook ran, and `commit-msg` moved the baseline before the commit existed. Now:

- The ledger keeps one entry per transcript (`{"sessions": {…}}`; an old one-entry ledger is read as one session). Sessions unseen for 14 days are dropped, at most 32 kept.
- A commit is charged to the session whose shell made it, by `CLAUDE_CODE_SESSION_ID` against the transcript's session id. With several sessions and no id, the commit carries `Agent:` only: no measurement, no trailer.
- `commit-msg` records a *pending* baseline with the exact `Agent-Tokens:` line it wrote. The next hook in that session moves the baseline only if a recent commit carries that line; a commit refused after the trailer step charges nothing. No post-commit hook is added: `.githooks` has none, and adding one would start chaining tenants' post-commit hooks, one of which pushes.
- `--amend` reaches the trailer step (the hook already detected it for the gate). When the commit replaced is this session's last, the trailer counts from the baseline before it.

**R7** is wording: the backlog says `Agent:` on each commit made from Claude Code.

## Worktrees and concurrent sessions (2026-11-22)

**Problem.** The ledger lived in each checkout's own git directory (R3, above, made it hold one entry per session, on `main` while this was built on a branch without it). A linked worktree (`git worktree add`) has a git directory of its own, so a session started in the main checkout recorded its transcript under `.git/agentsmith/`, and its commits from the worktree read `.git/worktrees/<name>/agentsmith/`, found nothing, and carried `Agent:` without `Agent-Tokens:` (`feat/ruff-s-rules` 85735d2 and 0298743). The tokens stayed in the main checkout's ledger, so its next commit would have claimed them. R3's settling had the same blind spot: the hook that moves the baseline looked for the landed commit with `git log` in its own checkout, and a commit made in a worktree lands on another branch, so the baseline would never have moved and every later commit would have repeated the spend.

**Approach.**

- The ledger moves to the git directory every worktree shares (`git rev-parse --git-common-dir`), so a session's hooks and its commits read one file wherever each runs.
- It is a new file, `agentsmith/agent-sessions.json`, holding one entry per session keyed by transcript path: `{"version": 2, "sessions": {<transcript>: entry}}`. An entry is R3's (with its pending baseline, last commit and the baseline before it) plus `seen`, when a hook last read it. A hook updates only its own entry; the stop hook's context note reads only its own.
- R3's settling looks for the landed commit in every ref and every worktree's HEAD (`git log --all`), because the hook that settles it may run in another worktree than the commit was made in.
- The old `agentsmith/agent-tokens.json` is read, never written, in either shape (one session, or R3's sessions). Code from before this change still writes it, from any checkout on an older branch, and giving the new ledger the same name let that code replace every other session with its one. A session the old file holds (in the shared git directory, or in a linked worktree's own) and the new one lacks is taken from it, so the main checkout keeps its baseline and a worktree's earlier session is not lost.
- The commit picks its session by `CLAUDE_CODE_SESSION_ID`, which Claude Code sets in its shell and which names the transcript (`<id>.jsonl`; observed in Claude Code 2.1.326, not documented). Set but matching no entry: no `Agent-Tokens:`, because the session committing is not one this repository recorded. Unset (an older Claude Code): the one recorded session, and none when there are several. Entries last until their transcript is deleted or they go a fortnight unused, so on such a version a repository that has recorded two sessions in that time gets no `Agent-Tokens:`. No measurement is no trailer; a wrong session's count is worse than none.
- Writes go to a temporary file renamed into place, under an exclusive `fcntl` lock taken with a 10-second limit. A filesystem without locks is used unlocked, as before; a lock still held after 10 seconds skips the bookkeeping (no trailer), so a hook or commit never hangs. A malformed `seen` reads as 0.
- Entries whose transcript is gone are dropped once they have been read, including the old ledger's, R3's fortnight rule drops one unused that long, and at most 32 are kept, newest `seen` first. An entry whose last use is unknown (a legacy entry, a malformed `seen`) is kept while its transcript is there, not forgotten as if it were ancient. Claude Code writes a new session's transcript just after its SessionStart hook, so an entry never read is kept for a day though its transcript is not there yet; dropping it lost the first turn's commits their trailer, and with no session id gave them another session's spend. The ledger keeps the lock file's mode (the umask), so a repository shared between users stays readable to each.
- A ledger that cannot be written costs the `Agent-Tokens:` line, never `Agent:`; one a later version wrote is neither read nor rewritten, and `report` says so.

**What still miscounts, and says so.** An entry rebuilt mid-session (ledger deleted, the session pruned, its transcript invisible to the hook that wrote last, an entry of the wrong shape, or an offset past the transcript's end) is read from the transcript's start, and its next commit reports the whole session as "this session so far: its first commit"; where a legacy ledger still holds the session, it is rebuilt from that ledger's older baseline instead, and its next commit repeats what was reported since. Hooks and commits both mark a session as used, so the cap drops only sessions idle while 32 others were used. During the window when one session's hooks run older code and its commits run this code (or the reverse), the two keep separate baselines (and older code settles only in its own checkout), so a commit can repeat what an older-code commit already reported. Subagents are not counted. A subagent's shell carries its parent's `CLAUDE_CODE_SESSION_ID`, so its commit carries the parent's spend since the parent's last commit; its own usage is in `<id>/subagents/agent-*.jsonl`, which `read_new` does not read. That was true before this change, and the backlog holds it. Not confirmed: what `/clear` and `--resume` do to the session id.

## Pillars

- P1 applies — the paper's token goal and gap 6 are the requirement; `.agent-rfc/designs/coding-agent-tokens.md` is the plan.
- P2 applies — `scripts/agent_tokens.py` is one module beside `scripts/gate_tracing.py`; no new dependency.
- P3 applies — `scripts/gate_tracing.py` already spans each hook; the token totals add no new span.
- P4 applies — `scripts/test/test_agent_tokens.py` covers counting, de-duplication, incremental reads, the trailers and the note, a real commit from a linked worktree, two sessions sharing one repository, a legacy ledger written by older code, a malformed entry, a held or unsupported lock, and the stop hook's note scoped to its session; `scripts/test/test_context_budget.py` holds the budgets; mutation-checked by hand.
- P7 applies — `scripts/gate_models.py` gains `token_discipline` beside `design_start`.
- P8 n/a — the telemetry wire is untouched.
- P9 n/a — no orchestration.
- P10 applies — `scripts/agent_tokens.py` is the measure this pillar lacked on the build side.
- P11 applies — `scripts/agent_tokens.py` reads the transcript as data, line by line, and skips what does not parse.
- P12 applies — `scripts/agent_tokens.py` keeps counts only; no prompt or response text leaves the transcript.
- P13 applies — `.githooks/commit-msg` adds trailers only after the gate allows, and never fails the commit; the lock waits at most 10 seconds and then skips the bookkeeping, and a filesystem without locks is used unlocked.
- P14 n/a — no fixtures.
- P15 applies — `scripts/test/test_agent_tokens.py` holds that no transcript or an unknown agent writes nothing, never a zero, and that two sessions with no way to tell which committed write no count (R3); a session id matching no entry writes no `Agent-Tokens:`.
- P16 applies — `CHANGELOG.md` names the trailers; removing the hook line stops them, and the ledger is local and disposable: deleting it costs each live session one commit that reports from its transcript's start.

## Deviations

none

## Dependencies

none

## Levers

- `failure-is-not-a-result` — no measurement is no trailer, never zero tokens.
- `implemented-not-invoked` — a test drives the real hook path, not only the module.
- `test-that-cannot-fail` — hand mutants.
- `out-of-order-and-repeated` — two sessions, an aborted commit and an amend each keep their own count (R3).
- `docs-match-behaviour` — the backlog says which commits carry `Agent:` (R7).
- `records-name-the-right-actor` — a commit carries its own session's spend, or none.
- `lock-what-you-decide-on` — the ledger is read and rewritten under one lock.
- `prove-it-fails-first` — the worktree and two-session tests fail on the old ledger before the fix.
- `bounded-by-default` — at most 32 sessions, gone transcripts dropped.
