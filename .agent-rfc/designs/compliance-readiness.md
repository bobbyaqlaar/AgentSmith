---
status: active
scope:
  - .agent-rfc/designs/compliance-readiness.md
---
# Compliance readiness: a regulated profile for AgentSmith and the apps it governs

The umbrella plan for closing the security and AI-governance gaps found on 2026-11-08 against the DESC Information
Security Regulation, OWASP LLM Top 10 (2025), NIST AI RMF, ISO/IEC 42001, the UAE AI Charter, Federal Decree-Laws 45/2021,
34/2021 and 25/2018, and the Digital Dubai AI ethics toolkit. It writes no code: every slice below gets its own design,
review and pull request.

Not legal advice. A product is never "compliant" with the ISR: the Dubai Government Entity is assessed, and AgentSmith
supplies controls and evidence. Clause text is paraphrased here because the ISR is copyrighted; identifiers are DESC's.

## Problem

Measured at `d31ec79`:

| Area | Finding | Where |
|---|---|---|
| Human accountability | A HITL decision is a bare `approved: bool`. Nothing records who decided. `ops.hitl` is defined and no route uses it, so the portal cannot decide a gate. No stop control | `agentsmith/workflows/base_workflow.py`, `portal/lib/authz.ts` |
| Audit coverage | Four event types only. Logins, logouts, failed logins, dead-letter replay and discard are not in `audit_log`. No retention setting | `portal/db/schema.sql` |
| Portal access | HTTP Basic is the default. No lockout or throttle. MFA is never checked. No idle timeout. No access review. No security headers | `portal/middleware.ts`, `portal/lib/sessionToken.ts` |
| Residency | `SEC-SOV-001` reads AgentSmith's own template, not the app's registry, and is marked Met. The gateway never refuses an out-of-border endpoint | `scripts/security/runners/sovereign_residency.py` |
| Continuity | No backup, restore, DR or RPO/RTO anywhere. The Helm database is one replica | `templates/onprem-deploy/` |
| OWASP LLM | The map says 2025 and uses 2023 numbering. The vector table has no tenant column or filter. No Arabic in prompt guard or in the injection, PII and fairness fixtures. Names are not scrubbed. Moderation has no default classifier | `fixtures/security/control_registry.json`, `agentsmith/vector_store.py` |
| Supply chain | No dependency scan, SBOM, SAST or signed release evidence in CI | `.github/workflows/` |
| Manual duties | Most of the ISR is organisational. Nothing lists those duties, assigns them or records that they were done | none |

**What the sources require, and do not.** ISR v3.1 binds Dubai Government Entities. Its one AI clause is 2.7.5 (privacy
controls for automated response systems), with synthetic data and masking at 2.7.3 and 2.7.4. It has no human-accountability
clause for AI: that duty comes from the UAE Charter, the Digital Dubai toolkit, ISO/IEC 42001 and NIST. It sets no numbers
for session timeout, log lifetime or RPO/RTO, so each must be a declared value. It names MFA only for data-centre access
(6.10.2). PDPL, per secondary sources, excludes government data and government entities, so a government build answers to
the Dubai Data Law (cited at ISR 2.7.1) and PDPL applies to the supplier's own processing.

## Approach

### Six rules

1. **A profile, not a new default.** `dubai-gov` is opt-in. A repository with no profile is judged exactly as today.
2. **One catalogue, one row per obligation.** Everything else is generated from it: docs, portal checklist, evidence pack.
3. **Every row is one of three classes.** There is no fourth class called "documented".
   - **Enforced:** a hook, CI job or the runtime refuses.
   - **Verified:** a check reads real content or wiring and fails.
   - **Attested:** a named person signs for it with evidence and an expiry.
4. **Decoupled by contract.** A new `contract/compliance/v1`. A tenant holds declarations and its own answers, never
   framework code or paths.
