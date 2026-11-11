# Security Framework Map — OWASP · NIST AI RMF · MITRE ATLAS · ISO/IEC 42001 · EU AI Act

Auditor- and engineer-facing pack: how AgentSmith maps **existing and planned**
controls to security and compliance frameworks, and how every tenant app
**proves** coverage via a **reusable security test harness**. The OWASP Agentic and EU AI Act
sections are a reading of the code, stated with their gaps; the harness does not grade them.

> **Disclaimer:** Not legal advice. Not certification. Not a licensed
> reproduction of OWASP, NIST, MITRE, or ISO standards. The organisation owns
> policy, risk acceptance, and certification scope. This document defines
> **mechanisms + evidence paths + automated checks** — not attestation.

**Related:**
- [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md) — ISO theme detail + evidence checklist
- [`docs/uae-regulatory.md`](./uae-regulatory.md) — UAE sovereign / PDPL / HITL
- [`docs/PRODUCT_ARCHIVE.md`](PRODUCT_ARCHIVE.md) — harness design
- [`docs/PRODUCT_ARCHIVE.md`](PRODUCT_ARCHIVE.md) — implementation plan
- [`docs/PRODUCT_BACKLOG.md`](PRODUCT_BACKLOG.md) — active gaps

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


## Verification coverage

**All 26** controls execute a runner,
so the map states what it verifies and nothing more.

`--strict` now fails on an **undeclared gap** — a control claiming `met` or
`partial` that no runner checks. Previously that produced `skip`, and skip
counted as green even under strict, so the harness exited 0 while 14 of 23
controls had never been examined. `SEC-HITL-001` — mandatory human review — was
among them, at a time when a live run showed that gate failing open on a
sanctions hit.

Runners delegate rather than re-implement: `verify_system.py --check-*`, an
existing pytest or portal test suite, or `run-evals.py`'s own fixture loading.
A second implementation would be a control that can disagree with the tests,
which is worse than none — it would eventually report Met while the behaviour
regressed.

Framework-owned suites run with tenant deployment and guardrail settings
stripped (`_TENANT_RUNTIME_KEYS`). Inheriting them made three budget tests fail
under `MODERATION_HOOK=required` and report as a compliance breach.

Judge-backed eval controls verify the gate is **wired and gateable** — fixtures
present, enough cases, threshold resolvable — and do not call a judge. A
control requiring a funded provider account would report Gap on an unpaid
invoice, which is an availability check wearing a compliance label. The same
The same reasoning kept `SEC-AUDIT-001`, `SEC-DLQ-001` and `SEC-SOV-001`
unbound: each would otherwise have failed whenever a database, a queue or a
credential was unavailable.

Three of those are now bound, by separating the claim that needs infrastructure
from the claim that does not — rather than by weakening either. `SEC-DLQ-001`
proves the dead-letter envelope contract (both producers build it through one
builder; its keys are what `enqueue` accepts) and says nothing about a row
reaching Postgres. `SEC-AUDIT-001` proves HMAC tamper-evidence and hands
append-only enforcement — a database trigger — to `SEC-AUDIT-002`, which stays
a declared gap because only a live database can demonstrate it. `SEC-SOV-001`
proves residency is *declared* correctly across the whole degrade ladder of the
template AgentSmith ships, which a live probe of one endpoint could never show.
Whether an application stays in-border is `SEC-SOV-002`, on a compliance profile.

### Tenant-declared controls

The framework registry cannot enumerate every control a tenant needs. KYC
Sentinel's evidence-mandated rating floor — a sanctions hit forces human review
whatever the model rated — is a real control with tests and documentation that
the compliance surface could not see, because there was nowhere to declare it.

A tenant may add `.agent-rfc/security/control_registry.json`. It merges over
the framework's, mirroring the `models.yaml` framework←tenant merge already in
this codebase, and is **additive only**: redefining a framework control id
raises. A registry the graded repo can edit is one where that repo can quietly
downgrade `SEC-HITL-001` to `noop` and keep a green harness.

Tenant controls use the `tenant_suite` runner and name a `suite:` — a test path
in the tenant repo. Running the tenant's own tests is deliberate: they already
encode what the control claims, including its negative cases, and a second
assertion written in the harness could drift from them.

