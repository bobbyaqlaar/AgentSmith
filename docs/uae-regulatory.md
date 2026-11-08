# AgentSmith for UAE — Sovereign & Regulated Agentic AI

AgentSmith is built for teams in the UAE, where agentic systems need to be aligned to **sovereign infrastructure**, **anti-bias law**, **mandatory human oversight**, **PDPL
privacy**, and **technical governance** — not optional ethics slides.

This page is AgentSmith’s UAE differentiator map: what the mandate requires,
what the framework already ships, and how to run it on UAE-aligned rails.

> **Disclaimer:** This document is a product/architecture mapping aid. It is
> **not legal advice**, **not a certification**, and **not a guarantee** of
> compliance with UAE law, the DESC Information Security Regulation, PDPL, Federal
> Decree-Law No. 34/2023, ISO/IEC 42001, or requirements of the UAE Authority for
> AI and Data. Engage qualified
> counsel and your compliance function before production use with national or
> personal data.

Full gap tracking and build triggers: `[docs/PRODUCT_BACKLOG.md](PRODUCT_BACKLOG.md)`
(UAE Regulatory gap register + Future Phase).

---



## Which instruments apply

A government build answers to more than the five mandates below. Which of these binds a given
project is a question for the entity and its counsel. Summaries are ours; read the source.

| Instrument | What it is | What it asks of a build | Where AgentSmith stands |
|---|---|---|---|
| **DESC Information Security Regulation** (v3.1) | Binds Dubai Government Entities; a supplier meets it through the entity. 13 domains | Access, sessions, logging, secure development, data location, continuity. It leaves timeouts, log lifetimes and RPO/RTO to the entity | Board below |
| **Dubai AI Security Policy** (DESC, 2024) | Guidance to Dubai government entities that build or consume AI | Not yet mapped: the text has not been obtained | A signed obligation on the profile (`OB-AI-SECURITY-POLICY`) |
| **PDPL**, Federal Decree-Law No. 45/2021 | In force. Published commentary reads Article 2 as excluding government data and government entities, and free zones with their own law. Executive regulations are reported as still unissued | Applies to a private supplier's own processing. A government project looks to the Dubai Data Law, which the ISR cites | Partial; see the PDPL mandate below |
| **Federal Decree-Law No. 34/2021** (rumours and cybercrimes) | Criminal law, including false news and rumours published online (Article 52, per commentary) | An application publishing AI text needs grounding on official matters, moderation and a way to withdraw content | On the profile: moderation is required, grounding is a signed obligation, and Stop and the incident register withdraw content |
| **Federal Decree-Law No. 34/2023** (discrimination and hatred) | Criminal law | Fairness evidence | Partial; see the bias mandate below |
| **Federal Decree-Law No. 25/2018** (projects of future nature) | Enables temporary licences for projects no existing law covers (Cabinet Resolution 14/2019) | Decide whether a licence is needed and keep to its conditions | A signed obligation on the profile (`OB-LICENCE`) |
| **UAE Charter for the Development and Use of AI** (2024) | National policy of 12 priorities | Safety, bias, privacy, transparency, human oversight, governance, among others | Partial on those six; the rest is the organisation's |
| **Digital Dubai AI ethics principles and self-assessment** | Recommended, not compulsory. Fairness, accountability, transparency, explainability | Complete the self-assessment | On the profile: fairness is a hard gate, and the portal keeps a decision trail per run. Explaining it to the person affected is a signed obligation |

OWASP, NIST AI RMF and MITRE ATLAS are in [`docs/security-framework-map.md`](./security-framework-map.md); ISO/IEC 42001
is in [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md).

---

## 1. Sovereign Infrastructure Mandate

**The Rule:** Agentic AI must not depend on unconstrained global cloud
inference for national data. Processing and model hosting belong **within UAE
borders** — e.g. sovereign AI clouds (such as platforms associated with G42)
and models from the Technology Innovation Institute (TII), including the
**Falcon** series.

**The Action:** Process national data and host AI models in-country to meet
data-residency expectations.

### AgentSmith today — **Partial (pattern ready)**