5. **Adopted by the repository's own config.** `compliance` in `.agenticframework/process-gates.json`, read at each commit,
   so history is never re-judged. It ratchets: the mode cannot be weakened without `agentsmith approve`.
6. **Split a claim, never relabel it.** Where a control is Met for less than its name says, the true part keeps the ID and
   the rest becomes a new control marked Gap.

### Three layers

| Layer | Who it binds | How it is held |
|---|---|---|
| AgentSmith itself | The framework, CLI, portal, release pipeline | Provider controls (`subject: provider`), AgentSmith's own CI, and AgentSmith adopting the profile on itself |
| Governed apps | Each repository on the profile | Repository controls (`subject: repository`), hooks, CI, deploy gates and the runtime |
| Operating organisation | The entity and its supplier | Attested rows, in the portal and in the documents |

### How an app is held, stage by stage

| Stage | Mechanism | What the profile adds |
|---|---|---|
| Scaffold | `tenant init --profile`, `tenant adopt --profile`, `agentsmith sync` | Declarations, compliance rules in every IDE file, hooks armed |
| Design | Edit gate and the rules registry | Three extra pillars: P17 Data classification and boundary, P18 Human accountability, P19 Regulatory touchpoint |
| Build | Commit and stop gates, pillars a script can check | `P18-hitl-wiring`, `P17-boundary`, sign-off Group 8 · Regulated AI |
| CI | `security check`, `compliance check --stage ci` | New repository controls; only a pass passes |
| Release | `cd-production.yml`, `tenant promote` | `compliance check --stage production` blocks on a failed control or a missing or expired attestation; fails closed |
| Run | Gateway, base workflow, Ops contract | Boundary refusal, named HITL, required moderation, AI marker, decision record |
| Operate | Portal | Live checklist, expiries, access review, incidents, stop control |

Two limits stated up front. The runtime guardrails are Python, so a TypeScript or Go app reaches them through a local sidecar
(`agentsmith runtime serve`, `contract/runtime/v1`). Edit-time hooks cover
two of six IDEs; the commit and CI gates catch the rest, and they bind only if branch protection requires them, which is an
attested row.

### The spine

`contract/compliance/v1/catalogue.json`, one row per obligation:

```json
{
  "id": "OB-SESSION-IDLE",
  "title": "Idle sessions end",
  "refs": {"desc_isr": ["5.2.3.6"], "nist_ai_rmf": [], "iso42001_theme": [], "uae_charter": [], "dubai_ethics": []},
  "layer": "provider",
  "class": "enforced",
  "phases": ["operate"],
  "mechanism": "SEC-SESSION-001",
  "owner_role": "administrator",
  "recurrence_days": null,
  "instructions": "What to do, in our own words.",
  "evidence": "What proves it.",
  "blocks": ["production"],
  "profiles": ["dubai-gov"]
}
```

**Declarations:** `.agenticframework/compliance.json` (JSON because hooks have no pyyaml): profile, data classes, residency
boundary, session and retention values, RPO/RTO, languages, named accountable owner per agent. Environment variables may
tighten these and never loosen them.

**Attestations.** One record shape: obligation, app, named actor, role, evidence reference and digest, date, expiry, note.
Two ways to write it, one view:

- `agentsmith attest <OB-ID> --evidence <ref>` asks at `/dev/tty` and appends to `.agenticframework/attestations.jsonl`,
  exactly as `agentsmith approve` does, so an agent cannot sign. This is the route for repositories with no portal.
- The portal, by a signed-in person holding `compliance.attest`, recorded in `compliance_attestations` and `audit_log`.

Repository records reach the portal through the Dev record. Portal records reach the repository through
`agentsmith compliance export`, run at each production deploy. The latest valid record per obligation wins. In the portal only a
`compliance_officer` can sign. At a terminal the signer states a role, and the record shows who signed and as what.

