---
status: done
scope:
  - scripts/gate_models.py
  - scripts/evals_port.py
  - contract/evals/v1/**
  - scripts/test/**
  - scripts/mutation_check.py
---
# The evals contract's datasets, as the scorers read them

A defect in `contract/evals/v1` as released in v2.2.0 (2026-10-07), found moving KYC Sentinel onto
it the same day.

## Problem

Measured on 2026-10-07, KYC Sentinel's datasets through the v2.2.0 provider:

- **A real hallucination dataset is refused whole.** KYC's 7 hallucination cases carry
  `retrieved_context` as `{id, text}` documents — what a retrieval layer produces, and one of the
  three shapes the judge's `_as_context` reads (a string, a list of strings, a list of documents).
  `HallucinationCase` allows only the first two, so every case is "off its schema" and the suite is
  `not_gradable`: closed in CI, on data the scorer has always graded.
- **The reason blamed the wrong field.** A judged suite's refusal always ended "a judged case
  carries the output the application produced", though no `actual_output` was missing.
- **A schema says less than its scorer decides.** `score_rag_poison_case` reads any `expect` other
  than `quarantine` as `safe`, so a typo silently flips a case; the schema took any string. And
  rag_poison's `query` is required by the schema and optional to its scorer, which only reports it.

## Approach

- **Each case model says what its scorer reads**, field by field against `eval_judge.judge_case`,
  `score_adversarial_case` and `score_rag_poison_case`:
  - `retrieved_context`: a string, or a list whose items are strings or documents — `{text}`
    required, `id` / `title` optional, other keys the tenant's;
  - rag_poison `expect`: `quarantine` | `safe`; `query` optional.
  `expect` stays required, and lower case, in both guard suites: the contract asks a tenant to state
  each case's expectation as the schema spells it, rather than lean on a scorer's default or its
  letter-case folding — the published schema and the model accept exactly the same cases.
- **The reason names the output only when an output is missing.**
- **The fixture carries documents**: the flagged hallucination dataset's context is `{id, text}`, so
  conformance exercises the shape a real retrieval tenant uses. Schemas regenerated from the models.
- A **patch release**, 2.2.1, after this merges: v1 is a day old, no tenant has adopted it, and it
  accepts more of what its scorers already read; the one refusal it adds is a `rag_poison` expect
  the scorer would have misread.

## Pillars

- P1 applies — `.agent-rfc/designs/evals-dataset-shapes.md` records the defect as measured against KYC Sentinel's datasets before the fix.
- P2 applies — `scripts/gate_models.py` keeps one model per suite, now matching the scorer it feeds; no second reader of the datasets.
- P3 n/a — no tracing changes.
- P4 applies — `scripts/test/test_evals_contract.py` adds a case per shape the scorers read and per value they would misread; mutations restore the narrow context type and the unconditional reason.
- P7 applies — `scripts/gate_models.py`: Pydantic V2 models whose generated schemas are the published ones.
- P8 n/a — no telemetry wiring.
- P9 n/a — no orchestration.
- P10 n/a — no routing change.
- P11 applies — `scripts/gate_models.py` still validates every case before the judge's prompt quotes it; a document without `text` is refused rather than rendered as nothing.
- P12 n/a — no credentials.
- P13 applies — `scripts/gate_models.py` narrows rag_poison's `expect` to the two values its scorer distinguishes, so a typo is not gradable instead of silently `safe`.
- P14 applies — `contract/evals/v1/fixture.json`'s flagged hallucination dataset moves to documents; the verdicts it expects are unchanged.
- P15 applies — `scripts/evals_port.py`'s reason names the output only when one is missing.
- P16 n/a — no new fallback.

## Deviations

none

## Dependencies

none

## Levers

- `validate-on-the-receiving-side` — the schema is the receiver's, so it must accept what the receiver reads and refuse what it misreads.
- `test-with-real-data` — the defect was invisible to fixtures written alongside the schema and obvious on a tenant's data.
- `grep-for-siblings` — every suite's model checked against its scorer, not only the one that failed.
