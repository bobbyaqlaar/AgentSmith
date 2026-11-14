---
status: active
scope:
  - agentsmith/token_limits.py
  - agentsmith/llm_gateway.py
  - agentsmith/test/test_token_limits.py
  - scripts/test/test_trajectory_evals.py
---
# Every role's caps are read when the gateway starts, and the token guards have tests that can fail

From the 4.1.0 review's second pass (the owner's local `review-4.1.0-pass2.md`): P2-R2 and P2-R3, two minors the
owner asked for before the release. Follows `.agent-rfc/designs/run-token-limits.md` and
`.agent-rfc/designs/stream-release-and-lockout.md`.

## Problem

- **P2-R2.** `max_output_tokens` and `max_input_tokens` are read only when a call reaches a role. An unreadable cap on
  a fallback tier (`"512k"`) is therefore found only when the primary provider fails: the failover raises
  `LimitUnreadableError`, and the app is down at the moment the degrade ladder exists for.
- **P2-R3.** Four guards from the first review's fixes had no test that failed without them. Two (a stream refused by
  the compliance guard or the run budget gives back its reservations) gained tests with P2-R1. Two remain in
  `scripts/evals_port.py`: a boolean is not a token count, and a span saying `llm.usage.reported: false` is unmeasured
  even when it carries counts.

## Approach

- **P2-R2.** `token_limits.check_declared_caps(models)` reads both caps of every role and raises `LimitUnreadableError`
  naming the role and the setting. `LLMGateway.__init__` calls it after loading the registry, so a model file with an
  unreadable cap stops the gateway at start, on every tier. The per-call reads stay: they are what applies the caps, and
  they still refuse a value set on a registry changed after start.
- **P2-R3.** Two trace cases in `scripts/test/test_trajectory_evals.py`: a model span whose token attributes are booleans,
  and a span that reports `llm.usage.reported: false` beside zero counts. Each is `not_gradable` under `max_tokens`.

## Pillars

- P1 applies — P2-R2 and P2-R3 are the requirement; `.agent-rfc/designs/caps-at-load-and-guard-tests.md` is the plan.
- P2 applies — one function in `agentsmith/token_limits.py`, one call in `agentsmith/llm_gateway.py`; no dependency.
- P3 applies — `scripts/test/test_trajectory_evals.py`: a trajectory budget is graded only on usage that was measured.
- P4 applies — `agentsmith/test/test_token_limits.py` and `scripts/test/test_trajectory_evals.py`; hand mutants after.
- P7 applies — `agentsmith/llm_gateway.py`: a model file is checked whole when the gateway starts.
- P8 n/a — no telemetry is emitted differently.
- P9 n/a — no orchestration.
- P10 applies — `agentsmith/token_limits.py`: the fallback ladder is never broken by its own configuration.
- P11 n/a — no untrusted content.
- P12 n/a — no secrets.
- P13 applies — `scripts/test/test_trajectory_evals.py` and `agentsmith/test/test_token_limits.py`: each guard is seen failing.
- P14 n/a — no fixture or baseline.
- P15 applies — `scripts/evals_port.py` behaviour pinned: "reported false" and "a boolean" are not counts.
- P16 applies — `CHANGELOG.md`: an unreadable cap anywhere in the model file now stops the gateway at start.

## Deviations

none

## Dependencies

none

## Levers

- `when-the-fallback-fails` — the fallback tier's caps are read before the fallback is needed (P2-R2).
- `test-that-pins-a-defect` — the test that pinned the raise at failover stays, as a second line, beside the load-time one.
- `guards-must-be-able-to-fail` — each guard has a test that fails without it (P2-R3).
- `test-that-cannot-fail` — hand mutants.
