# Security Framework Map — OWASP · NIST AI RMF · MITRE ATLAS · ISO/IEC 42001

Auditor- and engineer-facing pack: how AgentSmith maps **existing and planned**
controls to four security/compliance frameworks, and how every tenant app
**proves** coverage via a **reusable security test harness**.

> **Disclaimer:** Not legal advice. Not certification. Not a licensed
> reproduction of OWASP, NIST, MITRE, or ISO standards. The organisation owns
> policy, risk acceptance, and certification scope. This document defines
> **mechanisms + evidence paths + automated checks** — not attestation.

**Related:**
- [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md) — ISO theme detail + evidence checklist
- [`docs/uae-regulatory.md`](./uae-regulatory.md) — UAE sovereign / PDPL / HITL
- [`docs/superpowers/specs/2026-07-15-security-compliance-harness-design.md`](./superpowers/specs/2026-07-15-security-compliance-harness-design.md) — harness design
- [`docs/superpowers/plans/2026-07-15-security-compliance-harness.md`](./superpowers/plans/2026-07-15-security-compliance-harness.md) — implementation plan
- [`FIXES_AND_CLEANUP.md`](../FIXES_AND_CLEANUP.md) — active gaps

---

## How to read this document

| Column | Meaning |
|---|---|
| **Control ID** | Stable harness key (`SEC-*`). Used in fixtures, CI, evidence packs |
| **Status** | **Met** = shipped + testable today · **Partial** = mechanism exists, harness or depth incomplete · **Gap** = not shipped (plan covers) · **Org-owned** = tenant/process responsibility |
| **Owner** | **Framework** · **Tenant** · **Shared** |
| **Harness** | How the reusable test harness validates this control for any AgentSmith app |

### Status legend (same as ISO map)

| Status | Harness behaviour |
|---|---|
| **Met** | Hard CI check; failure blocks merge/deploy when gate enabled |
| **Partial** | Soft or smoke check today; hard gate after implementation plan lands |
| **Gap** | Harness emits `SKIP` with explicit gap ID until implemented |
| **Org-owned** | Harness validates **artifact presence** (template uploaded), not content truth |

---

## Unified control registry (cross-framework)

Every row is one **harness control**. Multiple frameworks may reference the same ID.