**Documents.** `docs/UserManual.md` and `docs/uae-regulatory.md` carry generated sections between
`BEGIN/END agentsmith:compliance` markers, on the pattern of the gates table in `docs/validation-checklist.md`, with a drift
check in CI. A governed app gets `docs/compliance-checklist.md`, registered as a new artifact type, holding every row, its
instructions and its current state.

### Slices

Size is S, M or L. Each slice ends with a real run, and its proof is listed. Releases are additive MINORs after CR.

#### Phase 0: correct the record (release 4.0.2)

- **CR1 (S) OWASP 2025.** Renumber `frameworks.owasp` in the registry and the map to LLM01–10:2025; add LLM07 and LLM08 rows.
  Proof: a test pins the ten names; evidence pack regenerated.
- **CR2 (S) Split the overclaims.** `SEC-HITL-001` keeps "the workflow pauses"; new `SEC-HITL-002` "a named person decided" is
  Gap. `SEC-SOV-001` keeps "the shipped template stays in-border", subject provider; new `SEC-SOV-002` "this app stays in-border"
  is Gap. `docs/uae-regulatory.md` human oversight becomes Partial.
- **CR3 (S) Wording.** README "stay compliant" and "UAE / Sovereign Compliance"; `DemoScript.md` Ch 6; add ISR, the Dubai AI
  Security Policy, 34/2021, 25/2018, the Charter and Digital Dubai to `docs/uae-regulatory.md`; state the PDPL government
  exclusion; flag the unconfirmed Annex A identifiers in `docs/agentic-42001-coverage.md`.

#### Phase 1: the spine (release 4.1.0)

- **SP1 (L) Contract and CLI.** `contract/compliance/v1` (schemas, protocol, cases, fixture), the first catalogue, the profile,
  `agentsmith compliance status | check | export`, the `.githooks/process-gate compliance` launcher, the ratchet. Proof:
  `agentsmith conformance --port compliance`.
- **SP2 (M) Attestation.** `agentsmith attest`, TTY-only, added to the refused shell surface and the edit gate's denied files.
  Proof: throwaway-repo tests with no terminal.
- **SP3 (M) Profile at design time.** A `dubai-gov` registry generated from `templates/agent-rules.yaml`, P17–P19, Group 8 in
  `docs/review-levers.md`, `docs/design-review-checklist.md` and `docs/validation-checklist.md`, rules in every IDE file,
  `tenant init` and `tenant adopt --profile`.
- **SP4 (M) Generated documents.** Markers, renderer, drift check, the tenant artifact type.
- **SP5 (L) Portal checklist.** Schema migration; role `compliance_officer`; permissions `compliance.read` and
  `compliance.attest`; a Compliance page per app, filtered by phase under Dev and Ops, with an Administration rollup across
  apps; overdue and expiring rows shown; read endpoint for the deploy gate. Proof: role-matrix tests, `npm run test:db`, and
  a browser walk-through.

#### Phase 2: human accountability (release 4.2.0)

- **HA1 (M) Decision record.** Additive in `contract/ops/v1`: `hitl_pending` and a signed decision carrying actor, role, time,
  rationale and payload digest. New signal `hitl_decide`. On the profile, the bare-boolean signals are refused.
- **HA2 (L) Portal queue.** `/ops/hitl` shows what is asked, why, the model, the citations and the risk. Approve or reject with a
  rationale, under `ops.hitl`. The person who started a run cannot decide it. A timeout escalates.
- **HA3 (S) Audit every human action.** Replay, discard, approvals, role and token changes.
- **HA4 (M) Wiring check.** Each `needs_hitl` action in the agency manifest must reach a real gate (`P18-hitl-wiring`, static),
  and each agent names an accountable owner. Closes backlog gap 14.
- **HA5 (M) Stop control.** `ops.stop`; stop a run or an app; a flag in the worker's database, set by the portal over the signed webhook or
  by `agentsmith ops stop`; the gateway refuses while halted; `agentsmith mode off` gains its meaning. Closes backlog gap 4.

