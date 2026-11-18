# Review: review-pass2-majors

Each defect was reproduced before it was fixed (in the second-pass review), and each fix has a test that fails on
`origin/main` (1d986d0): eight guard cases in `scripts/test/test_agent_workflow_injection.py`, the dataclass-and-date
gate in `agentsmith/test/test_compliance_runtime.py`, the SBOM interpreter in `scripts/test/test_compliance_checks.py`,
and the provider evidence in `scripts/test/test_compliance_port.py`.

## Pass 1 — findings: 4

Against `docs/review-levers.md`, by hand mutants on each fix (14). Four survived; each was a missing test, and one
showed the `||` refusal is load-bearing rather than redundant.

1. **`||` with a later `&&` term.** `contains(body, '@claude') || x && …author_association == 'OWNER'` splits on `&&`
   into a term that is a clean trusted-author test, and `&&` binds tighter, so it runs for anyone mentioning the agent.
   The `||` refusal catches it; no test held that. Added.
2. **A role test on the wrong author.** `github.event.issue.author_association == 'OWNER'` guarding a comment's body:
   the context check was tested only through the list form. Added.
3. **The real activity's answer.** The test fake computed the digest itself, so the activity could stop returning it
   with every test green. A test now calls `compliance_record_activity` and holds its answer to what it recorded.
4. **A known gap that starts passing.** Nothing failed when `KNOWN_PROVIDER_GAPS` named a row that passes, which would
   let the exception outlive the gap. Added.

## Pass 2 — findings: 0

- The 14 mutants again: all killed.
- Siblings: `_restricts` has one caller; every other `execute_activity(compliance_record_activity, …)` ignores the
  answer; the sidecar path already computes its digest where it records. `.github/workflows` and
  `workflow-templates` scanned with the new guard rule: no problem, so no tenant template turns red.
- The new SBOM commands run for real on a `pyproject.toml` app depending on `requests`: 7 components, the app and its
  dependencies (was 33, all CycloneDX's own).
- `scripts/compliance_port.py provider-evidence` on this tree: seven rows pass, `OB-AUDIT-COVERAGE` is the named gap,
  exit 0.
- Docs that described the old behaviour: `contract/compliance/v1/protocol.md` (`pending`, `not_applicable`), the
  CHANGELOG's earlier `OB-AUDIT-COVERAGE` sentence, the backlog's current state and three rows. Updated.
- ruff 0.15.20 over `scripts` and `agentsmith`: clean. mypy 1.14.1 as CI runs it: clean.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one digest, computed in the activity; `_input_digest` and its pinning test removed.
Group 2 · Quality / safety — [x] checked — a guard counts only with a term that can only narrow to trusted authors; a gate without a digest fails closed.
Group 3 · Architecture / hygiene — [x] checked — each fix in its own module; one new port verb; no dependency.
Group 4 · Process — [x] checked — design first; CHANGELOG, backlog and the compliance protocol updated.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — the provider evidence is produced and gates CI and the release; the one exception is named by id and reason, and fails if it goes stale.
Group 7 · Auth & session integrity — [x] checked — `author_association` counts only as a positive test of a trusted role on the field's own author.

Tests added: 13 guard cases in `scripts/test/test_agent_workflow_injection.py`; three in `agentsmith/test/test_compliance_runtime.py`; one in `scripts/test/test_compliance_checks.py`; six in `scripts/test/test_compliance_port.py`; three contract cases.
Mutation-checked: yes, by hand; 14 mutants, all killed after pass 1.
Fixtures re-pinned: `scripts/test/test_security_contract.py` case count (36 to 39); `docs/validation-checklist.md` gates table; `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; the whole Python suite; ruff; mypy; the knowledge-graph check; the process gate against the commit.

Levers reviewed: `guards-must-be-able-to-fail`, `grep-for-siblings`, `environment-parity`, `test-the-contract`, `implemented-not-invoked`, `aggregates-name-their-scope`, `test-that-cannot-fail`

KG query: kg:f771cb04716f

## Pass 3 — findings: 1

CI on #117 (Self-Test, "Python scripts/runtime/examples").

1. **The committed knowledge graph lacked this review record's node.** The graph was rebuilt before the record was
   written, and `agentsmith gate kg check` passed locally because the record was not yet tracked;
   `scripts/verify_system.py --check-kg`, which CI runs, counts tracked guardrails and found it missing. Rebuilt from
   the committed tree. (The `mutmut run || true` errors in the same job are its non-fatal survey step, and appear on
   `main` too.)

## Pass 4 — findings: 0

- `python3 scripts/verify_system.py --check-kg` on a clean checkout of the branch: passes after the rebuild, and leaves
  the tree clean.

## Sign-off (after CI)

Group 1 · DRY & shared code — [x] checked — no code change.
Group 2 · Quality / safety — [x] checked — no code change.
Group 3 · Architecture / hygiene — [x] checked — the graph fixture only.
Group 4 · Process — [x] checked — the check CI runs, run on the committed tree before pushing.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — the graph matches what is tracked.
Group 7 · Auth & session integrity — [x] n/a — no auth code.

Tests added: none.
Mutation-checked: n/a — fixture only.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `scripts/verify_system.py --check-kg`; `agentsmith gate kg check`; the process gate against the commit.

Levers reviewed: `run-the-gates-ci-lists`, `fixture-truth`

KG query: kg:e5219fce2510