| Control ID | OWASP LLM | NIST AI RMF | MITRE ATLAS | ISO 42001 | Status | Owner | AgentSmith mechanism | Harness check |
|---|---|---|---|---|---|---|---|---|
| `SEC-PII-001` | LLM06 | MAP 2.6 / MANAGE 2.4 | AML.T0043 | Theme 9 | **Partial→Met** | Shared | `runtime/input_guardrail.py` pre-call scrub | Inject Emirates ID/email/phone/card → assert redacted before `_invoke()` |
| `SEC-PII-002` | LLM06 | MANAGE 2.4 | AML.T0043 | Theme 9 | **Met** | Framework | `runtime/trace_redactor.py` + CD `--check-redaction` | `verify_system.py --check-redaction` + unit tests |
| `SEC-HITL-001` | LLM08 | GOVERN 1.5 / MANAGE 4.1 | AML.T0048 | Theme 5 | **Met** | Framework | `run_with_hitl_gate`, recoverable DLQ | Workflow fixture asserts pause signal + portal replay path |
| `SEC-AUDIT-001` | — | GOVERN 1.2 | AML.T0025 | Theme 6 | **Met** | Framework | HMAC append-only `audit_log` | Portal test: append → verify signature → reject tamper |
| `SEC-RBAC-001` | — | GOVERN 1.3 | AML.T0048 | Theme 1 | **Partial** | Shared | Portal OIDC + `authz.ts` RBAC | Role matrix tests: viewer cannot replay DLQ |
| `SEC-EVAL-001` | LLM09 | MEASURE 2.6 | — | Theme 7 | **Met** | Shared | `run-evals.py` golden suite | Scorecard `--fail-below` in CI |
| `SEC-EVAL-002` | LLM09 | MEASURE 2.11 | — | Theme 8 | **Partial** | Shared | Fairness suite + pair parity | `--suite fairness`; extend tenant pairs |
| `SEC-EVAL-003` | LLM09 | MEASURE 2.6 | AML.T0024 | Theme 7 | **Met** | Shared | Hallucination rate gate | `--suite hallucination`; rate ≤ threshold |
| `SEC-BUDGET-001` | LLM04 | MANAGE 2.4 | AML.T0034 | Theme 11 | **Met** | Framework | Budget caps, degrade ladder, circuit breaker | `test_llm_gateway_budget.py` + cap breach simulation |
| `SEC-CHANGE-001` | — | GOVERN 1.6 | — | Theme 10 | **Met** | Shared | Eval gates, hooks, RFC enforcement | CI workflow presence + hook dry-run |
| `SEC-DLQ-001` | LLM02 | MANAGE 4.4 | — | Theme 11 | **Met** | Framework | Recoverable step + DLQ | `verify_system.py --check-dlq` |
| `SEC-SELF-001` | LLM02 | MANAGE 4.4 | — | Theme 11 | **Partial** | Shared | Opt-in `run_with_self_correction` | Unit + workflow tests; not default path |
| `SEC-GW-001` | LLM07 | MAP 2.3 | AML.T0040 | Theme 4 | **Partial** | Shared | `llm_gateway.py` choke point | Static: tenant activities import gateway, not raw provider |
| `SEC-PROMPT-001` | LLM01 | MAP 2.6 | AML.T0051 | Theme 9 | **Met** | Framework | `runtime/prompt_guard.py` heuristics + denylist | Adversarial fixture suite: injection/jailbreak blocked or flagged |
| `SEC-OUTPUT-001` | LLM02 | MEASURE 2.7 | — | Theme 7 | **Met** | Shared | `runtime/structured_output.py` `parse_llm_json` | Schema validation rejects malformed LLM JSON |
| `SEC-TOOL-001` | LLM07 | GOVERN 1.3 | AML.T0040 | Theme 4 | **Met** | Shared | `runtime/tool_registry.py` + allowlist | Tool call without allowlist → hard fail |
| `SEC-MOD-001` | LLM01 | MAP 2.6 | AML.T0051 | Theme 9 | **Met** | Tenant | `runtime/moderation.py` + `MODERATION_HOOK` | Harness runner `scripts/security/runners/moderation_hook.py` — strict mode: unset hook fails CI; tenant registers classifier |
| `SEC-RISK-001` | — | MAP 1.5 | AML.T0000 | Theme 2 | **Org-owned** | Tenant | *Planned:* risk register template generator | Harness checks `.agent-rfc/security/risk_register.yaml` exists + schema |
| `SEC-ADV-001` | LLM01 | MEASURE 2.7 | AML.T0024 | Theme 7 | **Met** | Shared | `run-evals.py --suite adversarial` + prompt_guard | Red-team fixtures in `--suite adversarial` |
| `SEC-SSO-001` | — | GOVERN 1.3 | AML.T0048 | Theme 1 | **Met** | Framework | `jti` revocation + `SSO_REVOCATION_MODE=fail-open\|fail-closed` | — |
| `SEC-SOV-001` | LLM05 | MAP 2.3 | — | Theme 4 | **Partial** | Tenant | `templates/uae-sovereign/` + `verify_sovereign_endpoint.py` | Residency checklist + live endpoint smoke |
| `SEC-RAG-001` | LLM03 | MAP 2.6 | AML.T0010 | Theme 3 | **Partial** | Tenant | RAG v1 + fixture promotion | Ingest poison doc → retrieval does not surface in answer (tenant fixture) |
| `SEC-AGENCY-001` | LLM08 | GOVERN 1.5 | AML.T0048 | Theme 5 | **Partial** | Tenant | HITL + workflow `needs_hitl` flags | Tenant declares high-impact actions; harness verifies gate wired |

---

## Framework sections

### OWASP LLM Top 10 (2025-oriented mapping)