```json
[{ "id": "SEC-KYC-FLOOR-001",
   "owner": "tenant", "runner": "tenant_suite",
   "suite": "test/test_analyst_judge.py",
   "mechanism": "agents/judge.py:check_rating_floor" }]
```

### `skip` means two different things

The harness reports both as `skip`, and that ambiguity is what let 14
unverified controls read as green:

- **`not applicable — …`** — the control is sound but has nothing to govern in
  this repo. The framework ships eval fixtures *for tenants* and holds no
  golden dataset of its own, so `SEC-EVAL-001` has nothing to measure when the
  framework grades itself. Falling back to the shipped base fixture would be
  worse than skipping: it would grade generic cases as if they were this
  repo's, the exact defect pinning `actual_output` was introduced to fix.
- **`runner … not implemented`** — nothing checked this. A gap.

Only the second should ever fail a strict run.

### Still unverified

No control is without a runner. `SEC-AUDIT-002` is the last to be bound: only a live database can show it, so it reads *not applicable*
everywhere except Self-Test's Ops Portal job, which sets `AUDIT_APPEND_ONLY_DSN` and runs it.

A declared gap **warns** — visible in every report and evidence pack — but does
not fail a strict run. A repo honest about its gaps must be able to pass, or
the only route to green is relabelling them `met`, which is the failure this
section exists to prevent.

An **undeclared** gap — `met` or `partial` with no runner — now **fails**
`--strict`. That combination is the map saying something untrue, and it is how
14 of 23 controls reported green while never being examined.

## Unified control registry (cross-framework)

> **Annex A, agentic reading.** `docs/agentic-42001-coverage.md` maps these controls onto the
> twelve platform features and twelve test scenarios of the agentic ISO/IEC 42001 briefing in
> `assets/`, with the Annex A identifiers that briefing uses (A.2–A.10) and what is **not** covered.
> The ISO column below stays thematic on purpose — see `docs/iso-42001-control-map.md`.

Every row is one **harness control**. Multiple frameworks may reference the same ID.