| Capability                   | How it helps                                                                                                                                     |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Local / air-gapped inference | `AI_STACK_MODE=local` routes calls to Ollama (`OLLAMA_BASE_URL`, default `http://localhost:11434`) — prompts stay on the machine                 |
| UAE sovereign starter pack   | [`templates/uae-sovereign/`](../templates/uae-sovereign/) — Falcon `models.yaml`, env example, residency checklist                               |
| On-prem / air-gapped deploy  | `templates/onprem-deploy/` (Compose or Helm) for in-border clusters                                                                              |
| Pluggable providers          | `agentsmith/llm_gateway.py` + `agentsmith/provider_dispatch.py` — point the gateway at **any** OpenAI-compatible or cloud-adapter endpoint you control |
| Dedicated tenant isolation   | `tenant.isolation: dedicated` + K8s worker pools for stronger runtime separation                                                                 |


**Not claimed:** a formal partnership with G42 or TII, or a pre-certified
“UAE sovereign SKU.”

### What stays where

Python, TypeScript and Go apps can all go on the profile; the last two reach the guards through a local sidecar.

Tracing is self-hosted Phoenix, and evals are AgentSmith's own runner with a judge model you choose: neither is a hosted service. The UAE template points the judge at Falcon 3 on in-border Ollama.
LangChain and LangGraph are libraries, used only by an optional developer tool, and have no bearing on where data goes. What decides residency is which endpoint is called and where the stores sit,
and on the compliance profile each route is checked.

### How to run (pattern, not partnership)

**Starter pack:** [`templates/uae-sovereign/`](../templates/uae-sovereign/) —
example tenant `models.yaml` (HF Falcon live-verify + Ollama/sovereign paths),
`env.example`, and a **data residency checklist**. Copy into the tenant repo;
replace placeholders.

1. **In-border compute** — deploy workers, Phoenix, Postgres, and the Ops
   Portal on UAE-region or on-prem infrastructure (`templates/onprem-deploy/`,
   or your sovereign cloud’s Kubernetes).
2. **Falcon 3 via in-border Ollama (Pattern A)** — `ollama pull falcon3:3b`
   and `falcon3:1b`; `AI_STACK_MODE=local` + `OLLAMA_BASE_URL`. Live-verified
   2026-07-10. Smoke: `scripts/verify_sovereign_endpoint.py`.
3. **Sovereign cloud OpenAI-compatible API (Pattern B)** — set
   `UAE_SOVEREIGN_API_BASE` / key and enable `sovereign_api`.
4. **Optional HF Hub ids (Pattern C)** — research only; router does not host
   the TII Falcon-E / H1 ids. Prefer `falcon3:*` for gateway.
5. **Do not** send national data through hybrid mode to non-UAE frontier APIs
   (including public Hugging Face) unless counsel has approved that path.

See docs/UserManual.md (local vs hybrid mode, on-prem deploy) and docs/DESIGN.md › LLM Gateway (Production)
(LLM Gateway / provider adapters).

---



## 2. Strict Bias and Fairness Enforcement

**The Rule:** Algorithms must not discriminate against individuals or groups.
UAE enforcement includes laws against hate and bias such as **Federal
Decree-Law No. 34/2023**.

**The Action:** Run routine bias audits on training/eval data and agent
behaviour before launch — and keep evidence.

### AgentSmith today — **Partial (suite shipped)**


| Capability                         | Status                                                                |
| ---------------------------------- | --------------------------------------------------------------------- |
| Golden evals + LLM judge scorecard | **Shipped** — correctness / tool accuracy / latency gates             |
| Fairness / bias suite              | **Shipped (v1)** — `run-evals.py --suite fairness` + paired fixtures  |
| Audit artifacts for other controls | **Shipped** — HMAC audit log, Phoenix traces, promote gates           |


**How to run:** copy `fixtures/fairness_evals_base.json` →
`.agent-rfc/fixtures/fairness_evals.json` (or rely on framework base
fallback), set threshold in tenant `.env`, then:

```bash
# tenant .env
FAIRNESS_FAIL_BELOW=0.80

python3 scripts/run-evals.py --suite fairness
```

CI: `eval-fairness.yml` runs warn-only by default; set repo variable
`FAIRNESS_EVALS=required` (and optionally `FAIRNESS_FAIL_BELOW`) for a hard
gate. Extend pairs for your domain.

---



## 3. Human-in-the-Loop Oversight

**The Rule:** Autonomous agents must not have unchecked control over critical
actions. Government frameworks expect **human oversight** and a clear
accountability trail for agentic decisions.

**The Action:** Install **stop gates** so high-impact actions (permits,
financial transfers, irreversible state changes) require human approval before
they go live.

### AgentSmith today — **Partial (named decisions on the compliance profile; not by default)**