| Risk | Control IDs | Current | Target (harness) |
|---|---|---|---|
| LLM01 Prompt injection | `SEC-PROMPT-001`, `SEC-MOD-001`, `SEC-ADV-001` | Met | Prompt guard + adversarial suite + moderation hook API |
| LLM02 Insecure output handling | `SEC-OUTPUT-001`, `SEC-DLQ-001`, `SEC-SELF-001` | Partial | Pydantic schema gate on all structured LLM outputs in reference apps |
| LLM03 Training data poisoning | `SEC-RAG-001`, `SEC-CHANGE-001` | Partial | Fixture PR review + poison-doc retrieval test |
| LLM04 Model DoS | `SEC-BUDGET-001` | Met | Budget + rate tests in CI |
| LLM05 Supply chain | `SEC-SOV-001`, `SEC-CHANGE-001` | Partial | Model registry attestation + signed enterprise hooks |
| LLM06 Sensitive disclosure | `SEC-PII-001`, `SEC-PII-002` | Partial→Met | Pre + post PII tests mandatory in `--mode ci` |
| LLM07 Insecure plugin/tool design | `SEC-TOOL-001`, `SEC-GW-001` | Partial | Tool allowlist met; gateway-only static check still partial |
| LLM08 Excessive agency | `SEC-HITL-001`, `SEC-AGENCY-001` | Partial | Tenant manifest of gated actions; harness verifies wiring |
| LLM09 Overreliance | `SEC-EVAL-001`, `SEC-EVAL-003` | Met | Golden + hallucination gates |
| LLM10 Model theft | `SEC-GW-001`, `SEC-AUDIT-001` | Weak | Gateway key isolation; audit on config export (future) |

### NIST AI RMF 1.0

| Function | Category (summary) | Control IDs | Harness mode |
|---|---|---|---|
| **GOVERN** | Policies, roles, accountability | `SEC-RBAC-001`, `SEC-RISK-001`, `SEC-AUDIT-001`, `SEC-CHANGE-001` | Evidence pack: policy YAML + RBAC tests + audit sample |
| **MAP** | Context, risks, impacts | `SEC-RISK-001`, `SEC-AGENCY-001`, `SEC-SOV-001`, `SEC-PROMPT-001` | Risk register schema validation + tenant impact manifest |
| **MEASURE** | Evaluate, track, verify | `SEC-EVAL-*`, `SEC-ADV-001`, `SEC-OUTPUT-001`, `SEC-PII-*` | Eval + adversarial + schema + redaction scorecard |
| **MANAGE** | Prioritize, respond, recover | `SEC-HITL-001`, `SEC-DLQ-001`, `SEC-BUDGET-001`, `SEC-SELF-001` | DLQ drill + HITL simulation + budget breach |

**NIST profile:** Tenant fills `.agent-rfc/security/nist_profile.yaml` (template
shipped by harness) linking org roles → control IDs → evidence artifacts.

### MITRE ATLAS (selected tactics)

| Tactic | Technique (examples) | Control IDs | Harness |
|---|---|---|---|
| Reconnaissance | AML.T0000 | `SEC-RISK-001` | Threat model template present |
| Resource development | AML.T0010 | `SEC-RAG-001` | Poison-doc fixture |
| Initial access | AML.T0048 | `SEC-RBAC-001`, `SEC-SSO-001` | RBAC + revocation mode tests |
| ML attack staging | AML.T0024 | `SEC-ADV-001`, `SEC-EVAL-003` | Adversarial + hallucination |
| Exfiltration | AML.T0043 | `SEC-PII-001`, `SEC-PII-002` | PII leak probes |
| Impact | AML.T0034 | `SEC-BUDGET-001` | Cost exhaustion simulation |

Full technique IDs expand in `fixtures/security/atlas_technique_map.json` (shipped with harness).

### ISO/IEC 42001

ISO themes **1–12** map 1:1 to [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md).
The security harness **reuses** ISO evidence checklist items and adds **automated**
proof for themes 5–11.

| ISO theme | Primary control IDs |
|---|---|
| 1 AI policy & roles | `SEC-RBAC-001`, `SEC-RISK-001` |
| 2 Risk assessment | `SEC-RISK-001` (org-owned content) |
| 3 Data for AI | `SEC-RAG-001`, `SEC-CHANGE-001` |
| 4 Third-party & models | `SEC-SOV-001`, `SEC-GW-001` |
| 5 Human oversight | `SEC-HITL-001`, `SEC-AGENCY-001` |
| 6 Transparency & logging | `SEC-AUDIT-001`, `SEC-PII-002` |
| 7 Performance evaluation | `SEC-EVAL-*`, `SEC-OUTPUT-001` |
| 8 Fairness & bias | `SEC-EVAL-002` |
| 9 Security & privacy | `SEC-PII-*`, `SEC-PROMPT-001`, `SEC-MOD-001` |
| 10 Change management | `SEC-CHANGE-001` |
| 11 Incident & recovery | `SEC-DLQ-001`, `SEC-BUDGET-001`, `SEC-SELF-001` |
| 12 Continual improvement | `SEC-EVAL-001` + HITL promotion (manual evidence) |

