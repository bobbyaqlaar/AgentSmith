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

## Pass 3 — findings: 0

- `scripts/test/test_agent_tokens.py`: counting once per response, incremental reads that leave a half-written line for next time, the context size, other agents and missing transcripts recording nothing, a new session starting from zero, the note once per step, trailers only from Claude Code's shell and only what was spent since the session's previous commit, placement in the message, and a real commit through an adopted tenant's own hooks, with and without an agent.
- `scripts/test/test_context_budget.py`: every rule file a tenant gets, for three stacks, under 3,000 tokens (estimated); the token-discipline block in all five instruction files; the session-start message under 1,200 tokens. The largest rule file is about 2,600.
- Ten hand mutants, all caught.
- The related suites (process gate, rules contract, sync, gate table, repository tree, environment variables): 367 passed; ruff and mypy clean.

Left out on purpose, and documented: Cursor, Codex, Gemini CLI, Copilot and Antigravity get no trailer until their hook payloads are confirmed (gap 11). Showing the tokens in the portal comes with the run-side token work.

## Sign-off

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

KG query: kg:19c5ba4be06b
