# ISO/IEC 42001 — AgentSmith Control Map & Evidence Checklist

Auditor-facing pack: how AgentSmith’s **existing** controls and artifacts
map to an **AI Management System (AIMS)** style program under
**ISO/IEC 42001**.

This is a **thematic** map (plain-language control themes aligned to typical
AIMS / Annex A concerns). It is **not** a licensed reproduction of the
standard, **not** a clause-by-clause certification matrix, and **not** a
claim that AgentSmith or any tenant is ISO/IEC 42001 certified.

> **Disclaimer:** Not legal advice. Not a certification. Engage a qualified
> auditor and your compliance function. Framework mechanisms help produce
> **evidence**; the organisation still owns policy, risk acceptance, and
> certification scope.

**Related:** [`docs/uae-regulatory.md`](./uae-regulatory.md) (UAE mandates),
[`templates/uae-sovereign/`](../templates/uae-sovereign/) (residency),
SPECS.md §30 (enterprise pack + SOC2-oriented notes),
[`FIXES_AND_CLEANUP.md`](../FIXES_AND_CLEANUP.md) (gaps).

---

## How to read the status columns

| Status | Meaning |
|---|---|
| **Met** | Framework ships a concrete mechanism; evidence path exists today |
| **Partial** | Mechanism exists but incomplete for full AIMS intent |
| **Gap** | No first-class framework support yet (see FIXES) |
| **Org-owned** | Process/policy the tenant/org must supply; framework may only assist |

| Owner | Meaning |
|---|---|
| **Framework** | AgentSmith provides the control or artifact path |
| **Tenant** | Application / ops team must configure, run, or document |
| **Shared** | Framework mechanism + tenant policy/config required |

---

## Control theme map

| # | Theme | ISO 42001 focus (plain language) | Status | Owner | AgentSmith mechanism | Evidence artifact path |
|---|---|---|---|---|---|---|
| 1 | AI policy & roles | Define AI use, roles, accountability | **Partial** | Shared | Enterprise org policy (`agenticframework-org.yaml`), tenant `tenant.yaml`, portal RBAC (viewer/operator/admin) | Org policy file in MDM bundle; portal role assignments; `AGENT_OWNER_ID` on spans |
| 2 | Risk assessment | Identify AI risks before/during operation | **Org-owned** | Tenant | Template + schema gate at `.agent-rfc/security/risk_register.yaml` (`SEC-RISK-001`); HITL + budget caps reduce operational blast radius | Filled tenant risk register; `run-security-checks.py` schema result; link high-risk actions to `needs_hitl` |
| 3 | Data for AI systems | Govern training/eval/runtime data quality & provenance | **Partial** | Shared | Golden datasets under `.agent-rfc/`; fixture PRs; Knowledge Graph for code context — **not** a full data-governance suite | Golden JSON fixtures + PR history; KG rebuild via `map_codebase.py` / `verify_system.py --check-kg` |
| 4 | Third-party & models | Control providers, models, supply chain | **Partial** | Shared | `models.yaml` registry + degrade ladder; pluggable providers; UAE sovereign template | Tenant `models.yaml`; `templates/uae-sovereign/` residency checklist; provider adapter tests |
| 5 | Human oversight | Human control over significant AI decisions | **Met** | Framework | `run_with_hitl_gate`, recoverable DLQ + Ops Portal Replay/Discard, HITL promotion loop | Temporal HITL signals; portal DLQ actions; Phoenix HITL annotations; audit `hitl_promotion` |
| 6 | Transparency & logging | Traceability of AI system behaviour | **Met** | Framework | OTel → Phoenix; JSON agent logs; HMAC append-only audit log | Phoenix traces (filter `agent.owner_id` / `tenant.id`); `GET /api/audit`; `.agent-history.log` |
| 7 | Performance evaluation | Measure whether the AI system meets objectives | **Met** | Shared | `run-evals.py` scorecard; CD `--fail-below`; shadow-eval sampler | CI eval job logs; scorecard output; Phoenix shadow annotations; portal suggested-promotion queue |
| 8 | Fairness & bias | Prevent discriminatory outcomes | **Partial** | Shared | `run-evals.py --suite fairness`; paired fixtures; optional `fairness` judge field | Fairness scorecard + pair parity in `fairness_eval_results.json`; extend domain pairs in tenant fixtures |
| 9 | Security & privacy | Protect data in AI processing (incl. PII) | **Partial→Met** | Shared | Pre-call `input_guardrail.py` + `prompt_guard.py`; post-call `trace_redactor.py` + optional `moderation.py`; encrypted HITL blobs; CD `--check-redaction`; security harness CI | Guardrail/prompt-guard spans; redaction CI; `PROMPT_GUARD` / `MODERATION_HOOK`; `run-security-checks.py` evidence pack |
| 10 | Change management | Control changes to AI systems | **Met** | Shared | Branch protection; eval gates; enterprise RFC hook; IDE config drift check | PR + CI green; RFC files under `.agent-rfc/`; `generate-ide-config.py --check-only` |
| 11 | Incident & recovery | Detect, contain, recover from AI failures | **Met** | Framework | DLQ / recoverable steps; MAJOR/CRITICAL log protection; circuit breaker; budget degrade | Portal DLQ history; unresolved issues in `verify_system.py`; audit `hook_bypass` / config events |
| 12 | Continual improvement | Learn from production and improve | **Met** | Shared | HITL → golden dataset promotion; shadow-eval suggestions (never auto-promote) | Promoted fixtures PRs; portal promotion queue; `sync-ui-feedback.py` / `promote-learning.py` runs |