---

## Reusable security test harness (contract)

Every app built on AgentSmith **inherits** the framework harness and **extends**
it with tenant-specific fixtures. One orchestrator, four framework reports.

### Entry points

| Command | Purpose |
|---|---|
| `python3 scripts/run-security-checks.py` | Full harness: all controls, human-readable report |
| `python3 scripts/run-security-checks.py --mode ci` | CI gate: Met + implemented Partial only; Gap = fail if `--strict` |
| `python3 scripts/run-security-checks.py --framework owasp` | Filter report to one framework |
| `python3 scripts/run-security-checks.py --evidence-pack ./out/` | JSON + Markdown auditor bundle |
| `python3 scripts/verify_system.py --check-security` | Smoke subset wired into install health |
| `pytest scripts/test/test_security_*.py runtime/test/test_security_*.py` | Unit/integration layer |

### Directory layout (framework + tenant)

```
AgenticFramework/
├── fixtures/security/
│   ├── control_registry.json      # canonical SEC-* definitions
│   ├── atlas_technique_map.json
│   ├── adversarial_evals_base.json
│   ├── prompt_injection_cases_base.json
│   ├── pii_probe_cases_base.json
│   └── templates/
│       ├── risk_register.yaml
│       ├── nist_profile.yaml
│       ├── agency_manifest.yaml
│       └── tool_allowlist.yaml
├── scripts/
│   ├── run-security-checks.py     # orchestrator
│   └── security/
│       ├── registry.py            # load control_registry.json
│       ├── runners/               # one runner per control family
│       ├── schemas/               # JSON Schema for org-owned artifacts
│       └── report.py              # framework rollup
└── workflow-templates/
    └── eval-security.yml          # reusable CI job

<tenant-repo>/
└── .agent-rfc/security/
    ├── risk_register.yaml         # org-owned (required in strict mode)
    ├── nist_profile.yaml          # optional NIST profile
    ├── agency_manifest.yaml       # high-impact actions → needs_hitl
    ├── adversarial_evals.json     # extends base adversarial cases
    └── tool_allowlist.yaml        # SEC-TOOL-001
```

### Control check types

| Type | Description | Example |
|---|---|---|
| **unit** | pytest, no network | `test_input_guardrail.py` |
| **integration** | local services / mocks | DLQ replay drill |
| **eval** | LLM judge or deterministic scorer | adversarial suite |
| **artifact** | file exists + schema valid | risk_register.yaml |
| **static** | AST/import analysis | gateway-only LLM calls |
| **live** | optional; gated by env | sovereign endpoint smoke |

### CI integration (all tenant apps)

`workflow-templates/ci-python-fastapi.yml` (and siblings) gain:

```yaml
security-checks:
  uses: ./.github/workflows/eval-security.yml
  with:
    strict: true
```

**Strict mode (`SECURITY_STRICT=1` / `strict: true`):** **Gap** controls and
**warn** results fail CI. Missing runners on Met/Partial controls stay `skip`
(do not fail strict). Framework self-test and the Python FastAPI tenant
template ship with `strict: true` (P12 complete).

### Per-app onboarding checklist

1. Copy templates from `fixtures/security/templates/` (via `ai-tenant-init`) into `.agent-rfc/security/`:
   - `risk_register.yaml` — required in strict mode (`SEC-RISK-001`; schema: `scripts/security/schemas/risk_register.schema.json`)
   - `nist_profile.yaml` — optional NIST AI RMF profile
   - `agency_manifest.yaml` — high-impact actions → `needs_hitl`
   - `tool_allowlist.yaml` — `SEC-TOOL-001` allowlist
2. Fill `agency_manifest.yaml` — list workflows/actions requiring HITL
3. Fill `risk_register.yaml` — org risk entries (harness validates schema only; missing → warn non-strict / fail strict)
4. Extend `adversarial_evals.json` with domain-specific injection cases
5. Register moderation hook if `SEC-MOD-001` required (regulated content)
6. Enable `eval-security.yml` in tenant CI with `strict: true` when ready

