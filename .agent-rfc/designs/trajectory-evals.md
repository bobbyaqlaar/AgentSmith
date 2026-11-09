---
status: active
scope:
  - scripts/gate_models.py
  - scripts/evals_port.py
  - agentsmith/cli.py
  - .githooks/process-gate
  - contract/evals/**
  - contract/rules/v1/extends.schema.json
  - scripts/test/test_trajectory_evals.py
  - scripts/test/test_evals_contract.py
---
# Trajectory evals: grading the path, not only the answer

Gap 9 of `docs/PRODUCT_BACKLOG.md`.

## Problem

Every suite judges an output. Agents fail in the path: the wrong tool, the right tools in the wrong order, a tool they must never touch, a loop of calls. A run can end with a good answer reached the wrong way, and no suite sees it.

## Approach

A sixth suite in the evals contract, `trajectory`, at `.agent-rfc/fixtures/trajectory_evals.json`. A case names its tool calls one of two ways: `tools`, the names in order as a run made them, or `trace`, an OTLP/JSON export of a real run inside the repository, from which the calls are read. A call is a span carrying `gen_ai.tool.name` or `agent.tool.name`, ordered by start time.

A case states at least one rule in `expect`:

- `in_order`: these tools are called in this order, others may come between;
- `must_call`: each of these is called;
- `never`: none of these is called;
- `max_calls`: no more than this many calls.

**Graded without a model.** The verdict is computed from the calls, so it is the same on every run, needs no key, and gives a real answer on a compliance profile with no judge. The bar is a floor on the share of cases that keep their rules: by default 1.0, every case, declared lower in `extends.evals.trajectory` like any other suite.

**A trace that cannot be read is not a result.** A path outside the repository, a file that is not OTLP, or one with no spans makes the suite `not_gradable` and names the case, never a pass or a fail.

**Not in this slice:** "approved before". Human decisions are not on spans today, so a rule about them could only be checked against a list the tenant types. Recorded on the backlog, as is a CI job template for the suite.

## Pillars

- P1 applies — `docs/PRODUCT_BACKLOG.md` gap 9 is the requirement; `.agent-rfc/designs/trajectory-evals.md` is the plan.
- P2 applies — `scripts/evals_port.py` grades it beside the suites it already answers; no new dependency.
- P3 applies — `agentsmith/tracing.py` already writes `gen_ai.tool.name` and `agent.tool.name` on tool spans; this reads them back.
- P4 applies — `scripts/test/test_trajectory_evals.py` covers each rule, both sources and each way a trace fails; `contract/evals/v1/cases.json` gains a passing and a failing case; mutation-checked by hand.
- P7 applies — `scripts/gate_models.py` `TrajectoryCase` is the dataset's model, and `contract/evals/v1/dataset.trajectory.schema.json` is generated from it.
- P8 applies — `contract/evals/v1/protocol.md` gains a suite; existing suites, requests and scorecards are unchanged.
- P9 n/a — no orchestration change.
- P10 n/a — no model call: graded deterministically.
- P11 applies — `scripts/evals_port.py` refuses a `trace` path outside the repository and parses the file as data.
- P12 n/a — no secrets involved.
- P13 n/a — no gate changes.
- P14 applies — `scripts/test/test_evals_contract.py` holds every published schema to its model.
- P15 applies — `scripts/test/test_trajectory_evals.py` holds that an unreadable trace is `not_gradable`, never a pass.
- P16 applies — `CHANGELOG.md` names the suite; additive, so reverting is one commit.

## Deviations

none

## Dependencies

none

## Levers

- `failure-is-not-a-result` — an unreadable trace is not graded.
- `test-that-cannot-fail` — hand mutants of each rule.
- `implemented-not-invoked` — graded from the same tool spans the runtime writes.