---

## Evidence checklist (what to hand an auditor)

Export or screenshot these **artifacts**, not slide claims. Paths assume a
configured Ops Portal + Phoenix + tenant CI.

### A. Governance & access

- [ ] Org policy YAML (`agenticframework-org.yaml` / enterprise MDM bundle)
- [ ] Portal RBAC: who is viewer / operator / admin (SSO groups if OIDC)
- [ ] Sample audit events: `GET /api/audit?tenantId=<id>` (HMAC `verified: true`)
- [ ] Break-glass policy + sample `hook_bypass` audit row (if enterprise)

### B. Human oversight

- [ ] Workflow code or design note listing high-impact actions with `needs_hitl`
- [ ] One completed HITL approve/reject (Temporal history or portal record)
- [ ] One DLQ edit → Replay (or Discard) with before/after payload
- [ ] Encrypted HITL blob retention setting (`HITL_BLOB_DIR` / S3) documented

### C. Transparency & monitoring

- [ ] Phoenix project URL + example trace with `tenant.id` / `agent.owner_id`
- [ ] Ops Portal dashboard: run status, cost/cap, error rate (24h)
- [ ] Redaction profile in use (staging/production) +
      `python3 scripts/verify_system.py --check-redaction` CI log

### D. Performance & change

- [ ] Latest `run-evals.py` scorecard (or CD job) with `--fail-below` threshold
- [ ] Golden dataset location + recent fixture PR
- [ ] Shadow-eval schedule or sample annotations (if enabled)
- [ ] RFC / branch-protection evidence for a recent AI behaviour change

### E. Models, data residency, privacy

- [ ] Tenant `models.yaml` (providers, degrade chain)
- [ ] If UAE/national data: completed
      [`templates/uae-sovereign/`](../templates/uae-sovereign/) residency checklist
- [ ] Confirmation national/personal data does **not** use non-approved
      frontier hybrid endpoints (or counsel waiver on file)
- [ ] PII handling note: post-call redaction **plus** tenant pre-gateway scrub
      (pre-call `input_guardrail` + `prompt_guard` shipped)

### F. Gaps to disclose (honesty pack)

- [ ] Fairness/bias: **Partial** — run `python3 scripts/run-evals.py --suite fairness`; attach scorecard; extend pairs for domain
- [ ] Pre-call PII: **Partial→Met** — `INPUT_GUARDRAIL=default` + harness `SEC-PII-001`; extend via `register_input_guardrail` if needed
- [ ] Formal AI risk register: **Org-owned** — fill `.agent-rfc/security/risk_register.yaml` (schema gated by harness)
- [ ] ISO/IEC 42001 certificate: **not provided by this software**
- [ ] Multi-framework harness evidence: attach `run-security-checks.py --evidence-pack` output ([`docs/security-framework-map.md`](./security-framework-map.md))

---

## Suggested auditor narrative (one paragraph)

> AgentSmith embeds AI lifecycle controls in the delivery path: human
> stop-gates and recoverable failures, tamper-evident audit logs, full
> OpenTelemetry traces, eval gates on change, and optional enterprise hook
> enforcement. Evidence is produced as system artifacts (portal audit API,
> Phoenix, CI scorecards, redaction checks). The organisation remains
> responsible for AI policy, risk acceptance, fairness audits, data
> residency attestation, and any ISO/IEC 42001 certification scope.

---

## Mapping to UAE oversight

For UAE Authority for AI and Data / PDPL-oriented reviews, use this pack
**together with**:

1. [`docs/uae-regulatory.md`](./uae-regulatory.md) — five mandates  
2. [`templates/uae-sovereign/`](../templates/uae-sovereign/) — sovereign profile  
3. This document — AIMS-style control → artifact map  

Theme **5 (HITL)** and **6 (logging)** remain strong differentiators;
themes **8 (fairness)** and **9 (privacy)** are now **Partial** (suite +
pre-call scrub shipped — extend for domain/cert scope).

---

## SPECS cross-link

Enterprise pack mechanics: SPECS.md §30.  
SOC2-oriented short table: SPECS.md §30 “Compliance Notes”.  
ISO/IEC 42001-oriented short table: SPECS.md §30 (summary → this file).