| Control ID | OWASP LLM | NIST AI RMF | MITRE ATLAS | ISO 42001 | Status | Owner | AgentSmith mechanism | Harness check |
|---|---|---|---|---|---|---|---|---|
| `SEC-PII-001` | LLM02 | MAP 2.6 / MANAGE 2.4 | AML.T0043 | Theme 9 | **Partial** | Shared | `agentsmith/input_guardrail.py` pre-call scrub | Inject Emirates ID/email/phone/card → assert redacted before `_invoke()` |
| `SEC-PII-002` | LLM02 | MANAGE 2.4 | AML.T0043 | Theme 9 | **Met** | Framework | `agentsmith/trace_redactor.py` + CD `--check-redaction` | `verify_system.py --check-redaction` + unit tests |
| `SEC-HITL-001` | LLM06 | GOVERN 1.5 / MANAGE 4.1 | AML.T0048 | Theme 5 | **Met** | Framework | `run_with_hitl_gate`, recoverable DLQ: the workflow pauses | Workflow fixture asserts pause signal + portal replay path |
| `SEC-HITL-002` | LLM06 | GOVERN 1.5 / MANAGE 4.1 | AML.T0048 | Theme 5 | **Met** | Framework | On a compliance profile, a gate takes only a named, signed decision, recorded in the worker's database | `agentsmith/test/test_compliance_runtime.py` |
| `SEC-AUDIT-001` | — | GOVERN 1.2 | AML.T0025 | Theme 6 | **Met** | Framework | HMAC tamper-evidence over `audit_log` events (`portal/lib/auditSignature.ts`) | `portal/test/auditSignature.test.ts` — sign → mutate → reject; key order stable; malformed signature rejected; missing key refuses. No database. |
| `SEC-AUDIT-002` | — | GOVERN 1.2 | AML.T0025 | Theme 6 | **Gap** | Framework | Append-only `audit_log` (UPDATE/DELETE triggers, `db/schema.sql`) | `portal/test/auditLog.test.ts` — needs a live Postgres; verified at deploy, not in CI |
| `SEC-RBAC-001` | — | GOVERN 1.3 | AML.T0048 | Theme 1 | **Partial** | Shared | Portal OIDC + `authz.ts` RBAC; role AND tenant scope, checked in every handler that resolves an operator's Access | `portal/test/authz.test.ts` — the role matrix (viewer cannot replay DLQ), plus two sweeps: every API handler reading `currentAccess()` must also call `canAccessTenant`/`filterTenantIds`, and no credential in the auth path may be compared with `===`. Both were added after finding a live instance of each. Still **partial**: the sweeps read source, they do not exercise a request |
| `SEC-EVAL-001` | LLM09 | MEASURE 2.6 | — | Theme 7 | **Met** | Shared | `run-evals.py` golden suite | Scorecard `--fail-below` in CI |
| `SEC-EVAL-002` | — | MEASURE 2.11 | — | Theme 8 | **Partial** | Shared | Fairness suite + pair parity | `--suite fairness`; extend tenant pairs |
| `SEC-EVAL-003` | LLM09 | MEASURE 2.6 | AML.T0024 | Theme 7 | **Met** | Shared | Hallucination rate gate | `--suite hallucination`; rate ≤ threshold |
| `SEC-BUDGET-001` | LLM10 | MANAGE 2.4 | AML.T0034 | Theme 11 | **Met** | Framework | Budget caps, degrade ladder, circuit breaker | `test_llm_gateway_budget.py` + cap breach simulation |
| `SEC-CHANGE-001` | LLM03, LLM04 | GOVERN 1.6 | — | Theme 10 | **Met** | Shared | Eval gates, the process gate, RFC enforcement | a declared gate provider; in AgentSmith, commits through the gate's hooks in throwaway repos |
| `SEC-CIAGENT-001` | LLM01 | MAP 2.6 | AML.T0051 | Theme 9 | **Partial** | Tenant | Reads `.github/workflows` for attacker-controlled event fields reaching a coding agent | Static: fails on a direct expression, an `env:` it uses, or `$GITHUB_EVENT_PATH`; does not follow step outputs or scripts |
| `SEC-DLQ-001` | LLM05 | MANAGE 4.4 | — | Theme 11 | **Met** | Framework | Recoverable step + DLQ; one `dead_letter_envelope()` builder for both producers | `agentsmith/test/test_dead_letter.py` — envelope keys match `enqueue`, both producers use the builder (AST-checked), flattened shape rejected by name. No Postgres. |
| `SEC-SELF-001` | LLM05 | MANAGE 4.4 | — | Theme 11 | **Partial** | Shared | Opt-in `run_with_self_correction` | Unit + workflow tests; not default path |
| `SEC-GW-001` | LLM06 | MAP 2.3 | AML.T0040 | Theme 4 | **Partial** | Shared | `llm_gateway.py` choke point | Static: tenant activities import gateway, not raw provider |
| `SEC-PROMPT-001` | LLM01 | MAP 2.6 | AML.T0051 | Theme 9 | **Met** | Framework | `agentsmith/prompt_guard.py` heuristics + denylist; `PROMPT_GUARD=off\|warn\|default\|strict` (blocking by default) | Two-part: detection over the injection fixture corpus **and** enforcement — the runner reports `fail` on `off`, `warn` on the observe-first `warn` tier, `pass` only when the configured mode actually blocks |
| `SEC-OUTPUT-001` | LLM05 | MEASURE 2.7 | — | Theme 7 | **Met** | Shared | `agentsmith/structured_output.py` `parse_llm_json` | Schema validation rejects malformed LLM JSON |
| `SEC-TOOL-001` | LLM06 | GOVERN 1.3 | AML.T0040 | Theme 4 | **Met** | Shared | `agentsmith/tool_registry.py` + the TENANT's allowlist | Every registered tool resolves as the tenant allowlist says, and at least one is denied |
| `SEC-MOD-001` | LLM01 | MAP 2.6 | AML.T0051 | Theme 9 | **Met** | Tenant | `agentsmith/moderation.py` + `MODERATION_HOOK`; classifier declared via `moderation.hook` in `tenant.yaml` (or `MODERATION_HOOK_PATH`) | Harness runner `scripts/security/runners/moderation_hook.py` — API smoke, plus under `required` it imports the tenant's declared classifier and verifies it returns a `ModerationResult` and does not block benign text. Unset hook fails strict CI |
| `SEC-RISK-001` | — | MAP 1.5 | AML.T0000 | Theme 2 | **Org-owned** | Tenant | *Planned:* risk register template generator | Harness checks `.agent-rfc/security/risk_register.yaml` exists + schema |
| `SEC-ADV-001` | LLM01 | MEASURE 2.7 | AML.T0024 | Theme 7 | **Met** | Shared | `run-evals.py --suite adversarial` + prompt_guard | Red-team fixtures in `--suite adversarial` |
| `SEC-SSO-001` | — | GOVERN 1.3 | AML.T0048 | Theme 1 | **Met** | Framework | `jti` revocation + `SSO_REVOCATION_MODE=fail-open\|fail-closed`; `GET /api/auth/session-status` answers **503**, not a 2xx, when the revocation store is unreachable | `sso_revocation` — snippet-checks the mode switch in `proxy.ts`/`lib/ssoRevocationMode.ts`, then runs `portal/test/ssoRevocation.test.ts`: the mode default, both branches, and (since 2026-08-25) what the ROUTE answers rather than a stubbed transport. Until then the route returned `200 {revoked:false}` on a database error, so fail-closed allowed every session through the one outage it exists for — met, green, and a no-op |
| `SEC-SOV-001` | LLM03 | MAP 2.3 | — | Theme 4 | **Met** | Framework | The template AgentSmith ships stays in-border, checked as a declaration. No application's registry is read | `sovereign_residency` — resolves the template through `_roles_from_doc` and walks every role's ladder with `llm_gateway.degrade_chain`; fails a hosted provider, a self-hostable one with no declared endpoint, or a dangling degrade target. No credentials. |
| `SEC-SOV-002` | LLM03 | MAP 2.3 | — | Theme 4 | **Met** | Shared | On a compliance profile, the application's registry and stores are checked against its boundary and the gateway refuses outside it | `scripts/test/test_compliance_checks.py` |
| `SEC-RAG-001` | LLM04, LLM08 | MAP 2.6 | AML.T0010 | Theme 3 | **Met** | Tenant | `prompt_guard.scan_documents` quarantines poisoned retrieved context per-document | `run-evals.py --suite rag_poison` over `fixtures/rag_poison_base.json` — poisoned/benign twins, miss ceiling `RAG_POISON_FAIL_ABOVE` (0.10). Detects poisoned context before prompt assembly; does not claim model resistance. |
| `SEC-AGENCY-001` | LLM06 | GOVERN 1.5 | AML.T0048 | Theme 5 | **Partial** | Tenant | HITL + workflow `needs_hitl` flags | Tenant declares high-impact actions; the harness checks the declaration is present, edited and gates at least one action, not that the gate is wired |

