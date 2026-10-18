# Agentic ISO/IEC 42001 briefing — what AgentSmith covers

**Source.** `assets/Agentic_AI_ISO_IEC_42001_Compliance.pdf` — "Agentic AI Platform Compliance",
Z.ai Risk & Compliance Practice, October 2026: twelve platform features (F1–F12), an Annex A
mapping (A.2–A.10), twelve test scenarios (S1–S12), continuous-compliance obligations, and a
fifteen-item posture checklist (C1–C15). This page is AgentSmith's answer to it, control by control,
checked against the code on 2026-10-18.

**Same disclaimer as the rest of this map.** A mapping aid, **not** a certification, not legal
advice, and not a claim of conformance with ISO/IEC 42001 or any other standard. Annex A control
identifiers here are the briefing's; the ISO *themes* used elsewhere in this repository
(`docs/iso-42001-control-map.md`) are thematic and deliberately not clause numbers.

**How to read the status column.** `Met` — a runner or a gate enforces it and something fails when
it does not hold. `Partial` — the mechanism exists, its scope is narrower than the briefing asks.
`Tenant` — the framework provides the shape, the application owns the content.
`Not covered` — nothing in the framework does this today; listed, not quietly dropped.

---

## 1. Platform features F1–F12

| # | Briefing's feature | Annex A (per briefing) | AgentSmith | Status |
|---|---|---|---|---|
| **F1** | AI policy register & system inventory, per agent, with owner and risk tier | A.2, A.3 | Portal **Administration › Apps** (app, repo, tokens), `.agenticframework/tenant.yaml` (id, isolation, security toggles), org policy `agenticframework-org.yaml`, `AGENT_OWNER_ID` on spans | **Partial** — the inventory is per **app**, not per agent; no risk tier, acceptance criteria or review cadence field |
| **F2** | RBAC with separation of duties; approver ≠ author | A.3 | `portal/lib/authz.ts` — seven roles granted per app, role **and** tenant scope checked in every handler (`SEC-RBAC-001`); deviations approved only by the owner at a terminal (`agentsmith approve`), never by the agent; branch protection with admin enforcement, so the CI gate refuses the repository owner too | **Partial** — author/approver separation holds for *deviations* and for *merges*, not yet for a production release approval in the portal (phase 2) |
| **F3** | Auto-generated model & system card per agent, regenerated on artefact change | A.6.1.10 | — nearest are the design records under `.agent-rfc/designs/` and `docs/DESIGN.md`, which are written, not generated | **Not covered** |
| **F4** | Versioned artefact registry: model, prompt, tool, memory schema, planner | A.6, A.9 | `models.yaml` registry with `decommissioned:` flags and the degrade ladder; `.agent-rfc/security/tool_allowlist.yaml`; framework version pinned in `tenant.yaml`; the knowledge graph as the code-side registry; `agentsmith sync` refreshes framework-owned files **by hash** | **Partial** — models and tools are registered; **prompts, memory schemas and planner policy are not versioned artefacts** with an author, approval and rollback pointer |
| **F5** | Evaluation gate as the only path to production | A.6.1.9 | `agentsmith tenant promote --from staging --to production` gates on the staging scorecard; CD smoke runs `evals run --suite golden --fail-below`; suites golden / fairness / hallucination (`SEC-EVAL-001` Met, `-003` Met, `-002` Partial) | **Met** for model/code promotion — ⚠️ the gate is driven by commits and CD, so a change to a *prompt or tool* that is not a commit does not re-trigger it (see F4) |
| **F6** | Retirement & decommissioning workflow for an agent | A.6.4 | `models.yaml` carries `decommissioned: true` for a **model**; nothing retires an agent, archives its runs, withdraws its tool permissions or notifies consumers | **Not covered** |
| **F7** | Pre-deployment risk assessment, reviewed independently, re-run on scope change | A.5, Clause 6.1.3 | `.agent-rfc/security/risk_register.yaml` with a schema gate (`SEC-RISK-001`) and `agency_manifest.yaml` (`SEC-AGENCY-001`); every change carries a design answering P11/P12/P13 and a review; `agentsmith security check` fails a repository whose register is missing | **Partial** — the artefact is enforced, its **content** is the tenant's; no independent-reviewer role, and no trigger that re-runs it when autonomy or tool scope changes |
| **F8** | Red-team environment, scheduled, findings into the risk register | A.5.4 | Prompt-injection fixture corpus with **enforcement** checking (`SEC-PROMPT-001`: detection *and* that the configured mode actually blocks); a planted ghost citation that must be caught or CI fails (`SEC-EVAL-003`); `run-security-checks.py` harness | **Partial** — adversarial *tests* exist and gate CI; a sandboxed red-team environment, a schedule, and triage into the register do not |
| **F9** | Continuous bias & performance monitoring, versioned thresholds, owner alerts | A.6.1.10 | Fairness suite with pair parity; Phoenix traces; Ops shows cost against cap, run status, unresolved incidents; budget caps with a degrade ladder and circuit breaker | **Partial** — measurement is **batch at CI/promotion**, not continuous in production; no per-segment refusal rate, no drift threshold, no alert to a named owner |
| **F10** | Full agent trace log: every input, model call, tool call, memory write, HITL checkpoint; immutable, retained | A.7.3, A.6.1.10 | `contract/telemetry/v1` — a published attribute catalogue, judged by `agentsmith conformance --port telemetry`; spans per step including guardrail, prompt-guard and redaction; JSON agent logs; HMAC-signed audit log (`SEC-AUDIT-001`) that the **database refuses to delete from** (`audit_log_immutable()`, `SEC-AUDIT-002`, a declared gap because its test needs a live Postgres) | **Met** — ⚠️ retention is a deployment decision; traces live in Phoenix, which is not immutable storage |
| **F11** | User disclosure + explainability API keyed by run id | A.8.2 | `templates/in-app-widget/` — read-only: last agent run status, tenant-scoped trace link, error summary; run status and history through the Ops contract | **Partial** — no structured disclosure (that this is an agent, its identity and version, the tool categories, what it retains), and **no post-hoc explanation API keyed by run id** |
| **F12** | HITL checkpoints, runtime guardrails, kill switch | A.5.5, A.6.2 | **Checkpoints:** `run_with_hitl_gate`, durable pause, DLQ replay signed with a portal-issued key (`SEC-HITL-001`, Met). **Guardrails:** prompt guard, tool allowlist (unlisted = denied), budget caps with degrade ladder, circuit breaker, pre-call scrub and post-call redaction sharing one validator. **Kill switch:** — | **Partial** — two of three tiers are Met; **no kill switch** that halts in-flight runs, blocks new ones and alerts |

