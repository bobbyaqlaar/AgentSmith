---
status: active
scope:
  - scripts/gate_pillars.py
  - scripts/gate_history.py
  - scripts/gate_shell.py
  - scripts/process_gate.py
  - scripts/test/test_declaration_ratchet.py
  - scripts/test/test_compliance_port.py
  - agentsmith/test/test_compliance_runtime.py
---
# An agent may edit the declaration, a weakening needs the owner's approval, and every change is logged

From the 4.1.0 review's second pass (the owner's local `review-4.1.0-pass2.md`): P2-R12 and P2-R16, two minors the
owner asked for before the release. The owner's decision on P2-R12 (2026-11-13): agents may edit
`.agenticframework/compliance.json`; a change that weakens a duty needs an approval; and the action is logged in the
audit log. Follows `.agent-rfc/designs/compliance-profile-holds.md` (R24) and
`.agent-rfc/designs/decision-names-its-request.md`.

## Problem

- **P2-R12.** The declaration was refused to an agent's shell (`scripts/gate_shell.py`) and open to its edit tool, so
  the refusal protected nothing, and nothing checked what an edit did: dropping `ar` from `languages`, widening
  `boundary.hosts`, lengthening a session or shortening retention all committed without a word.
- **P2-R16.** No test could tell that a purge and its record are one transaction: the fake connection is shared by
  `record()`, and the refusal test fails at the record key, before the change, in both versions.

## Approach

- **P2-R12.**
  - The shell refusal goes: agents may edit the declaration with any tool.
  - `gate_pillars.declaration_weakenings(old, new)` lists what a change weakens, field by field: the profile changed or
    the file deleted; `app_owner` changed; a class no longer classified; a host added to `boundary.hosts`; a
    `boundary.sinks` entry moved; a session made longer; a retention made shorter or removed; a continuity target made
    looser or its backup host moved; a language removed; an agent removed or its accountable owner changed;
    `user_calls_per_minute` raised or removed. Replacing a `REPLACE_ME` placeholder is filling the declaration, never a
    weakening. Strengthening needs nothing.
  - `gate_pillars.declaration_transition(...)` turns that into the commit's verdict: a weakening needs an
    `Approval: A-xxxxxxxx` trailer naming an approval the owner recorded at a terminal (`agentsmith approve`), the same
    record the `compliance` config ratchet reads. It runs in `check_change` for every commit that touches the file,
    gated or not, in every mode, locally and in CI.
  - The audit log: the commit gate appends one entry to `.agent-history.log` (`gate_history.record_event`) for each
    commit that changes the declaration: `compliance_declaration_changed` (INFO), `compliance_declaration_weakened`
    with the approval id (MAJOR, resolved by that approval), or `compliance_declaration_weakening_refused` (MAJOR,
    unresolved, so the next session start surfaces it). Each names the fields. CI does not write the local log; it
    refuses the same commits.
- **P2-R16.** A database test runs a purge in a schema of its own, with a trigger that refuses the
  `retention_purge` record, and asserts the runs are still there; the same for a stop. It fails if the record is
  written in a transaction of its own after the change.

## Pillars

- P1 applies — P2-R12 (with the owner's decision) and P2-R16 are the requirement; `.agent-rfc/designs/declaration-ratchet-and-atomic-test.md` is the plan.
- P2 applies — `scripts/gate_pillars.py` gains the rule beside `compliance_transition_problems`; `scripts/gate_history.py` gains `record_event`; no dependency.
- P3 applies — `scripts/gate_history.py`: every change to the declaration is an entry in `.agent-history.log`.
- P4 applies — `scripts/test/test_declaration_ratchet.py` holds each weakening and each non-weakening; `agentsmith/test/test_compliance_runtime.py` the transaction; hand mutants after.
- P7 n/a — no model.
- P8 applies — `scripts/process_gate.py`: the commit gate's existing span records the decision; the log records the change.
- P9 n/a — no orchestration.
- P10 n/a — no routing.
- P11 n/a — no untrusted content.
- P12 n/a — no secrets.
- P13 applies — `scripts/process_gate.py`: the declaration only strengthens without the owner's recorded approval, as the profile's config already does.
- P14 n/a — no fixture or baseline.
- P15 applies — `scripts/gate_pillars.py`: filling a placeholder and weakening a duty are told apart.
- P16 applies — `CHANGELOG.md` and the manual say how to make an approved weakening: `agentsmith approve`, then the `Approval:` trailer.

## Deviations

none

## Dependencies

none

## Levers

- `consistent-auth-gates` — one rule for every tool an agent edits with (P2-R12).
- `declared-vs-enforced` — the declaration's duties hold unless the owner says otherwise.
- `failure-mode-visibility` — a refused weakening surfaces at the next session start.
- `test-that-cannot-fail` — the purge test fails with the record outside the transaction (P2-R16); hand mutants.
