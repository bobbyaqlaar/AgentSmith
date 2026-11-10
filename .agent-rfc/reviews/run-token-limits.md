# Review: run-token-limits

The run half of the token goal, after the owner's instruction of 2026-11-10 to do the token items first. This record covers the caps per role and the limits per run. The trajectory `max_tokens` rule and the portal's tokens column build on #112 and follow once it merges, recorded here as further passes.

## Pass 1 — findings: 2

Against `docs/review-levers.md`.

1. **Three hand-built test gateways had no budget backend.** The real constructor always opens one, and the run limits read it, so 11 existing tests failed with `AttributeError`. Fixed in the shared fixture and the two files that build their own, not by making the gateway tolerate a missing backend.
2. **The streaming path cannot settle a run budget,** because a stream reports no usage. Decided, not fixed: the reservation stands as the charge, the same rule the money cap applies to streams, and the design says so.

## Pass 2 — findings: 0

- `agentsmith/test/test_token_limits.py`: an undeclared limit changes nothing; the role caps the answer; an oversized prompt is refused before it is sent; a run stops at its budget, settles to the real count, and keeps runs apart; a failed call is released; unreported usage keeps the reservation; the tool-call limit per run; the environment variable, and a malformed one.
- Nine hand mutants, all caught, including the gateway skipping the settle or the release.
- The 22 gateway, streaming, guard, moderation, tool and compliance suites: 250 passed; ruff and mypy clean.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one module for the arithmetic; the gateway and registry call it; the run counters reuse the spend cap's atomic backend.
Group 2 · Quality / safety — [x] checked — every limit refuses before anything is sent, with an error that names the setting.
Group 3 · Architecture / hygiene — [x] checked — additive; `ToolRegistry.invoke` gains an optional keyword.
Group 4 · Process — [x] checked — design first; manual, environment-variable table and CHANGELOG updated.
Group 5 · Intuitive UI — [x] n/a — no screen in this part.
Group 6 · Signal integrity — [x] checked — unreported usage is charged as the estimate, never as zero.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: `agentsmith/test/test_token_limits.py`.
Mutation-checked: yes, by hand; nine mutants, all killed.
Fixtures re-pinned: `agentsmith/test/_gateway_fixtures.py` and two hand-built test gateways gain a budget backend; `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; ruff; mypy; the documentation checks; the process gate against the commit.

Levers reviewed: `failure-is-not-a-result`, `test-that-cannot-fail`, `declared-vs-enforced`.

KG query: kg:f4ac4c02e475
