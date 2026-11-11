---
status: active
scope:
  - scripts/security/runners/agent_workflow.py
  - scripts/test/test_agent_workflow_injection.py
  - contract/security/v1/cases.json
  - scripts/test/test_security_contract.py
  - agentsmith/workflows/base_workflow.py
  - agentsmith/test/test_compliance_runtime.py
  - workflow-templates/agentsmith-supply-chain.yml
  - scripts/test/test_compliance_checks.py
  - scripts/compliance_port.py
  - scripts/test/test_compliance_port.py
  - .github/workflows/self-test.yml
  - .github/workflows/release.yml
---
# The four majors of the 4.1.0 review's second pass

From `.git/agentsmith/review-4.1.0-pass2.md` (local to the owner's checkout): P2-R5, P2-R13, P2-R7, P2-R22. The
owner asked for these four before the 4.1.0 release; the minors follow the release. Follows
`.agent-rfc/designs/ciagent-guard-holds.md`, `.agent-rfc/designs/compliance-profile-holds.md` and
`.agent-rfc/designs/portal-compliance-holds.md`.

## Problem

- **P2-R5.** SEC-CIAGENT-001 searches a condition for the field's `author_association`, a trusted role word and no
  `||` or `!`. Written another way, a guard that lets outsiders through still passes: `contains(fromJSON(roles), …)
  == false`; an allow-list that includes `CONTRIBUTOR` (anyone with one merged commit); a comparison with `'NONE'`
  beside an unrelated role word. Meanwhile the common `… == 'OWNER' && !github.event.issue.pull_request` is refused.
- **P2-R13.** On the Temporal path the workflow waits for a digest of the Python object it holds; the pending record,
  the portal and the reviewer's decision carry a digest of the input after Temporal serialized it for the activity. For
  a dataclass, or a date, the two differ, every decision is ignored, and the gate times out beside a decision the
  portal accepted.
- **P2-R7.** For an app with only `pyproject.toml`, the supply-chain template's SBOM is `cyclonedx-py environment` run
  under `pipx`: the tool's own packages, not the app's.
- **P2-R22.** The eight `release:` obligations are `layer: provider`. A tenant sees them as `not_applicable`
  ("AgentSmith's own release evidence"), AgentSmith itself has no profile, and no workflow evaluates them, so that
  evidence is never produced and `OB-AUDIT-COVERAGE`'s failure is visible nowhere.

## Approach

- **P2-R5.** Read the guard as terms joined by `&&`. It restricts when it has no `||`, no negated group (`!(`), and at
  least one term that is exactly a positive author test for the field's own author:
  `github.event.<x>.author_association == '<role>'` (either side), or
  `contains(fromJSON('<JSON list>'), github.event.<x>.author_association)`, every role in OWNER, MEMBER,
  COLLABORATOR, compared without case as GitHub does. In a conjunction every term must hold, so one such term is enough,
  and the other terms (`!github.event.issue.pull_request`, a mention test) may be anything: they can only narrow. Three
  contract cases for the three bypasses; the accepted `&& !…pull_request` shape becomes a passing test.
- **P2-R13.** One digest, computed once. `compliance_record_activity` returns `input_sha256` with the record id for a
  `hitl_pending` record, and the workflow waits for that value. `_input_digest` and the test that held two functions
  equal on one object go. A pending record that comes back without a digest refuses the gate (fail closed). The test
  fake computes its digest the way the activity sees the input: through Temporal's data converter.
- **P2-R7.** The `pyproject.toml` branch installs the app into its own virtual environment and points
  `cyclonedx-py environment` at that interpreter, so the SBOM names the app's packages. The audit is unchanged
  (`pip-audit .`). A test holds that every `cyclonedx-py environment` in the template names an interpreter.
- **P2-R22.** `scripts/compliance_port.py provider-evidence [--out FILE]` judges the provider rows as AgentSmith's own
  evidence and writes the document. It fails on any failing row except those in `KNOWN_PROVIDER_GAPS`, which today
  holds only `OB-AUDIT-COVERAGE`, by the owner's decision (2026-11-12): named in the code, the document and the
  backlog, never silent. Self-Test runs it and uploads the document; the release workflow runs it and attaches it to
  the release. On a tenant, a provider row reads `not_applicable` with a pointer to that document, and a known-gap row
  reads `pending` with the reason, instead of claiming evidence.

## Pillars

- P1 applies — the four majors in the second-pass review are the requirement; `.agent-rfc/designs/review-pass2-majors.md` is the plan.
- P2 applies — each fix changes its module in place (`scripts/security/runners/agent_workflow.py`,
  `agentsmith/workflows/base_workflow.py`, `workflow-templates/agentsmith-supply-chain.yml`,
  `scripts/compliance_port.py`); no new dependency.
- P3 n/a — no spans or evaluations change.
- P4 applies — a failing test first for each (`scripts/test/test_agent_workflow_injection.py`,
  `agentsmith/test/test_compliance_runtime.py`, `scripts/test/test_compliance_checks.py`,
  `scripts/test/test_compliance_port.py`); hand mutants after.
- P7 n/a — no model changes.
- P8 n/a — no telemetry.
- P9 applies — `agentsmith/workflows/base_workflow.py`: the gate's wait reads the activity's answer, which is how a
  Temporal workflow is meant to learn what an activity computed.
- P10 n/a — no routing.
- P11 applies — `scripts/security/runners/agent_workflow.py` decides when event text an outsider writes may reach an
  agent.
- P12 n/a — no secrets.
- P13 applies — `contract/security/v1/cases.json` holds every security provider to the three bypasses;
  `scripts/compliance_port.py provider-evidence` gates Self-Test and the release on AgentSmith's own evidence; the one
  exception is named in code (`KNOWN_PROVIDER_GAPS`), not a switch.
- P14 applies — `scripts/test/test_security_contract.py` pins the case count (36 to 39).
- P15 applies — `scripts/compliance_port.py`: a tenant's provider row stops reading `not_applicable` for evidence that
  is not produced; a known gap reads `pending` with its reason.
- P16 applies — `CHANGELOG.md` says what newly fails (a guard that only appeared to restrict) and what newly passes;
  a tenant takes the template with `agentsmith sync`.

## Deviations

none

## Dependencies

none

## Levers

- `guards-must-be-able-to-fail` — the guard must contain a term that can only narrow to trusted roles (P2-R5).
- `grep-for-siblings` — `== false` is `!`; a list is a comparison (P2-R5).
- `environment-parity` — one digest, taken where the input has crossed the boundary (P2-R13).
- `test-the-contract` — the SBOM's interpreter, the activity's answer, the provider contract's cases.
- `implemented-not-invoked` — the provider rows are evaluated by a step CI and the release run (P2-R22).
- `aggregates-name-their-scope` — a known gap is listed by id and reason, not folded into a pass.
- `test-that-cannot-fail` — hand mutants.
