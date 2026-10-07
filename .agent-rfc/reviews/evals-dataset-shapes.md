# Review — evals-dataset-shapes

Design: `.agent-rfc/designs/evals-dataset-shapes.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 2

Found while fixing, each verified before it was changed.

1. **A letter-case validator made the model and its schema disagree** (`single-source-of-truth`).
   The first fix lower-cased the guard suites' `expect` in a `before` validator, as their scorers
   do; the generated JSON schema still listed only lower-case values, so a published schema would
   have refused a case the provider graded. Dropped: `expect` is lower case as the schema spells
   it, and a test holds the model and the schema to the same verdict on every refused case.
2. **Nested-union errors named every branch tried** — `retrieved_context.list[str].0`,
   `retrieved_context.str` — not the field to fix. The reason now names each case's top-level
   field once.

## Pass 2 — findings: 0

Every case field the three scorers read (`eval_judge.judge_case`, `score_adversarial_case`,
`score_rag_poison_case`) against its model: required where the scorer needs it, optional where it
only reports it, enumerated where it branches on it. KYC Sentinel's four datasets validate; its
hallucination suite reaches the judge through the launcher. The contract's 17 cases pass unchanged,
the flagged hallucination dataset now in documents.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one model per suite, matched to its one scorer; the published dataset schemas regenerated from those models, and a test holds model and schema to the same verdict.
Group 2 · Quality / safety — [x] checked — 82 tests in `test_evals_contract.py` (14 new: every context shape the judge renders, every case a scorer would misread, the reason's wording both ways); `evals_contract` mutations 10/10, three new ones restoring each defect.
Group 3 · Architecture / hygiene — [x] checked — no dependency; no change to scoring; the fixture's verdicts unchanged.
Group 4 · Process — [x] checked — design before the fix; CHANGELOG Fixed; protocol table; backlog logs the sync gap found on the same move; patch release next.
Group 5 · Intuitive UI — [x] checked — a refusal names each case and the field to fix, and mentions outputs only when one is missing.
Group 6 · Signal integrity — [x] checked — a rag_poison typo is not gradable rather than silently `safe`; a valid retrieval dataset is no longer not gradable.
Group 7 · Auth & session integrity — [x] n/a — no credential or session change.

Tests added: 14 in `scripts/test/test_evals_contract.py`.
Mutation-checked: `evals_contract` 10/10.
Fixtures re-pinned: `contract/evals/v1/fixture.json` (documents in the flagged hallucination dataset); `dataset.hallucination` and `dataset.rag_poison` schemas regenerated; `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
Gates run: full `pytest` on the staged tree (2303 passed, 10 skipped); `ruff check .`; `mypy` (1.14.1); the self-test's tree and knowledge-graph gates; `agentsmith conformance --port evals` 17/17; KYC Sentinel's four CI suites through its launcher against this provider (adversarial passes; the judged three answer no verdict without a key and warn, as declared).

Levers reviewed: `validate-on-the-receiving-side`, `test-with-real-data`, `grep-for-siblings`, `single-source-of-truth`.

KG query: kg:1477f20d35b8
