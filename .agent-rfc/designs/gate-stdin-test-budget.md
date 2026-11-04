---
status: active
scope:
  - scripts/test/test_process_gate.py
  - .agent-rfc/fixtures/knowledge_graph.json
---
# A contract decision's test bounds the wait, not the gate's work

## Problem

`test_a_contract_decision_answers_when_nobody_closes_stdin[ci --decision]` failed PR #78 with "answered in 7.0s" against a limit of
7.0s: two seconds for the read and five of slack. `ci --decision` reads the range's commits after the read, so that number
grows with the repository and the runner's load. The test's claim is that the gate does not wait for an EOF, and it proves that through
the `hold` of `_gate_with_open_stdin`, which raises if the gate has not answered at all.

## Approach

- **Remove the elapsed assertion from the contract test.** `hold`, twenty seconds, remains the bound, and the message that a wait
  expired remains asserted.
- **Keep it on `stop`:** that path does no range work, so its time measures the read.
- **The curated mutation "the payload read waits for an EOF the caller may never send" must still be caught,** through `hold`.

## Pillars

- P1 applies — `.agent-rfc/designs/gate-stdin-test-budget.md` records the failed check and what the test claims.
- P2 n/a — one assertion removed; no dependency.
- P3 n/a — a test; no traced path changes.
- P4 applies — `scripts/test/test_process_gate.py` keeps its bound through `hold`, and the `hook_payload` suite proves it can still fail.
- P7 n/a — no stack-specific rule applies.
- P8 n/a — no telemetry.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 n/a — reads nothing untrusted.
- P12 n/a — no secret involved.
- P13 applies — `scripts/process_gate.py` does not change, so no gate behaviour moves; only a flaky check on it does.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `scripts/test/test_process_gate.py` no longer turns a slow runner into a claim about the read.
- P16 n/a — nothing to recover; a test.

## Deviations

none

## Dependencies

none

## Levers

- `guards-must-be-able-to-fail` — the guard still fails on the defect, and no longer on a busy machine.
- `environment-parity` — a laptop's timing passed where a loaded runner did not.
