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

## Sign-off (after the 4.1.0 review)

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

KG query: kg:a82981f44083