---

## Framework sections

### OWASP Top 10 for LLM Applications (2025 edition)

The numbering is OWASP's 2025 list, in this table, in the registry and in every evidence pack. A test holds this table to
the registry.

| Risk | Control IDs | Current | What is missing |
|---|---|---|---|
| LLM01 Prompt Injection | `SEC-PROMPT-001`, `SEC-MOD-001`, `SEC-ADV-001`, `SEC-CIAGENT-001` | Partial | Heuristics can be evaded, in Arabic as in English |
| LLM02 Sensitive Information Disclosure | `SEC-PII-001`, `SEC-PII-002` | Partial | Names are not scrubbed: the default covers Emirates ID, email, phone and cards |
| LLM03 Supply Chain | `SEC-SOV-001`, `SEC-SOV-002`, `SEC-CHANGE-001` | Partial | Dependency scan, SBOM and signed release provenance run in CI. MCP servers and tool definitions are pinned on a compliance profile. Model provenance is not checked |
| LLM04 Data and Model Poisoning | `SEC-RAG-001`, `SEC-CHANGE-001` | Partial | Covers retrieved documents and fixture review. Training data is the application's |
| LLM05 Improper Output Handling | `SEC-OUTPUT-001`, `SEC-DLQ-001`, `SEC-SELF-001` | Partial | Schema validation of structured output only. Nothing checks how an application uses free text |
| LLM06 Excessive Agency | `SEC-HITL-001`, `SEC-HITL-002`, `SEC-AGENCY-001`, `SEC-TOOL-001`, `SEC-GW-001` | Partial | Named decisions and manifest wiring on a compliance profile only. The allowlist says which tools, not with what arguments |
| LLM07 System Prompt Leakage | none | Partial | On a compliance profile the gateway withholds an answer that repeats a run of the system prompt. Paraphrase is not caught, and no control has a runner for it |
| LLM08 Vector and Embedding Weaknesses | `SEC-RAG-001` | Partial | Poisoned documents are quarantined. Tenant filtering applies on a compliance profile only |
| LLM09 Misinformation | `SEC-EVAL-001`, `SEC-EVAL-003` | Partial | Suites run at release. `citations_grounded` is opt-in per request and nothing requires it |
| LLM10 Unbounded Consumption | `SEC-BUDGET-001` | Partial | Tenant budget caps, and per-user limits on a compliance profile. Model extraction is not addressed |

