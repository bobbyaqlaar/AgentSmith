# Review — setup-evals-provider

Design: `.agent-rfc/designs/setup-evals-provider.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 3

1. **The new test could not fail** (`test-that-cannot-fail`), shown by the mutation suite: it asked
   whether `requirements-gate.txt` *mentions* `httpx`, and the comment beside the requirement does.
   Deleting the requirement line survived. Both list tests — the new one and
   `test_the_gate_requirements_list_covers_what_the_gate_imports` — now read requirement lines only,
   with comments stripped; the mutation is caught.
2. **The setup action still described itself as the gate's alone** while tenants' eval jobs install
   it for the evals port; its comment and description now name the gate, the rules and the evals.

3. **The design's scope did not cover `scripts/mutation_check.py`**, where the new mutation lives —
   the commit gate refused the commit and named it. Scoped in.

## Pass 2 — findings: 0

Every reference to `requirements-gate.txt` checked — the setup action, the sync workflow template,
self-test, `docs/process-gates.md`, `docs/DESIGN.md`: each installs or names the same file, which now
carries what all three ports need; none needed changing beyond DESIGN's tree comment. The judge path's
other third-party imports are optional (`tiktoken`, with a fallback) or route-specific (`google-auth`
for Vertex AI, `boto3` for Bedrock), and stay the tenant's — named in the CHANGELOG.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one requirements list for the provider's CI setup, now covering all three ports; no second file.
Group 2 · Quality / safety — [x] checked — a judged case run with and without `httpx` (pass, then no_verdict); both list tests read requirement lines only; `evals_contract` mutations 11/11, the new one deleting the requirement.
Group 3 · Architecture / hygiene — [x] checked — one package added to the setup step, already a framework dependency; Vertex AI and Bedrock SDKs stay the tenant's.
Group 4 · Process — [x] checked — design before the change; CHANGELOG Fixed; DESIGN's tree comment; patch release next, in the same pull request.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — a provider that cannot call its judge no longer reads as a judge that did not answer.
Group 7 · Auth & session integrity — [x] n/a — no credential handling changes.

Tests added: `test_a_judged_suite_cannot_grade_without_httpx` (`scripts/test/test_evals_contract.py`); `test_the_gate_requirements_list_covers_what_the_gate_imports` names `httpx` and ignores comments.
Mutation-checked: `evals_contract` 11/11.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
Gates run: full `pytest` on the staged tree (2328 passed, 10 skipped); `ruff check .`; the self-test's knowledge-graph gate; the evals conformance suite against a provider in the setup step's environment (8/17 before, 17/17 after); AqlaarTeleologyStudio's three suites through its launcher in that environment.

Levers reviewed: `environment-parity`, `failure-is-not-a-result`, `test-the-contract`, `test-that-cannot-fail`, `grep-for-siblings`.

KG query: kg:ad2e7f39a231
