---
status: done
scope:
  - fixtures/security/control_registry.json
  - scripts/run-security-checks.py
  - scripts/security/report.py
  - scripts/test/test_security_evidence_pack.py
  - scripts/test/test_security_contract.py
  - scripts/test/test_security_registry.py
  - agentsmith/workflows/base_workflow.py
---
# Compliance Phase 0: correct the record

Phase 0 of `.agent-rfc/designs/compliance-readiness.md`. Slices CR1, CR2 and CR3. It changes what AgentSmith claims and adds
no capability.

## Problem

Measured on 2026-11-08 at `d31ec79`:

- **The OWASP map is mislabelled.** `docs/security-framework-map.md` is headed "2025-oriented" and uses the 2023 numbering, in
  the map and in the tags every evidence pack prints. A row tagged `LLM06` for PII means Excessive Agency to anyone reading
  the 2025 list. `https://genai.owasp.org/llm-top-10/` lists 2025 as the current edition.
- **Two controls are Met for less than their names say.** `SEC-HITL-001` proves a workflow pauses; `docs/uae-regulatory.md` calls
  human oversight "Met (core differentiator)", and a decision is a bare boolean with no approver. `SEC-SOV-001` reads AgentSmith's
  own template and no application's registry.
- **Public wording outruns the code.** README "Stay compliant", "UAE / Sovereign Compliance" and "mandatory HITL". The UAE page
  omits the DESC ISR and most of the instruments an owner building for a Dubai entity must answer, and presents PDPL as the
  privacy law without its government exclusion.
- **Status rows drift from the registry.** Several say `Partial→Met` where `SEC-PII-001` is `partial`.
- **A docstring claims a sender that does not exist.** `hitl_approved` says the Ops Portal fires it.

## Approach

**CR1, the numbering.** A crosswalk applied mechanically, so this is a relabel and not a re-judgement:

| 2023 | 2025 |
|---|---|
| LLM01 Prompt Injection | LLM01 |
| LLM02 Insecure Output Handling | LLM05 |
| LLM03 Training Data Poisoning | LLM04 |
| LLM04 Model Denial of Service | LLM10 |
| LLM05 Supply Chain | LLM03 |
| LLM06 Sensitive Information Disclosure | LLM02 |
| LLM07 Insecure Plugin Design | LLM06 |
| LLM08 Excessive Agency | LLM06 |
| LLM09 Overreliance | LLM09 |
| LLM10 Model Theft | LLM10 |

Three deliberate exceptions, each a judgement stated here:

- `SEC-RAG-001` also carries `LLM08`: it quarantines poisoned retrieved documents, which is part of that entry.
- `SEC-EVAL-002` (fairness) loses its tag. It was filed under Overreliance, and no 2025 entry is about fairness.
- `SEC-CHANGE-001` gains `LLM03` and `LLM04`, which the map already listed it under and the registry did not.

The map's rows are rewritten for the 2025 entries and the Current column re-graded against what the code does, including
LLM07 and LLM08. LLM01 and LLM09 drop from Met to Partial, and LLM10 is Partial because it now includes model extraction.

A test holds the map to the registry, so the two cannot drift again.

**CR2, split the claims** (`security-controls-closed` practice: split, never relabel):

- `SEC-HITL-001` keeps "the workflow pauses". New `SEC-HITL-002`, "Named human decision", is `gap`.
- `SEC-SOV-001` becomes "the shipped template stays in-border", owner framework. New `SEC-SOV-002`, "App residency", is `gap`.
- Both new rows have `subject: provider`. A repository-subject row would be run against every tenant, and a capability that does
  not exist must not change a tenant's Security job. `SEC-SOV-002` moves to the repository subject with AR1, on the profile. A
  tenant sees two more `not_applicable` rows and no change of verdict.
- Human oversight becomes Partial wherever it was Met on the strength of the pause: the UAE page, the ISO map and the design doc.

**CR3, wording.** README, the UAE page (the instruments, the ISR readiness board, the PDPL exclusion), the unconfirmed Annex A
identifiers in `docs/agentic-42001-coverage.md`, `Partial→Met` rows made `Partial`, the docstring, the manual's HITL note, and the
local `DemoScript.md`. ISR clauses are paraphrased because the text is copyrighted.

No release in this slice: changes go under `[Unreleased]`.

## Pillars

- P1 applies — `.agent-rfc/designs/compliance-readiness.md` is the plan; this file scopes Phase 0.
- P2 n/a — no new module or dependency; registry rows and documents only.
- P3 n/a — no code path changes, so no span changes; a docstring is the only change under `agentsmith/`.
- P4 applies — `scripts/test/test_security_registry.py` gains the map-against-registry test, proven by mutation; `scripts/test/test_security_contract.py` pins the provider rows.
- P7 n/a — no code path changes.
- P8 n/a — the telemetry wire is untouched.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 n/a — nothing new reads untrusted content.
- P12 n/a — no secrets involved.
- P13 applies — `scripts/security_port.py` is unchanged: a provider-subject row is `not_applicable` for a tenant, which is why the new rows cannot move a tenant's verdict.
- P14 applies — `fixtures/security/control_registry.json` is the one source; the new test fails when `docs/security-framework-map.md` disagrees with it.
- P15 applies — `scripts/run-security-checks.py` reports a declared gap as a gap, not as not-implemented or as a pass.
- P16 applies — `CHANGELOG.md` states the change; reverting is one commit, and no schema or wire value moves.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the two overclaiming controls are split so each name says only what its runner proves.
- `single-source-of-truth` — the registry is the source and a test holds the map to it.
- `grep-for-siblings` — every `Partial→Met`, `SEC-SOV-001` and human-oversight status in the live documents is searched and matched.
- `test-that-cannot-fail` — the new test is mutation-checked by hand against both directions of drift.
- `small-verified-slices` — claims only; no capability arrives with it.