#### Phase 3: AgentSmith's own portal (release 4.2.x, default-on where harmless)

- **PH1 (M) Sessions.** Idle and absolute limits, separately configurable. ISR 5.2.3.6.
- **PH2 (M) Sign-in.** Throttle and lockout (5.2.3.7). On the profile, Basic auth refuses to start and the identity provider's
  `amr` or `acr` claim is checked for MFA.
- **PH3 (M) Audit.** Migration widens event types; sign-in, sign-out, failure, denial, export; the harness row `SEC-AUDIT-002` is bound to the
  Postgres job that already verifies the triggers in `self-test.yml`; signed export to a SIEM or object store; declared retention (6.9.6, 6.9.7).
- **PH4 (S) Access review.** Export grants per app; the review is an attested row with a period (5.2.1.12).
- **PH5 (S) Headers and transport.** CSP, HSTS, frame-ancestors with the widget's exception, nosniff; `sslmode` checked on the
  profile; session secret strength checked at boot.

#### Phase 4: what each governed app must do (release 4.3.0)

- **AR1 (L) Residency.** `SEC-SOV-002` walks the app's own registry and degrade ladder and every declared sink (Postgres, Phoenix,
  blob store, Redis, embeddings, portal) against the declared boundary. The gateway and exporters refuse out-of-boundary
  endpoints for classified data. An exception is a recorded deviation. ISR 2.7.2, 13.2.1.
- **AR2 (M) Data class per request.** Gateway input and span attribute; masking or synthetic data by class. ISR 2.7.3–2.7.5.
- **AR3 (M) OWASP 2025.** LLM07 canary and leakage suite; LLM08 `tenant_id` column with a mandatory filter and a cross-tenant
  test; LLM09 grounding required on declared routes through `citations_grounded`; LLM10 per-user limits.
- **AR4 (M) Arabic.** Prompt-guard patterns; Arabic injection, PII, fairness and adversarial cases; a declared named-entity hook for
  names; the harness fails when `languages` includes `ar` and the suites hold no Arabic.
- **AR5 (M) Content duties.** Moderation `required` on the profile; a gateway AI marker and widget disclosure (`SEC-DISCLOSE-001`,
  also EU AI Act Article 50); fairness a hard gate on the profile.
- **AR6 (L) Explanation.** A decision record per run: input digest, model, prompt digest, citations, commit, human. A portal view
  for one decision. Digital Dubai explainability; backlog gap 2.
- **AR7 (M) Retention and subjects.** Declared retention per store, `agentsmith ops purge`, export and erasure by subject reference with
  legal hold, for builds where PDPL or the Dubai Data Law requires it.
- **AR8 (M) Incidents.** A portal register linked to dead letters and runs, with a report export. ISR domain 4. Withdrawing published
  AI content uses HA5.

#### Phase 5: supply chain and continuity (release 4.4.0)

- **SC1 (M) AgentSmith's own pipeline.** `pip-audit`, `npm audit`, SAST, SBOM, Dependabot, signed release evidence. ISR 8.6.1; backlog gap 5.
- **SC2 (M) Apps.** A supply-chain job in the workflow templates (`SEC-SUPPLY-001`); declared MCP servers and tool-definition hashes.
  Backlog gap 3.
- **SC3 (L) Continuity.** Postgres backup job and restore script for Compose and Helm, an HA option, `agentsmith ops restore-drill` writing
  evidence, and `SEC-BCP-001`: RPO/RTO declared and a drill younger than the declared period. ISR 7.3, 7.4.

#### Phase 6: evidence and proof (release 4.5.0)

- **EV1 (M) Evidence by clause.** Pack gains `dubai_isr.md`, `uae_charter.md`, `dubai_ethics.md`, and state per row: class, result, evidence.
- **EV2 (S) Mappings.** NIST AI 600-1 GenAI Profile and subcategories; ISO/IEC 42001 Annex A and a draft Statement of Applicability, once a
  licensed copy is in hand.