| Mechanism                                    | Role                                                                                    |
| -------------------------------------------- | --------------------------------------------------------------------------------------- |
| `BaseAgentWorkflow.run_with_hitl_gate`       | Explicit pause when an activity sets `needs_hitl` — workflow waits on a Temporal signal |
| `run_with_recoverable_step` + Ops Portal DLQ | Failed high-impact steps park alive; human edits payload, Replay/Discard                |
| HITL promotion loop                          | Production failures → golden tests → guardrails                                         |
| HMAC-signed audit log                        | Append-only, tamper-evident record of admin/bypass/config actions (docs/DESIGN.md › Enterprise Install and Compliance Pack)        |
| Encrypted HITL blobs                         | Full payload preserved for compliance review under redaction profiles                   |


**How to use for UAE-critical actions:** mark permit issuance, payments, and
similar activities with `needs_hitl` (or route failures through recoverable
steps). Do not auto-approve high-impact tools in tenant code. Point auditors
at Phoenix spans + Ops Portal audit events — not a slide saying “we have HITL.”

**On the `dubai-gov` compliance profile** (`agentsmith compliance enable`): a gate accepts only a named, signed decision made in
**Ops › Human decisions**, a person cannot decide their own request, and every action in the agency manifest must reach such a gate. A
person can stop a run or the app from the portal, or with `agentsmith ops stop` when the portal is down. If the record of an action
cannot be written, that function raises an error and stops. **Off the profile**, a decision is still a bare approve or reject.

---



## 4. Data Privacy Alignment (PDPL)

**The Rule:** Agents need data, but **UAE PDPL** (and related privacy
expectations) forbid feeding personal or sensitive data into an agent without
consent and strong protections.

**The Action:** Mask or anonymize personal information (names, **Emirates ID**
numbers, contact data, etc.) during the agent’s decision-making path — not only
in logs after the fact.

### AgentSmith today — **Partial (pre-call + post-call)**

The default scrubbers cover Emirates ID, email, phone and cards. **Names are not scrubbed**, so
masking them needs a custom guardrail, which the compliance profile requires. On a government project, check first whether PDPL applies
at all (see **Which instruments apply**).


| Capability                                | Status                                                                                       |
| ----------------------------------------- | -------------------------------------------------------------------------------------------- |
| Post-call trace redaction / anonymization | **Shipped** — `agentsmith/trace_redactor.py`, CD redaction compliance checks                    |
| Encrypted HITL blob storage               | **Shipped** — full payload for review without leaving cleartext in traces                    |
| Pre-call PII scrub before model invoke    | **Shipped** — `agentsmith/input_guardrail.py` in `llm_gateway.complete()` (Emirates ID, email, phone, cards; pluggable) |
| Prompt injection guard + adversarial eval | **Shipped** — `agentsmith/prompt_guard.py` + `run-evals.py --suite adversarial` (`SEC-PROMPT-001` / `SEC-ADV-001`) |
| Security harness evidence pack            | **Shipped** — `run-security-checks.py --evidence-pack` ([`docs/security-framework-map.md`](./security-framework-map.md)) |


**How to run:** staging/production default `INPUT_GUARDRAIL=default` (or unset).
Development defaults to `off`. Force on: `export INPUT_GUARDRAIL=default`.
Custom: `register_input_guardrail(fn)` + `INPUT_GUARDRAIL=custom`.
Also: `PROMPT_GUARD=default` (or `strict`); harness probes as `SEC-PII-001`.

Keep national/personal datasets on in-border stores (see §1).

---



## 5. Compliance with Oversight Bodies

**The Rule:** Governance is moving from abstract ethics to **mandatory
technical standards**. The **UAE Authority for AI and Data** monitors
compliance; frameworks such as **ISO/IEC 42001** are the architectural bar.

**The Action:** Embed governance into the AI architecture from day one —
controls, logs, and promote gates — rather than bolting them on after launch.

### AgentSmith today — **Partial (governance substrate shipped)**


| Capability                            | Status                                                        |
| ------------------------------------- | ------------------------------------------------------------- |
| Enterprise pack                       | GPG-signed hooks, MDM deploy, break-glass with audited bypass |
| Immutable audit log + RBAC Ops Portal | Evidence substrate for oversight reviews                      |
| Eval / redaction / promote gates      | Controls in the delivery path (Delivery Model needs 2–3)      |
| Multi-framework security harness      | **Shipped** — [`docs/security-framework-map.md`](./security-framework-map.md) + strict CI |
| ISO/IEC 42001 control map             | **Shipped (thematic)** — [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md) |
| Authority-facing artifact checklist   | **Shipped** — evidence checklist in ISO map + harness pack    |