**Summary:** 2 Met (F5, F10), 7 Partial, 3 Not covered (F3 system card, F6 retirement, F12's kill
switch — plus F11's explanation API, counted inside its Partial).

---

## 2. The twelve scenarios S1–S12

What exists today that would exercise each, and what would have to be built. "Runner" means
something in this repository fails when the behaviour does not hold.

| ID | Scenario | Runner today | Status |
|---|---|---|---|
| S1 | Indirect prompt injection via retrieved document | `SEC-PROMPT-001` corpus + enforcement tier check; KYC's F3 scenario | **Covered** |
| S2 | Tool-call poisoning (compromised plugin returns malicious payload) | `structured_output.parse_llm_json` rejects malformed output; allowlist denies unlisted tools | **Partial** — no scenario for a *registered* tool returning a hostile payload, no quarantine |
| S3 | PII exfiltration via tool call | `input_guardrail` pre-call scrub, `trace_redactor` post-call, one shared card validator, `trace_tool_payloads` toggle (`SEC-PII-001/002`) | **Partial** — tool **arguments** are not inspected against a policy before the call |
| S4 | Unauthorised privileged action | Tool allowlist + HITL gate + portal RBAC | **Partial** — no test for escalation-with-approval as a path |
| S5 | Model drift with auto-rollback | — | **Not covered** |
| S6 | Hallucination cascade across turns | Hallucination suite with a planted ghost citation; citation check blocks auto-approval | **Partial** — per-turn budget and mid-run pause are not implemented |
| S7 | Memory poisoning from a prior session | — | **Not covered** |
| S8 | Third-party plugin compromise (vendor pushes a bad version) | Providers pinned by version range and a pinned CI setup ref; `agentsmith sync` verifies framework-owned files by hash | **Partial** — covers *our* supply chain, not a tenant's tool vendor |
| S9 | Bias in autonomous decisions at scale | Fairness suite with pair parity (`SEC-EVAL-002`) | **Partial** — batch, not per-segment in production |
| S10 | Kill-switch invocation & recovery | — | **Not covered** |
| S11 | Audit-trail completeness for a sampled run | Telemetry contract + conformance judge; HMAC audit log; append-only trigger | **Covered** |
| S12 | Consent withdrawal mid-session | — | **Not covered** — and see §4: this is an application obligation |

---

## 3. Not relevant to the framework

These are **management-system obligations**. A platform can emit evidence for them; it cannot hold
them, and building them into the framework would be claiming an organisation's duties as a
product feature.

- **Compliance drivers** (§2.3) — procurement gates, audit economy, regulatory anticipation. Reasons
  to certify, not controls.
- **Management review, Clause 9.3** (§6.4) — the AIMS owner's periodic review and its decisions. The
  framework supplies inputs (gate results, eval history, incident records, red-team findings); the
  review is a meeting with minutes.
- **CAPA register and internal audit cycle** (§6.2, C15) — corrective-action tracking belongs in the
  organisation's existing ISMS tooling. AgentSmith's backlog and archive are engineering records,
  not a CAPA register, and should not be renamed into one.
- **Appointing an AIMS owner with cross-functional authority** (§7.3) — an organisational decision.
- **Integrating the AIMS with an existing ISO/IEC 27001 ISMS / 27701 privacy programme** (§7.3).
- **Commissioning a first-party audit before certification** (§7.3), **certification-body engagement
  and the phased roadmap** (§7.2).
- **Evidence retention periods** (12–36 months per jurisdiction, F10) — a policy input; the platform
  enforces whatever period the deployment configures, it does not choose one.

---

## 4. Tenant guidelines — per application, not framework code

These are the items the briefing treats as platform features but which, in this architecture, are
**content the application owns**. The framework's job is to make them required and checkable; it
must not invent them. Each belongs in that app's design records, its `.agent-rfc/security/`
artefacts, or its own documentation — and `agentsmith security check` already fails a repository
that leaves the first two empty.

1. **Risk register content and risk tier per agent** (F7, C1) — the schema is enforced
   (`SEC-RISK-001`); the entries, impact tiers and residual-risk judgements are the app's.
2. **Agency manifest: which actions need a human** (F12, C12) — `SEC-AGENCY-001` requires the file;
   which of the app's actions are high-impact is a product decision.
3. **Acceptance criteria, review cadence and named owner per agent** (F1) — organisational metadata
   that the app declares.
4. **Consent capture and withdrawal semantics** (S12) — what consent covers, how a withdrawal
   propagates to in-flight runs and downstream calls, and what is purged. Entirely domain law and
   product design; the framework offers the HITL pause and DLQ as mechanisms.
5. **Per-segment fairness pairs and thresholds** (F9, S9) — the protected attributes and the pairs
   that matter are the app's domain; the suite and the parity scorer are the framework's.
6. **Tool inventory with a per-tool risk assessment** (F4, A.9) — the allowlist is enforced; the
   assessment behind each entry is the app's.
7. **Incident severity scale and time-to-contain targets** (§6.2) — the DLQ, audit log and incident
   surface exist; the thresholds are the organisation's.
8. **End-user disclosure wording** (F11) — that this is an agent, what it retains, which tools it
   may call. The widget is a surface; the words are the app's, in its language and jurisdiction.
9. **Decommissioning plan per agent** (F6) — who is notified, what is archived, for how long.
10. **Red-team scope and cadence** (F8) — which attacks matter for this domain, and how often.

**Suggested home:** a short `docs/agent-guidelines.md` in each tenant, referenced from its
`docs/DESIGN.md`, with these ten headings — so an auditor sampling that app finds the content where
the framework's artefacts point.

---

## 5. If the owner wants the gaps closed

Not started, not scheduled — listed so the gaps above are not just prose. Roughly in the order the
briefing's own roadmap implies:

| Gap | Shape it would take here |
|---|---|
| **Kill switch** (F12, S10) | A per-app halt in the Ops contract: portal action → worker refuses new runs and cancels in-flight ones → audit event. The pieces exist (ops settings, audit, RBAC). |
| **System card** (F3, C3) | Generated from what the repo already has — `tenant.yaml`, `models.yaml`, the tool allowlist, the latest eval scorecard, the active designs — regenerated by a gate when any of them changes. |
| **Prompt & memory-schema versioning** (F4) | The missing half of the artefact registry; without it F5's promotion gate cannot re-trigger on a prompt change. |
| **Explanation API keyed by run id** (F11) | The Ops contract already carries run identity; this is a read path plus a disclosure payload. |
| **Agent retirement** (F6) | A CLI verb plus an Ops event; mostly bookkeeping once the registry exists. |
| **Drift & per-segment monitoring** (F9, S5, S9) | The heaviest: needs production-time measurement, thresholds as versioned config, and alerting. |
| **Memory provenance** (S7) | Only meaningful once memory is a registered artefact (F4). |

---

## Related

- `docs/iso-42001-control-map.md` — the twelve themes this repository maps itself to, with statuses.
- `docs/security-framework-map.md` — the `SEC-*` control registry, with OWASP / NIST AI RMF / MITRE
  ATLAS / ISO theme citations per control and what verifies each.
- `docs/uae-regulatory.md` — the five UAE mandates and their statuses.
- `assets/Agentic_AI_ISO_IEC_42001_Compliance.pdf` — the briefing this page answers.