- **EV3 (M) Scratch tenant.** `python-fastapi` on the profile in `.github/scratch-tenants`, with mutation suites proving each new check fails.
- **EV4 (S) Adoption.** AgentSmith adopts the profile on itself. Other tenants move only on the owner's word.

### Attested checklist: first catalogue

Listed in the portal and the documents. Owner roles are suggestions for the entity to confirm.

| Obligation | Reference | Phase | Owner | Repeat |
|---|---|---|---|---|
| Confirm the current ISR version and which entity's policies apply | ISR 11.1 | Design | Compliance | Yearly |
| Read and map the Dubai AI Security Policy | DESC | Design | Compliance | Yearly |
| Counsel opinion: PDPL or Dubai Data Law; 34/2021 exposure | Decree-Laws 45/2021, 34/2021 | Design | Legal | On change |
| Decide whether a temporary licence is needed; record its conditions and expiry | Decree-Law 25/2018 | Design | Legal | On change |
| Classify the data and approve the residency boundary | ISR 2.3, 2.7.2 | Design | Data owner | Yearly |
| Complete the Digital Dubai ethics self-assessment | Digital Dubai | Design, Operate | AI owner | Yearly |
| Map the app to the Charter's 12 priorities | UAE Charter | Design | AI owner | Yearly |
| Fill the risk register truthfully and accept residual risk | ISR 3.3, 3.4; NIST MAP | Design | Risk owner | Half-yearly |
| Name an accountable person for each agent | Charter 6, 7; ISO theme 5 | Design | AI owner | On change |
| Require the gates through branch protection | ISR 8.5.1 | Build | Repo admin | Quarterly |
| Independent code review and penetration test | ISR 8.6.1, 8.6.2 | Build, Operate | Security | Yearly |
| Security sign-off before production | ISR 8.7.2 | Deploy | Security | Per release |
| CSP is DESC-approved; contract covers residency, encryption, no data ownership | ISR 13.2.4 | Deploy | Procurement | Yearly |
| Encryption at rest and key custody | ISR 8.8 | Deploy | Infrastructure | Yearly |
| Clock synchronisation across systems | ISR 6.9.8 | Deploy | Infrastructure | Yearly |
| Review privileged and user access | ISR 5.2.1.12, 5.6 | Operate | Administrator | Quarterly |
| Review logs and feed the SOC | ISR 6.9.1, 6.9.5 | Operate | SOC | Monthly |
| Business impact analysis and continuity plan | ISR 7.1, 7.2 | Operate | BCM owner | Yearly |
| Run and record a DR exercise | ISR 7.3.4, 7.5 | Operate | BCM owner | Yearly |
| Incident plan, including withdrawing AI content | ISR 4.1; 34/2021 | Operate | Security | Yearly |
| Train reviewers on what a HITL decision means | ISR 10.2; Charter 11 | Operate | AI owner | Yearly |
| Physical, personnel and remaining ISR domains | ISR 9, 10, 11, 12 | Operate | Entity | Yearly |

### Order

Phase 0 first, because the claims are already public. Then the spine, because every later slice registers its rows in it.
Human accountability next, as the largest gap and the strongest differentiator. Phases 3 to 6 follow.

### Owner decisions (2026-11-08)

1. **Hard fail on the profile: yes.** A failed control or expired attestation blocks production, with exceptions only through
   `agentsmith approve`.
2. **Basic auth on the profile: refused.** SSO is required.
3. **The portal may be down as long as logging to the database works.** A tenant app raises an error and stops the affected function when its record cannot be written.
4. **Attestation:** a new `compliance_officer` role, separate from every delivery role.
5. **Source material:** proceed on the current draft. The aim is to help an enterprise become ready for a DESC certification. Until the Dubai AI
   Security Policy and a licensed ISO/IEC 42001 are in hand, those rows stay Attested or unmapped.