### OWASP Top 10 for Agentic Applications (2026 edition, December 2025)

**None of the ten is fully covered: six are partial and four are not covered.** The list is about agents at run time. AgentSmith's
strongest controls act earlier, on the change before it merges, and this list has no entry for those. These rows are a reading
of the code on 2026-11-05. From 4.1.0 the harness grades them: each control carries an `owasp_agentic` tag for the rows below
that are at least partial, a test holds the registry to this table, and every evidence pack has an `owasp_agentic_top10.md`
listing all ten, with "not covered by any control" where that is the truth.

| Risk | Control IDs | Current | What it does | What it does not do |
|---|---|---|---|---|
| ASI01 Agent Goal Hijack | `SEC-PROMPT-001`, `SEC-RAG-001`, `SEC-ADV-001`, `SEC-MOD-001`, `SEC-CIAGENT-001` | **Partial** | Heuristics and a denylist scan prompts; poisoned retrieved documents are quarantined; a red-team suite tests both | Heuristics can be evaded. Nothing notices a hijack from what the agent then does, because evals judge the answer, not the path. `SEC-CIAGENT-001` reads CI workflows for event text reaching a coding agent; text passed through a step's output, a file or a script is not followed |
| ASI02 Tool Misuse | `SEC-TOOL-001`, `SEC-AGENCY-001`, `SEC-HITL-001`, `SEC-GW-001` | **Partial** | An unlisted tool is refused in strict mode; a human gate pauses a workflow | The allowlist says which tools, not with what arguments or in what order. `SEC-AGENCY-001` reads the declaration; it does not prove the gate is wired |
| ASI03 Identity & Privilege Abuse | `SEC-RBAC-001`, `SEC-SSO-001` | **Not covered** for agents | Human operators have OIDC, role and tenant scope, and revocation | An agent has no credential of its own. Tenant and role on a span are labels for tracing, not identity. No per-agent scope and no delegation chain |
| ASI04 Agentic Supply Chain Vulnerabilities | `SEC-CHANGE-001` | **Not covered** at run time | The framework's own dependencies are hash-locked and a repository pins the gate to a release | Off the profile, a repository's MCP servers and tool definitions are not checked: no declaration, no drift detection. On the `dubai-gov` profile, `agentsmith compliance mcp-pin` records each server in `.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json` and `.gemini/settings.json` with every page of its tools, `mcp-verify` fails on any change, and `OB-SUPPLY-CHAIN` fails an unpinned server. Servers an app starts from its own code are not seen, and nothing is signed |
| ASI05 Unexpected Code Execution | `SEC-OUTPUT-001` | **Not covered** | Structured model output is validated against a schema | Nothing sandboxes code an agent generates or runs. The edit-time gate governs what a coding agent commits; it contains nothing |
| ASI06 Memory & Context Poisoning | `SEC-RAG-001` | **Partial** | Retrieved context is scanned document by document | Memory that persists between sessions is not a governed artefact: no provenance, no versioning, no test |
| ASI07 Insecure Inter-Agent Communication | none | **Not covered** | Spans record the orchestrator and each role | Messages between agents are not authenticated or integrity-checked. Agents in one graph share state, and nothing governs agents across a boundary |
| ASI08 Cascading Failures | `SEC-BUDGET-001`, `SEC-DLQ-001`, `SEC-SELF-001`, `SEC-EVAL-003` | **Partial** | Budget caps and a degrade ladder bound spend; a failed step goes to a recoverable dead-letter queue; a citation check blocks auto-approval | No per-turn budget and no mid-run pause. Self-correction is opt-in. No way to stop a running app |
| ASI09 Human-Agent Trust Exploitation | `SEC-HITL-001`, `SEC-EVAL-001`, `SEC-EVAL-003` | **Partial** | Golden and hallucination suites gate releases; replay of a dead-lettered step is signed with a portal-issued key | Nothing tests what an approver is shown, or whether it misleads them. No explanation keyed by run |
| ASI10 Rogue Agents | `SEC-AUDIT-001`, `SEC-BUDGET-001` | **Partial** | The audit log is tamper-evident, spend is capped, and a person can stop an app on a compliance profile | Off the profile, no kill switch, no behavioural baseline or drift detection, and no retirement of an agent |

