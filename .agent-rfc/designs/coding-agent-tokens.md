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

**Measure, from what the agent already writes.** Claude Code writes every response's usage to the session transcript. Its hook payloads name that transcript (`transcript_path`). The session-start and stop hooks record it in `<git dir>/agentsmith/agent-tokens.json`. `scripts/agent_tokens.py` reads only the bytes added since its last read, and counts each response once by its message id, because one response spans several transcript lines. Only Claude Code is read: the other agents' payloads are unconfirmed (gap 11), so they are left out and the documentation says so.

**Write it on the commit.** After the gate allows a commit, the commit hook asks `process-gate agent-trailers` to add:

- `Agent: claude-code`, when the commit is made from Claude Code's shell (`CLAUDECODE` is set). Owner's decision on gap 6.
- `Agent-Tokens:`, the output, new input, cache-read and cache-write tokens the session spent since its previous commit.

The step can never block a commit: any failure adds nothing. A commit with no trailer means "not recorded", never "written by hand".

**Warn when a session grows.** When the context a turn re-reads passes 150,000 tokens, the stop hook tells the person, once per further 50,000 (a Claude Code `systemMessage`, never a block): commit, and start a fresh session for the next slice. The threshold is `AGENTSMITH_CONTEXT_NOTE_TOKENS`.

**Inject less, under a budget.** A test holds each rendered rule file, the session-start message and the stop hook's message to a token budget, estimated as characters divided by four. The rule files gain a short "token discipline" block, rendered into all six from `records.token_discipline`. It covers reading the impact list rather than the tree, searching before reading, reading slices of large files, not printing large outputs, and one slice per session.

## Pillars

- P1 applies — the paper's token goal and gap 6 are the requirement; `.agent-rfc/designs/coding-agent-tokens.md` is the plan.
- P2 applies — `scripts/agent_tokens.py` is one module beside `scripts/gate_tracing.py`; no new dependency.
- P3 applies — `scripts/gate_tracing.py` already spans each hook; the token totals add no new span.
- P4 applies — `scripts/test/test_agent_tokens.py` covers counting, de-duplication, incremental reads, the trailers and the note; `scripts/test/test_context_budget.py` holds the budgets; mutation-checked by hand.
- P7 applies — `scripts/gate_models.py` gains `token_discipline` beside `design_start`.
- P8 n/a — the telemetry wire is untouched.
- P9 n/a — no orchestration.
- P10 applies — `scripts/agent_tokens.py` is the measure this pillar lacked on the build side.
- P11 applies — `scripts/agent_tokens.py` reads the transcript as data, line by line, and skips what does not parse.
- P12 applies — `scripts/agent_tokens.py` keeps counts only; no prompt or response text leaves the transcript.
- P13 applies — `.githooks/commit-msg` adds trailers only after the gate allows, and never fails the commit.
- P14 n/a — no fixtures.
- P15 applies — `scripts/test/test_agent_tokens.py` holds that no transcript or an unknown agent writes nothing, never a zero.
- P16 applies — `CHANGELOG.md` names the trailers; removing the hook line stops them, and the ledger is local and disposable.

## Deviations

none

## Dependencies

none

## Levers

- `failure-is-not-a-result` — no measurement is no trailer, never zero tokens.
- `implemented-not-invoked` — a test drives the real hook path, not only the module.
- `test-that-cannot-fail` — hand mutants.
