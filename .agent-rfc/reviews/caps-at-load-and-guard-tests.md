# Review: caps-at-load-and-guard-tests

P2-R2's fix has tests that fail without it: `test_an_unreadable_cap_on_any_tier_stops_the_gateway_at_start` (a real
`LLMGateway` built over a registry whose fallback tier declares `"512k"`) and `test_every_declared_cap_is_read`, in
`agentsmith/test/test_token_limits.py`. P2-R3 adds tests, not code: two cases in `scripts/test/test_trajectory_evals.py`
pass on the existing guards, and the point is that they fail without them (below).

## Pass 1 — findings: 0

Against `docs/review-levers.md`, by hand mutants (six).

- The load-time check not called; the input cap not checked: both killed.
- The four guards the second-pass review named under P2-R3, with the mutants it reported surviving: the stream's release
  on a compliance refusal (M1), the money in `release()` (M5), booleans counted as tokens (M8), `llm.usage.reported:
  false` ignored (M9). All four killed now: M1 and M5 by the stream tests added with P2-R1, M8 and M9 by the two new
  trace cases.
- `agentsmith/test`: 901 passed, 18 skipped (every gateway built in a test now goes through the check). ruff and mypy
  1.14.1: clean.
- Siblings: `LLMGateway.__init__` is the one place the gateway's registry is loaded, so the sidecar
  (`agentsmith runtime serve`) and every app get the check. `scripts/_shared.py` loads the registry for the eval path,
  which applies no token caps. The per-call reads stay, and `test_an_unreadable_cap_on_a_fallback_tier_is_named_not_wrapped`
  keeps holding them, for a registry changed after start.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one `_positive` for both reads; one `check_declared_caps`.
Group 2 · Quality / safety — [x] checked — a broken model file stops the gateway at start, not at failover.
Group 3 · Architecture / hygiene — [x] checked — one function and one call.
Group 4 · Process — [x] checked — design first; CHANGELOG and backlog updated.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — each token guard is seen failing; an unmeasured count stays `not_gradable`.
Group 7 · Auth & session integrity — [x] n/a — no auth code.

Tests added: four in `agentsmith/test/test_token_limits.py`; two in `scripts/test/test_trajectory_evals.py`.
Mutation-checked: yes, by hand; six mutants, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; ruff; mypy; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `when-the-fallback-fails`, `test-that-pins-a-defect`, `guards-must-be-able-to-fail`, `test-that-cannot-fail`

KG query: kg:7cce6444b5c1
