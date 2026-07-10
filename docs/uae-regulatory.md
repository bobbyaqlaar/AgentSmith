# AgentSmith for UAE — Sovereign & Regulated Agentic AI

AgentSmith is built for teams in the UAE, where agentic systems need to be aligned to **sovereign infrastructure**, **anti-bias law**, **mandatory human oversight**, **PDPL
privacy**, and **technical governance** — not optional ethics slides.

This page is AgentSmith’s UAE differentiator map: what the mandate requires,
what the framework already ships, and how to run it on UAE-aligned rails.

> **Disclaimer:** This document is a product/architecture mapping aid. It is
> **not legal advice**, **not a certification**, and **not a guarantee** of
> compliance with UAE law, PDPL, Federal Decree-Law No. 34/2023, ISO/IEC 42001,
> or requirements of the UAE Authority for AI and Data. Engage qualified
> counsel and your compliance function before production use with national or
> personal data.

Full gap tracking and build triggers: `[FIXES_AND_CLEANUP.md](../FIXES_AND_CLEANUP.md)`
(UAE Regulatory gap register + Future Phase).

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
| Pluggable providers          | `runtime/llm_gateway.py` + `runtime/provider_dispatch.py` — point the gateway at **any** OpenAI-compatible or cloud-adapter endpoint you control |
| Dedicated tenant isolation   | `tenant.isolation: dedicated` + K8s worker pools for stronger runtime separation                                                                 |


**Not claimed:** a formal partnership with G42 or TII, or a pre-certified
“UAE sovereign SKU.”

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

See OPERATIONS.md (local vs hybrid mode, on-prem deploy) and SPECS.md §29
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

### AgentSmith today — **Met (core differentiator)**


| Mechanism                                    | Role                                                                                    |
| -------------------------------------------- | --------------------------------------------------------------------------------------- |
| `BaseAgentWorkflow.run_with_hitl_gate`       | Explicit pause when an activity sets `needs_hitl` — workflow waits on a Temporal signal |
| `run_with_recoverable_step` + Ops Portal DLQ | Failed high-impact steps park alive; human edits payload, Replay/Discard                |
| HITL promotion loop                          | Production failures → golden tests → guardrails                                         |
| HMAC-signed audit log                        | Append-only, tamper-evident record of admin/bypass/config actions (SPECS.md §30)        |
| Encrypted HITL blobs                         | Full payload preserved for compliance review under redaction profiles                   |


**How to use for UAE-critical actions:** mark permit issuance, payments, and
similar activities with `needs_hitl` (or route failures through recoverable
steps). Do not auto-approve high-impact tools in tenant code. Point auditors
at Phoenix spans + Ops Portal audit events — not a slide saying “we have HITL.”

---



## 4. Data Privacy Alignment (PDPL)

**The Rule:** Agents need data, but **UAE PDPL** (and related privacy
expectations) forbid feeding personal or sensitive data into an agent without
consent and strong protections.

**The Action:** Mask or anonymize personal information (names, **Emirates ID**
numbers, contact data, etc.) during the agent’s decision-making path — not only
in logs after the fact.

### AgentSmith today — **Partial (pre-call + post-call)**


| Capability                                | Status                                                                                       |
| ----------------------------------------- | -------------------------------------------------------------------------------------------- |
| Post-call trace redaction / anonymization | **Shipped** — `runtime/trace_redactor.py`, CD redaction compliance checks                    |
| Encrypted HITL blob storage               | **Shipped** — full payload for review without leaving cleartext in traces                    |
| Pre-call PII scrub before model invoke    | **Shipped** — `runtime/input_guardrail.py` in `llm_gateway.complete()` (Emirates ID, email, phone, cards; pluggable) |


**How to run:** staging/production default `INPUT_GUARDRAIL=default` (or unset).
Development defaults to `off`. Force on: `export INPUT_GUARDRAIL=default`.
Custom: `register_input_guardrail(fn)` + `INPUT_GUARDRAIL=custom`.

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
| ISO/IEC 42001 control map             | **Shipped (thematic)** — [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md) |
| Authority-facing artifact checklist   | **Shipped** — evidence checklist in the same doc              |


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
| 3   | HITL stop-gates             | Met     | README HITL; `run_with_hitl_gate`; Ops Portal                            |
| 4   | PDPL / PII in decision path | Partial | `input_guardrail.py` + `trace_redactor.py`                               |
| 5   | Oversight / ISO 42001       | Partial | [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md); enterprise pack |


---



## Related docs

- [`FIXES_AND_CLEANUP.md`](../FIXES_AND_CLEANUP.md) — UAE gap register + Future Phase
- [`templates/uae-sovereign/`](../templates/uae-sovereign/) — Falcon models.yaml, env, residency checklist
- [`docs/iso-42001-control-map.md`](./iso-42001-control-map.md) — ISO/IEC 42001 thematic map + evidence checklist
- [`README.md`](../README.md) — Ten Pillars, HITL, enterprise layer
- [`OPERATIONS.md`](../OPERATIONS.md) — Install, modes, on-prem, portal
- [`SPECS.md`](../SPECS.md) — §27 redaction, §29 gateway, §30 enterprise/compliance
- [`enterprise/README.md`](../enterprise/README.md) — Hook bundles, bypass policy

