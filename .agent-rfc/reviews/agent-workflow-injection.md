# Review: agent-workflow-injection

Gap 10 of `docs/PRODUCT_BACKLOG.md`, after the owner's instruction of 2026-11-09 to fix the gaps.

## Pass 1 — findings: 3

Against `docs/review-levers.md`, with eleven hand mutants of the runner.

1. **The `!=` refusal was not tested.** The only `!=` case named no trusted role, so it failed for another reason. Fixed: a case with `!= 'OWNER'`.
2. **A check in `_guarded` was dead.** The four-part test already excludes branch names, so the title-or-body test could not change a result. Removed.
3. **A first draft took the field's subject from any word in it,** which would have let `pull_request.head.ref` count as authored text under a pull-request author guard. Rewritten by position, with a test.

## Pass 2 — findings: 0

- `scripts/test/test_agent_workflow_injection.py`: 45 passed. Every route in, each agent action and shell form, the environment's three scopes with a nearer value replacing a further one, and each way a guard can fail to hold.
- Hand mutants: all caught, including the two re-run after Pass 1.
- The contract has a published failing case, so another provider is held to it.
- AgentSmith's own six workflows pass, and no shipped template hands event text to an agent, so no tenant goes red from what AgentSmith wrote.

What it cannot see is stated in the design and in the control's passing message: text laundered through step outputs or files, an unlisted agent action, an agent started from a script. So the control is `partial` in the registry.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one runner, in the registry's dispatch; no second list of fields.
Group 2 · Quality / safety — [x] checked — workflow text is parsed and matched, never evaluated.
Group 3 · Architecture / hygiene — [x] checked — a repository control, the shape `delegating.py` uses; no new dependency.
Group 4 · Process — [x] checked — design first; CHANGELOG, backlog and the framework map updated.
Group 5 · Intuitive UI — [x] n/a — no screen changes.
Group 6 · Signal integrity — [x] checked — a workflow that does not parse fails; the passing message says what was not followed.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: `scripts/test/test_agent_workflow_injection.py`; a case in `contract/security/v1/cases.json`.
Mutation-checked: yes, by hand; thirteen runs across eleven mutants, all killed after Pass 1.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`; the contract's case count.
Gates run: the new tests; `test_security_registry.py`, `test_security_contract.py`, `test_security_first_run.py`, `test_security_evidence_pack.py`; ruff; the runner on this repository; the process gate against the commit.

Levers reviewed: `failure-is-not-a-result`, `test-that-cannot-fail`, `declared-vs-enforced`.

KG query: kg:ad0800fc4605