### Decision 3: what "logging works" has to mean

Today a worker's records take three paths. Dead letters are written straight to Postgres. Run status goes through the portal
(`/api/ops/ingest`) and is lost when the portal is down, because `agentsmith/ops_contract.py` fails open with no retry. Audit events go
through `/api/audit/append` and fall back to a local file on that machine, `local-audit-fallback.log`, unsigned and outside the database. The owner's rule needs the write to stop depending on the portal. Built in HA1 and HA5:

- **An outbox in the database the worker already uses.** Audit and run records go to an append-only table first, and a forwarder drains
  them to the portal when it is up, idempotently.
- **No write, no high-impact action.** On the profile, a worker that cannot write the record does not take a gated action or a call on
  classified data. The dependency moves from the portal to the database.
- **The stop flag lives in that database too.** The portal sets it over the signed webhook; `agentsmith ops stop` sets it at a terminal when
  the portal is down. Workers read the database, so no portal lease is needed.
- **While the portal is down,** runs continue and gates stay parked until someone can decide them; a timeout routes to the dead-letter queue.
- **Integrity.** The HMAC key is the portal's today, so outbox records need a per-app signing key or a hash chain, and the same refuse-update
  triggers.

## Pillars

- P1 applies — this file records the measured gaps in Problem and the plan in Approach; each slice gets its own design under `.agent-rfc/designs/`.
- P2 applies — `contract/gate/v1/protocol.md` is the shape `contract/compliance/v1` copies, and `agentsmith conformance` is extended rather than duplicated.
- P3 applies — `agentsmith/llm_gateway.py` is where boundary, marker and decision-record spans are emitted; each slice names its span.
- P4 applies — `scripts/test/test_security_contract.py` is the model; every new check has cases, a test and a mutation suite that proves it fails (EV3).
- P7 n/a — no code in this design; each slice answers it for its stack.
- P8 applies — `contract/telemetry/v1` stays the wire; new attributes are additive and listed in each slice.
- P9 n/a — no orchestration in this design; HA1 and HA5 answer it for workflows.
- P10 n/a — no model call in this design.
- P11 applies — `portal/lib/devIngest.ts` is the pattern: attestations and decisions from outside the portal are validated whole or refused.
- P12 applies — `scripts/send_dev_record.py` is the pattern: tokens are read by name from the environment; signing keys never enter a committed file.
- P13 applies — `.agenticframework/approvals.jsonl` is the pattern for TTY-only attestation; the mode ratchets as `scripts/gate_pillars.py` does, and SP2 adds the new files to the denied surface.
- P14 applies — `contract/security/v1/fixture.json` is the model: the catalogue's fixture carries what its decisions depend on, and SP4's drift check holds generated documents to the catalogue.
- P15 applies — `contract/gate/v1/protocol.md` separates "declared none" from "could not run"; an unreachable portal at deploy is "could not run" and fails closed on the profile.
- P16 applies — `contract/gate/v1/providers.schema.json` lets a tenant pin each port; a repository leaves the profile only by a recorded deviation, and migrations are additive.

## Deviations

none

## Dependencies

none in this design. SC1 names its scanners and their transitive packages in its own design.

## Levers

- `declared-vs-enforced` — every obligation is Enforced, Verified or Attested, and the residency and HITL claims are split where they said more than the code does.
- `implemented-not-invoked` — a slice is done only when the scratch tenant on the profile runs it, and a mutation shows the check fails.
- `single-source-of-truth` — one catalogue generates the portal checklist, the documents and the evidence pack.
- `gate-integrity` — attestation is TTY-only or by a signed-in named person, and the profile cannot be weakened quietly.
- `small-verified-slices` — each slice has its own design, review and pull request.
- `failure-is-not-a-result` — an unreachable portal or an unrun check is never a pass.