### Evidence pack output

`run-security-checks.py --evidence-pack` produces:

```
out/
├── security_report.json           # machine-readable per control
├── security_report.md             # human rollup by framework
├── owasp_llm_top10.md
├── nist_ai_rmf.md
├── mitre_atlas.md
└── iso_42001.md
```

Attach to auditor requests alongside [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md) checklist.

---

## Gap closure roadmap (required implementation)

These gaps **must** ship for full framework coverage. Status tracked in
[`FIXES_AND_CLEANUP.md`](../FIXES_AND_CLEANUP.md) and implemented per
[`docs/superpowers/plans/2026-07-15-security-compliance-harness.md`](./superpowers/plans/2026-07-15-security-compliance-harness.md).

| Priority | Control ID | Deliverable |
|---|---|---|
| P0 | Harness core | ~~`run-security-checks.py`, registry, CI workflow, evidence pack~~ **done** |
| P1 | `SEC-PROMPT-001` | ~~`runtime/prompt_guard.py` + injection fixtures + CI~~ **done** |
| P1 | `SEC-OUTPUT-001` | ~~`runtime/structured_output.py`~~ **done** (reference app migration optional) |
| P1 | `SEC-TOOL-001` | ~~`runtime/tool_registry.py` + allowlist enforcement~~ **done** |
| P2 | `SEC-ADV-001` | ~~`--suite adversarial` in eval pipeline~~ **done** |
| P2 | `SEC-MOD-001` | ~~Pluggable moderation hook + strict-mode CI~~ **done** |
| P2 | `SEC-RISK-001` | ~~Template + schema validator~~ **done** |
| P3 | `SEC-SSO-001` | ~~`SSO_REVOCATION_MODE=fail-closed` option + tests~~ **done** |
| P3 | `SEC-RAG-001` | Poison-doc harness fixture + docs |

---

## Evidence checklist (auditor handoff)

Use with ISO pack. Automated items marked **auto**.

- [x] **auto** PII pre-call scrub (`SEC-PII-001`) — probe cases pass
- [x] **auto** Trace redaction (`SEC-PII-002`) — `--check-redaction` green
- [ ] **auto** Eval gates (`SEC-EVAL-001/002/003`) — CI scorecards attached (existing eval workflows; harness runners still skip)
- [ ] **auto** HITL/DLQ (`SEC-HITL-001`, `SEC-DLQ-001`) — drill logs (verify_system; harness runners still skip)
- [ ] **auto** Audit integrity (`SEC-AUDIT-001`) — sample signed events (portal tests; harness runner still skip)
- [x] **auto** Prompt guard / structured output / tool allowlist / adversarial / moderation / SSO (`SEC-PROMPT-001`, `SEC-OUTPUT-001`, `SEC-TOOL-001`, `SEC-ADV-001`, `SEC-MOD-001`, `SEC-SSO-001`)
- [x] Framework risk register scaffold on file (`SEC-RISK-001` template)
- [ ] Tenant agency manifest filled (`SEC-AGENCY-001`)
- [ ] NIST profile filled (`nist_profile.yaml`) if claiming RMF alignment
- [ ] Sovereign residency checklist if UAE (`SEC-SOV-001`)
- [ ] Gap disclosure: any remaining Partial/Gap row above with target date / waiver

---

## Suggested auditor narrative

> AgentSmith tenants inherit a unified security harness that maps controls to
> OWASP LLM Top 10, NIST AI RMF, MITRE ATLAS, and ISO/IEC 42001 themes.
> Automated checks produce CI scorecards and an exportable evidence pack;
> the organisation supplies policy, risk registers, and certification scope.
> Pre-call PII scrubbing, prompt-injection defense, structured-output
> validation, tool allowlists, post-call redaction, HITL gates,
> tamper-evident audit, adversarial evals, and moderation hooks are
> framework-owned (P12 shipped); remaining Partial rows (RAG poison,
> sovereign smoke runners, RBAC matrix harness) are tracked above.

---

## SPECS cross-link

Enterprise pack §30: add **Security Framework Map** alongside ISO map.
Mechanisms unchanged — this document adds **cross-framework IDs** and the
**harness contract** for all tenant apps.