AgentSmith’s bet: **compliance is demonstrated through logs and artifacts**
(audit events, eval scorecards, redaction check output, HITL records) — the
same Delivery Model stance as the enterprise consultant review. Use the
ISO/IEC 42001 control map + evidence checklist when an oversight body asks
for technical standards alignment (still not a certificate).

---



## Quick status board


| #   | Mandate                     | Status  | Primary pointer                                                          |
| --- | --------------------------- | ------- | ------------------------------------------------------------------------ |
| 1   | Sovereign infrastructure    | Partial | [`templates/uae-sovereign/`](../templates/uae-sovereign/); this doc §1    |
| 2   | Bias & fairness             | Partial | `run-evals.py --suite fairness`; FIXES Data Bias & Fairness              |
| 3   | HITL stop-gates             | Partial | `run_with_hitl_gate`; named decisions on the compliance profile (`SEC-HITL-002`) |
| 4   | PDPL / PII in decision path | Partial | `input_guardrail.py` + `prompt_guard.py` + `trace_redactor.py`; harness `SEC-PII-*` |
| 5   | Oversight / ISO 42001       | Partial | [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md); [`docs/security-framework-map.md`](./security-framework-map.md); enterprise pack |


---



## Readiness against the DESC Information Security Regulation

An entity is assessed against the ISR, not a product. This is what AgentSmith contributes, by clause of v3.1. The ISR has
no human-accountability clause for AI: its AI clause, 2.7.5, concerns privacy controls. That duty comes from the UAE Charter,
the Digital Dubai principles, ISO/IEC 42001 and NIST.

| Area | Clause | What ships | What does not | Status |
|---|---|---|---|---|
| Access control | 5.2.1, 5.2.3.7 | Eight roles per app. On the profile: SSO required, multi-factor checked from the identity token. Failed-sign-in lockout, access-review export | Basic-auth lockout is per process. The review itself is a person's duty | Met on the profile |
| Session handling | 5.2.3.6 | Separate idle and absolute limits; revocation on logout | Connection-time limits (5.2.3.8) are the identity provider's | Met on the profile |
| Logging and accountability | 6.9 | Signed audit log the database will not let you edit, covering sign-ins and human actions; a chained record in the worker's database; signed export for a SIEM | Basic-auth failures are throttled, not logged. Clock sync and log review are operational | Met on the profile |
| Secure development | 8.1, 8.2, 8.5, 8.6, 8.7 | Design, review and sign-off on every commit; dependency scan, SAST and SBOM; security headers | Penetration testing is a person's duty | Strong |
| Input and output integrity | 8.3 | Structured-output validation; prompt guard and PII scrub, with Arabic cases | Heuristics can be evaded. Names need a guardrail you supply | Partial |
| Data location | 2.7.2, 13.2.1 | On the profile: the app's routes and stores are checked against its boundary. The gateway, eval router, developer pipeline, trace export and notifications refuse outside it | A store's real location is what you declare it to be. CI on GitHub-hosted runners is outside any UAE boundary: a signed obligation (`OB-CI-BOUNDARY`) | Partial |
| Business continuity | 7.2, 7.3, 7.4 | Backup and restore scripts, a Helm job, and a recorded restore drill the deploy gate checks. RPO/RTO declared | The plan, and alternative processing, are the entity's | Partial |

The remaining domains (governance, risk, incident planning, physical, personnel, compliance and assurance) are the entity's: the profile
lists each as an obligation a named person signs, in **Ops › an app › Compliance checklist** and in the manual. The aim is to help an enterprise
prepare for a DESC assessment. The profile does not replace that assessment.

---

## Related docs

- [`docs/PRODUCT_BACKLOG.md`](PRODUCT_BACKLOG.md) — remaining gaps (P12 security harness ✅)
- [`templates/uae-sovereign/`](../templates/uae-sovereign/) — Falcon models.yaml, env, residency checklist
- [`docs/security-framework-map.md`](./security-framework-map.md) — OWASP · NIST · ATLAS · ISO crosswalk + harness
- [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md) — ISO/IEC 42001 thematic map + evidence checklist
- [`README.md`](../README.md) — Ten Pillars, HITL, enterprise layer
- [`docs/UserManual.md`](UserManual.md) — Install, modes, on-prem, portal, security harness
- [`docs/DESIGN.md`](DESIGN.md) — §27 redaction, §29 gateway, §30 enterprise/compliance
- [`enterprise/README.md`](../enterprise/README.md) — Hook bundles, bypass policy

