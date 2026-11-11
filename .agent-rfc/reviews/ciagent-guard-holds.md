# Review: ciagent-guard-holds

## Pass 1 — findings: 1

Against `docs/review-levers.md`, after the fix.

1. **Two of my own negation tests passed for the wrong reason.** Written as a bare `if: !contains(…)`, the `!` starts a YAML tag and the parser drops it, so the condition the check saw was a positive guard (one of them was accepted). GitHub's parser reads it the same way, so a real workflow would have to write `${{ !… }}`. The tests now use that form, and say why.

## Pass 2 — findings: 0

- `scripts/test/test_agent_workflow_injection.py`: 60 passed; 14 of them fail on `origin/main`'s runner. `scripts/test/test_security_contract.py`: the provider passes all 36 cases.
- Five hand mutants (accept `!`; accept `||`; inherited environment only when named; drop the new fields; `toJSON(github)` without `.event`), all killed.
- The framework's own `.github/workflows` and `workflow-templates` scanned with the new rules: no problem, so the stricter rule turns no tenant template red.
- Read for siblings: the step-level `if:` is held to the same rule as the job's, since both go through `_guarded`.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one `_restricts` rule for job and step conditions.
Group 2 · Quality / safety — [x] checked — the check errs toward reporting; the message says how to restrict.
Group 3 · Architecture / hygiene — [x] checked — runner, tests and contract cases only.
Group 4 · Process — [x] checked — design first; CHANGELOG updated.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — green now needs a guard that can only narrow.
Group 7 · Auth & session integrity — [x] checked — `author_association` is read only as a restriction that holds.

Tests added: 15 cases in `scripts/test/test_agent_workflow_injection.py`; two contract cases.
Mutation-checked: yes, by hand; five mutants, all killed.
Fixtures re-pinned: `scripts/test/test_security_contract.py` case count; `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; the knowledge-graph check; the process gate against the commit.

Levers reviewed: `guards-must-be-able-to-fail`, `grep-for-siblings`, `test-the-contract`, `test-that-cannot-fail`.

KG query: kg:c00ba3184bb4