### EU AI Act (Regulation (EU) 2024/1689, as amended)

Whether the Act applies, and in which role, depends on the application and is the organisation's call: AgentSmith classifies
nothing. Dates are from the [Digital Omnibus on AI, Regulation (EU) 2026/1744](https://eur-lex.europa.eu/eli/reg/2026/1744/oj/eng),
published 24 July 2026 and in force 27 July 2026, read on 2026-11-05.

| Duty | Applies |
|---|---|
| Article 50 transparency | 2 August 2026, the general date, which the Omnibus left in place |
| Article 50(2) marking, for systems on the market before 2 August 2026 | Comply by 2 December 2026 |
| New Article 5 prohibitions, in points (ba) and (bb) of Article 5(1) and in Article 5(1a) and (1b) | 2 December 2026 |
| High-risk, Article 6(2) and Annex III | 2 December 2027 |
| High-risk, Article 6(1) and Annex I | 2 August 2028 |

**These rows say what AgentSmith gives you evidence for, not that a duty is met.** A control passing here is not a conformity
assessment. Article 50 is already in force and AgentSmith provides nothing for it.

| Article | Duty | Current | What AgentSmith gives you | What is yours, or missing |
|---|---|---|---|---|
| 9 | Risk management | **Partial** | A risk register checked for shape (`SEC-RISK-001`); the entries are yours | The system across the lifecycle, and whether the entries are true |
| 10 | Data governance | **Not covered** | Fairness suites test outputs (`SEC-EVAL-002`) | Training, validation and test data are the application's |
| 11, Annex IV | Technical documentation | **Partial** | Designs, reviews and evidence packs, tied to commits | Written by hand, not generated; nothing produces Annex IV as such |
| 12 | Record-keeping | **Partial** | The telemetry contract and a tamper-evident audit log (`SEC-AUDIT-001`). Append-only is a declared gap in the harness (`SEC-AUDIT-002`) | A new repository starts with no emitter, so nothing is recorded until you declare one. A run does not record its commit |
| 13 | Information for deployers | **Partial** | The widget shows run status and a trace link | Instructions for use are yours. No explanation keyed by run |
| 14 | Human oversight | **Partial** | A durable human gate (`SEC-HITL-001`); a declared list of actions needing one (`SEC-AGENCY-001`). Who decided is recorded on a compliance profile only (`SEC-HITL-002`) | A stop control, which Article 14(4)(e) names, exists on a compliance profile only. The manifest is not checked against the workflow |
| 15 | Accuracy, robustness, cybersecurity | **Partial** | Eval gates, the red-team suite and prompt guard | Declaring accuracy levels, and resilience testing beyond these suites |
| 17 | Quality management | **Partial** | The process gate records design, review and sign-off for each change | The organisation's system, of which this is one input |
| 19 | Keeping logs at least six months | **Not covered** | Nothing | Nothing sets or checks a retention period |
| 50(1) | Telling people they are dealing with AI | **Partial** | `CompletionResult.ai_generated`, and a signed obligation on a compliance profile (`OB-AI-DISCLOSURE`) | The application's interface; no gate reads it |
| 50(2) | Machine-readable marking of generated content | **Partial** | Every completion carries a signed machine-readable mark (`CompletionResult.provenance`) | Passing it on with the content is the application's, and marks inside images or audio are not covered |
| 72 | Post-market monitoring | **Partial** | The Ops portal shows runs, failures and traces | No plan, no production drift measurement |
| 73 | Serious incident reporting | **Not covered** | The audit log and dead-letter queue are inputs | No incident workflow or report |

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
| 4 Third-party & models | `SEC-SOV-001`, `SEC-SOV-002`, `SEC-GW-001` |
| 5 Human oversight | `SEC-HITL-001`, `SEC-HITL-002`, `SEC-AGENCY-001` |
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
| `pytest scripts/test/test_security_*.py agentsmith/test/test_security_*.py` | Unit/integration layer |

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

1. `agentsmith tenant init` seeds `.agent-rfc/security/` from `fixtures/security/templates/`:
   - `risk_register.yaml` — required in strict mode (`SEC-RISK-001`; schema: `contract/security/v1/risk_register.schema.json`)
   - `nist_profile.yaml` — optional NIST AI RMF profile
   - `agency_manifest.yaml` — high-impact actions → `needs_hitl`
   - `tool_allowlist.yaml` — `SEC-TOOL-001` allowlist
2. Fill `agency_manifest.yaml` — list workflows/actions requiring HITL
3. Fill `risk_register.yaml` — org risk entries (harness validates schema only; missing → warn non-strict / fail strict)
4. Extend `adversarial_evals.json` with domain-specific injection cases
5. Register moderation hook if `SEC-MOD-001` required (regulated content)
6. `eval-security.yml` runs on every push, and there is no non-strict mode

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
[`docs/PRODUCT_BACKLOG.md`](PRODUCT_BACKLOG.md) and implemented per
[`docs/PRODUCT_ARCHIVE.md`](PRODUCT_ARCHIVE.md).

| Priority | Control ID | Deliverable |
|---|---|---|
| P0 | Harness core | ~~`run-security-checks.py`, registry, CI workflow, evidence pack~~ **done** |
| P1 | `SEC-PROMPT-001` | ~~`agentsmith/prompt_guard.py` + injection fixtures + CI~~ **done** |
| P1 | `SEC-OUTPUT-001` | ~~`agentsmith/structured_output.py`~~ **done** (reference app migration optional) |
| P1 | `SEC-TOOL-001` | ~~`agentsmith/tool_registry.py` + allowlist enforcement~~ **done** |
| P2 | `SEC-ADV-001` | ~~`--suite adversarial` in eval pipeline~~ **done** |
| P2 | `SEC-MOD-001` | ~~Pluggable moderation hook + strict-mode CI~~ **done** |
| P2 | `SEC-RISK-001` | ~~Template + schema validator~~ **done** |
| P3 | `SEC-SSO-001` | ~~`SSO_REVOCATION_MODE=fail-closed` option + tests~~ **done** |
| P3 | `SEC-RAG-001` | Poison-doc harness fixture + docs |
| P1 | `SEC-HITL-002` | ~~A named, signed human decision on each gate~~ **done**, on a compliance profile |
| P1 | `SEC-SOV-002` | ~~An application's own registry and data stores checked against a declared boundary~~ **done**, on a compliance profile |

---

## Evidence checklist (auditor handoff)

Use with ISO pack. Automated items marked **auto**.

- [x] **auto** PII pre-call scrub (`SEC-PII-001`) — probe cases pass
- [x] **auto** Trace redaction (`SEC-PII-002`) — `--check-redaction` green
- [ ] **auto** Eval gates (`SEC-EVAL-001/002/003`) — CI scorecards attached (existing eval workflows; harness runners still skip)
- [x] **auto** HITL/DLQ (`SEC-HITL-001`, `SEC-DLQ-001`) — `test_hitl_gate.py` and `test_dead_letter.py`, one control each
- [x] **auto** Audit integrity (`SEC-AUDIT-001`) — `portal/test/auditSignature.test.ts`
- [ ] **manual** Audit append-only (`SEC-AUDIT-002`) — needs a live Postgres; deploy-time check
- [x] **auto** Prompt guard / structured output / tool allowlist / adversarial / moderation / SSO (`SEC-PROMPT-001`, `SEC-OUTPUT-001`, `SEC-TOOL-001`, `SEC-ADV-001`, `SEC-MOD-001`, `SEC-SSO-001`)
- [x] Framework risk register scaffold on file (`SEC-RISK-001` template)
- [ ] Tenant agency manifest filled (`SEC-AGENCY-001`)
- [ ] NIST profile filled (`nist_profile.yaml`) if claiming RMF alignment
- [ ] Sovereign residency checklist if UAE (`SEC-SOV-001` covers the shipped template; `SEC-SOV-002` the application, on a compliance profile)
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
