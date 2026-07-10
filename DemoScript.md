# AgentSmith — Live Demo Script

**Audience:** Technical evaluators, enterprise architects, engineering leads
(including UAE / regulated-industry stakeholders)
**Duration:** ~25 minutes
**Format:** Live screen share — no slides

**Disclaimer (say once if counsel is in the room):** AgentSmith maps controls to
UAE regulatory *themes* (sovereign residency, Federal Decree-Law No. 34/2023
bias rules, HITL, PDPL, ISO/IEC 42001-oriented governance). This is **not**
legal advice and **not** a certification.

**What this demo covers:**
1. The AgentSmith framework — install, IDE harness, Knowledge Graph, spec gate
2. GitHub Actions CI/CD — guardrails + eval gates (fairness, hallucination, TTFT)
3. The oil-price-demo app — Streamlit UI → live Temporal workflow on GCP
4. GCP operations — Cloud Run, Cloud SQL, Arize Phoenix, Ops Portal
5. **UAE compliance differentiator** — Falcon 3 sovereign path, PDPL scrub,
   bias suite, HITL / self-correction, audit evidence

**Tabs to open before you start:**
- `github.com/bobbyaqlaar/AgentSmith` → Actions tab + `templates/uae-sovereign/`
- `github.com/bobbyaqlaar/oil-price-demo` → Actions tab, then Code tab
- GCP Console → Cloud Run (project `agentsmith-500916`, region `us-central1`)
- Arize Phoenix at `localhost:6006` (or team server)
- Ops Portal: `https://agentsmith-portal-production-431995395208.us-central1.run.app`
- Terminal window at `/Users/mac/Documents/Bobby/Aqlaar/Apps/oil-price-demo`
- Optional second terminal at AgentSmith root for Falcon / eval smoke commands

---

## Part 1 — The Framework: One Install, Every Repo

**[~4 minutes]**

---

### Beat 1 · Open the AgentSmith GitHub repo

> **SHOW:** `github.com/bobbyaqlaar/AgentSmith` — repo root, README visible

> **SAY:** "Let me start with what AgentSmith actually is. It's a single install — one `curl` command — that provisions the complete AI agent lifecycle on your machine or team server. Once it's installed, every repository you work in from that point gets guardrails, observability, evaluation, and CI/CD. Automatically. On `git init`."

---

### Beat 2 · Show the install command in the README

> **SHOW:** Scroll to the Quick Start section — highlight the `curl` install line

> **SAY:** "This is the only command you run once. After this, every `git init` or `git clone` on this machine triggers the framework — no per-project setup, no copy-pasting config."

---

### Beat 3 · Show the AgentSmith repo structure

> **SHOW:** Click the repo file tree — expand `scripts/`, `runtime/`, `hooks/`, `portal/`, `templates/`

> **SAY:** "What the install lays down: the multi-agent scripts here in `scripts/`, the production runtime — gateway, HITL, tracing — in `runtime/`, git hook templates in `hooks/`, and the Ops Portal in `portal/`. The `templates/` folder holds the IDE config source of truth that gets written to every repo on checkout."

---

### Beat 4 · Show the auto-generated IDE harness

> **SHOW:** Navigate to `oil-price-demo` repo on local machine — open terminal, `ls -la` to show `.cursorrules`, `CLAUDE.md`

```bash
ls -la /Users/mac/Documents/Bobby/Aqlaar/Apps/oil-price-demo | grep -E "cursorrules|CLAUDE|agents"
```

> **SAY:** "Here's what fires automatically the moment you clone or init a repo. `.cursorrules` for Cursor. `CLAUDE.md` for Claude Code. The `.agents/skills/` directory for Antigravity. Stack-detected — this is a Python repo, so it got Python/FastAPI rules. Every IDE agent that opens this project starts with the right guardrails already in place. No manual prompt engineering. The harness is the environment."

---

### Beat 5 · Show the Knowledge Graph

> **SHOW:** Terminal in the oil-price-demo directory — run the command below

```bash
python3 -c "
import json
kg = json.load(open('/Users/mac/Documents/Bobby/Aqlaar/Apps/oil-price-demo/.agent-rfc/fixtures/knowledge_graph.json'))
nodes = kg.get('nodes', [])
edges = kg.get('edges', [])
print(f'Files mapped: {len(nodes)}  |  Import edges: {len(edges)}')
langs = {}
for n in nodes:
    l = n.get('language', 'unknown')
    langs[l] = langs.get(l, 0) + 1
print('By language:', '  '.join(f'{k}: {v}' for k, v in sorted(langs.items(), key=lambda x: -x[1])))
print()
print('Sample files and exported symbols:')
for n in nodes[:4]:
    syms = n.get('symbols', [])[:4]
    print(f'  {n[\"id\"]}  ->  {syms}')
"
```

> **SAY:** "Every commit rebuilds this — the Knowledge Graph. It's an AST-driven map of every file in the repo: language, exported symbols, last-modified timestamp, and import edges between files. 69 files, 19 dependency edges right now. When a new agent session starts cold, it queries this graph instead of re-reading the whole codebase. It knows which modules a file depends on, what symbols it exports, and the blast radius of any change before touching anything."

---

### Beat 6 · Show the spec gate

> **SHOW:** Open `.agent-rfc/` directory — show the fixtures and any RFC markdown files

> **SAY:** "Agents can't write a line of code until a spec exists here. That's Pillar 1 enforced at the environment level. The IDE agent reads this before planning anything. Requirements first, always."

---

### Beat 7 · Show the pre-commit hook firing

> **SHOW:** Terminal — run a quick `git log --oneline -5` in the oil-price-demo repo to show recent commits with guardrail output

```bash
git -C /Users/mac/Documents/Bobby/Aqlaar/Apps/oil-price-demo log --oneline -5
```

> **SAY:** "Every commit triggers the pre-commit guardrails — AST checks for empty exception handlers, commit message linting, and a Knowledge Graph rebuild. You saw the hook fire when we committed the code-review fixes earlier. Same rules locally as in CI."

---

## Part 2 — GitHub Actions: CI/CD Already Running

**[~4 minutes]**

---

### Beat 8 · Open AgentSmith Actions tab

> **SHOW:** `github.com/bobbyaqlaar/AgentSmith` → Actions tab — run list visible

> **SAY:** "Let's look at what CI/CD actually looks like for the framework itself. This is the AgentSmith repo — its own workflows, running against itself."

---

### Beat 9 · Open the CD Portal Deploy run

> **SHOW:** Click on the most recent successful **CD: Ops Portal Deploy** run (pick the latest green run from the list)

> **SAY:** "This is the Ops Portal CD run. Two jobs — staging then production. The staging job builds the Docker image, pushes it to GCP Artifact Registry, and captures the exact content-addressed digest. The production job pulls that exact digest and deploys it. No rebuild. What was tested in staging is byte-for-byte identical to what runs in production."

---

### Beat 10 · Expand the staging job steps

> **SHOW:** Click **Deploy Portal → Staging** job — expand the steps list to show: GCP auth, Docker build, AR push, digest capture, Cloud Run deploy

> **SAY:** "GCP auth here is keyless — Workload Identity Federation. No service account JSON key stored anywhere. GitHub exchanges a short-lived OIDC token for a GCP access token, and the deploy goes through. The digest is captured right after the push and passed to the production job as an output. That's what guarantees the promotion is exact."

---

### Beat 11 · Show the production job

> **SHOW:** Click **Deploy Portal → Production** job — show it pulled the digest from staging, ran Cloud Run deploy, completed in 30 seconds

> **SAY:** "Production job took 30 seconds — because there's nothing to build. It pulled the exact digest, retagged it as production, deployed. Done."

---

### Beat 12 · Switch to oil-price-demo Actions

> **SHOW:** `github.com/bobbyaqlaar/oil-price-demo` → Actions tab

> **SAY:** "Now the oil-price-demo — the tenant application. Different repo, same CI/CD pattern. The post-checkout hook wrote these workflows automatically when the repo was initialised."

---

### Beat 13 · Open the CI guardrails run

> **SHOW:** Click the most recent successful **CI: Python/FastAPI Guardrails** run (pick the latest green run from the list) — show both jobs: Guardrails and Eval scorecard

> **SAY:** "Two jobs — and more reusable eval workflows in the templates: fairness, hallucination hard-fail, optional TTFT live. The guardrails job — ruff, format, AST bare-except, pytest. The eval scorecard — golden dataset through an LLM judge. Both passed. The PR was gated before merge."

---

### Beat 14 · Expand the eval scorecard job

> **SHOW:** Click **Eval scorecard** job — scroll to the scorecard output showing case results and overall score

> **SAY:** "The judge scores correctness, tool accuracy, latency — and when you enable the suites, fairness and a dedicated hallucination dimension. Hallucination flag rate above `HALLUCINATION_FAIL_ABOVE` — default five percent — hard-fails CI. Fairness uses `FAIRNESS_FAIL_BELOW`. Production annotations still promote into the golden set via HITL — the dataset grows from real incidents, not only synthetic cases. We'll show the UAE angle on these gates in Part 5."

---

## Part 3 — The Oil-Price-Demo App

**[~6 minutes]**

---

### Beat 15 · Show the Streamlit app connecting to GCP

> **SHOW:** Terminal — start the Streamlit app pointed at the GCP Temporal server

```bash
# Get the Temporal server URL first (run once before the demo):
# gcloud run services describe temporal-server --region us-central1 --project agentsmith-500916 --format="value(status.url)"
# Strip the https:// prefix and append :443

cd /Users/mac/Documents/Bobby/Aqlaar/Apps/oil-price-demo
TEMPORAL_ADDRESS=<host-from-above>:443 TEMPORAL_TLS=true streamlit run demo/app.py
```

> **SAY:** "The demo UI is a Streamlit app. It connects to the Temporal server running on GCP Cloud Run. The worker — also on Cloud Run — is listening on the `agent-tasks-oil-price-demo` task queue. We're running the UI locally but the backend is live on GCP."

---

### Beat 16 · Walk through the UI layout

> **SHOW:** Browser opens at `localhost:8501` — show the three-column layout: IngestionAgent, PredictionAgent, DecisionAgent

> **SAY:** "The UI reflects the three-agent pipeline directly. Ingestion validates the price series. Prediction runs anomaly detection and an LLM forecast. Decision compares against the threshold and either places the order or routes to the dead-letter queue — with a HITL gate in the middle if the model flags uncertainty."

---

### Beat 17 · Select the HITL preset and start a workflow

> **SHOW:** Sidebar → Preset dropdown → select **"HITL — price spike"** → click **▶ Start workflow**

> **SAY:** "This preset includes a price spike — a value well outside the normal range. That's going to trigger the anomaly detection in the prediction agent and flag the run for human review before any order goes out."

---

### Beat 18 · Show the workflow running

> **SHOW:** Main panel updates — workflow ID visible, status shows 🟡 Running, running info message appears

> **SAY:** "The workflow is live on the Temporal server in GCP. The worker picked it up, ran the ingestion activity, ran the prediction activity — found the spike, flagged it. The workflow is now parked at the HITL gate, waiting for a signal."

---

### Beat 19 · Show the HITL gate panel

> **SHOW:** HITL panel appears — ✅ Approve and ❌ Reject buttons visible, warning message about the flagged run

> **SAY:** "This is the approve/reject gate. The Temporal workflow is paused — not polling, not burning resources, just waiting on a signal. The workflow will wait up to 24 hours. In production, this notification would go to Slack or Teams. Here, the operator reviews and decides."

---

### Beat 20 · Approve the signal

> **SHOW:** Click **✅ Approve** — button grays out, "Signal already sent" message appears, status refreshes

> **SAY:** "Signal sent. The Temporal workflow receives the `hitl_approved: true` signal and resumes — runs the decision activity, checks the threshold, places the order. Let's refresh to see the result."

---

### Beat 21 · Refresh and show the result

> **SHOW:** Click **🔄 Refresh status** — status transitions to ✅ Completed, result JSON appears with prediction, confidence, action taken

> **SAY:** "Completed. The result is the decision — predicted price, confidence score, action taken. All of this is recorded. The trace is live in Phoenix right now. Let's go look at it."

---

## Part 4 — GCP Operations

**[~6 minutes]**

---

### Beat 22 · Open GCP Console — Cloud Run

> **SHOW:** GCP Console → Cloud Run → filter by region `us-central1`, project `agentsmith-500916`

> **SAY:** "Four services running in GCP. The Temporal server — self-hosted, min-instances set to 1 because it's a long-running poller, not a request/response service. The oil-price worker — also min-instances 1, same reason. And the AgentSmith Ops Portal in staging and production."

---

### Beat 23 · Open the Temporal server service

> **SHOW:** Click `temporal-server` → show the service details: URL, min instances, revision, health check

> **SAY:** "The Temporal server fronts the workflow engine. The worker connects to it over the task queue. Cloud SQL Postgres is the persistence backend — all workflow history, state, and event logs stored durably. If the server restarts, the workflow history survives."

---

### Beat 24 · Open the oil-price worker service

> **SHOW:** Click `oil-price-worker-staging` → show Cloud Run logs tab — filter to show recent activity from the workflow run we just triggered

> **SAY:** "These are the worker logs from the run we just triggered. You can see the activity executions — ingestion, prediction, decision. Each one is a Temporal activity with its own retry policy. Transient failures — rate limits, network blips — are retried automatically by Temporal. Only failures that need a human fix reach the DLQ."

---

### Beat 25 · Open Cloud SQL

> **SHOW:** GCP Console → Cloud SQL → `temporal-pg` instance → Overview tab

> **SAY:** "The Temporal database — Postgres on Cloud SQL. The workflow history lives here. The Ops Portal audit log and budget tracking also use Postgres, in a separate schema on the same instance for this demo. In production at scale, these would be separate instances."

---

### Beat 26 · Open Arize Phoenix

> **SHOW:** Switch to Arize Phoenix at `localhost:6006` (or team server) — Projects view showing `oil-price-demo`

> **SAY:** "Every LLM call, every agent action, every token is streaming to Arize Phoenix via OpenTelemetry. This is the observability layer. Let's look at the trace from the run we just did."

---

### Beat 27 · Open the most recent trace

> **SHOW:** Click `oil-price-demo` project → Traces → click the most recent trace → expand the span tree

> **SAY:** "Here's the full trace. The root span is the workflow run. Under it: the ingestion span, the prediction span — this is where the LLM call happened — and the decision span. Expand the prediction span."

---

### Beat 28 · Show span attributes

> **SHOW:** Click the prediction span — show attributes panel: `agent.owner_id`, `agent.name`, `llm.model_name`, `llm.gateway.cost_usd`, token counts, latency

> **SAY:** "Every span carries agent identity — owner, name, role, session ID. Cost in USD per call. Token counts in and out. Latency. This is the answer to 'what did the agent do and why did it cost what it cost' — recorded at the point of execution, not inferred afterwards. Filter by owner ID and you see every action across every project and session attributed to that person."

---

### Beat 29 · Show the Ops Portal

> **SHOW:** Open `https://agentsmith-portal-production-431995395208.us-central1.run.app` — log in — show the main dashboard

> **SAY:** "The Ops Portal. This is the operational nerve centre — cross-tenant cost and issues dashboard, run history, DLQ triage, and the audit log."

---

### Beat 30 · Show the run history

> **SHOW:** Navigate to the Runs or History section — show the oil-price-demo runs listed with status, model, cost, duration

> **SAY:** "Every agent run synced here from the tenant's CD pipeline. Status, model used, cost, duration, outcome. Operators can see across all tenants in one view."

---

### Beat 31 · Show the audit log

> **SHOW:** Navigate to the Audit section — show entries with `verified: true` badges

> **SAY:** "Every admin and system action is HMAC-SHA256 signed and written to an append-only table. On read, the portal recomputes the signature. A tampered row shows `verified: false` — including if someone disables the database trigger, edits a row, and re-enables it. The signature layer catches it either way."

---

### Beat 32 · Show the DLQ view (optional — if a DLQ entry exists)

> **SHOW:** Navigate to DLQ section — show a dead-lettered entry if one exists, with workflow ID, gate ID, and the failing payload editable

> **SAY:** "If an agent's tool call produces a payload the downstream system rejected — a hallucinated field name, a misformatted structure — the workflow parks here alive, not dead. Optionally, `run_with_self_correction` asks the model for one corrected JSON payload first; if that still fails, a human edits here and clicks Replay. The portal signs it, sends it to the tenant's webhook. The same workflow execution resumes with the fix. Not a fresh run. That is how we meet 'human oversight' expectations without killing the run."

---

## Part 5 — UAE Compliance Differentiator

**[~5 minutes]**

*Goal: show that AgentSmith is not a ChatGPT wrapper — residency, bias law,
HITL, PDPL, and governance map to runnable artifacts.*

---

### Beat 33 · Open the UAE regulatory map

> **SHOW:** AgentSmith repo → `docs/uae-regulatory.md` — scroll the five-mandate table

> **SAY:** "For UAE and GCC buyers the question is not 'can it call an LLM?' — it is 'where does national data go, who stops a high-impact action, how do you prove fairness and privacy?' This doc maps five themes: sovereign infrastructure, Federal Decree-Law No. 34/2023-style bias accountability, mandatory human oversight, PDPL-aligned PII handling, and ISO/IEC 42001-oriented governance. Not a partnership claim. Not a certificate. A control map with pointers into the code."

---

### Beat 34 · Sovereign Falcon 3 on Ollama (Pattern A)

> **SHOW:** `templates/uae-sovereign/models.yaml` — highlight `falcon3:3b` / `falcon3:1b` roles

```bash
# Optional live smoke (Ollama running locally):
OLLAMA_BASE_URL=http://127.0.0.1:11434 python3 scripts/verify_sovereign_endpoint.py
```

> **SAY:** "Pattern A — TII Falcon 3 via in-border Ollama. Primary roles use `falcon3:3b`; degrade and judge use `falcon3:1b`. Live-verified chat completions. National data stays on the host you control — not a public frontier API. Pattern B is a UAE sovereign OpenAI-compatible endpoint when your cloud provides one. Public Hugging Face is research-only and explicitly out of residency profile."

---

### Beat 35 · Bias & fairness gate (Decree-Law 34/2023 theme)

> **SHOW:** `fixtures/fairness_evals_base.json` (or CI Actions → fairness job) + `FAIRNESS_FAIL_BELOW` in env example

> **SAY:** "Bias accountability is not a slide. Paired fairness cases run through `run-evals.py --suite fairness` with pair-parity scoring. Threshold comes from `.env` — `FAIRNESS_FAIL_BELOW`. Wire it into CI as warn or required. That is how you show routine bias audits against protected attributes, not a one-off workshop."

---

### Beat 36 · Hallucination rate + TTFT as compliance evidence

> **SHOW:** `fixtures/hallucination_evals_base.json` + mention `HALLUCINATION_FAIL_ABOVE=0.05`; optionally `scripts/verify_ttft.py`

> **SAY:** "Reliability is also evidence. The judge scores a dedicated `hallucination` dimension — unsupported claims, distinct from mere incorrectness. Flag rate above five percent fails the hard CI gate. Separately, opt-in streaming records time-to-first-token; live Ollama can enforce `TTFT_FAIL_ABOVE_MS` when you set `TTFT_LIVE=required`. Auditors ask for metrics; these are named, gated numbers."

---

### Beat 37 · PDPL — PII scrubbed before the model call

> **SHOW:** `runtime/input_guardrail.py` (or README Security layer) — mention Emirates ID pattern

> **SAY:** "PDPL is about personal data in the *decision path*, not only in logs. Before the provider call, `input_guardrail` masks Emirates ID, email, phone, and cards. After the call, `trace_redactor` still protects Phoenix. Staging and production default the guardrail on. That is decision-path anonymization, not a privacy policy PDF."

---

### Beat 38 · HITL + self-correction + tamper-evident audit

> **SHOW:** Ops Portal audit log (`verified: true`) and/or DLQ — tie back to Beats 31–32

> **SAY:** "High-impact actions pause for a human — approve/reject or edit-and-resume. Self-correction is opt-in and still falls through to a human if the model cannot fix the payload. Every admin action is HMAC-signed append-only. ISO 42001 themes for human oversight and transparency are Met in our control map with these artifacts as evidence — again, thematic alignment, not a certificate on the wall."

---

### Beat 39 · Delivery Model — rules in the pipeline

> **SHOW:** `docs/delivery-model.md` or `templates/delivery-model/org-policy.example.yaml` — `uae-sovereign` as approved platform

> **SAY:** "Enterprise buyers ask for pre-approved environments and in-pipeline governance. The Delivery Model catalog lists approved platforms — including `uae-sovereign` — and soft-gates evidence before promote. Compliance is logs and gates, not a deck."

---

## Wrap-Up

**[~1 minute]**

---

### Beat 40 · Close the loop

> **SHOW:** Return to the Arize Phoenix trace — show the completed span tree

> **SAY:** "That's the full loop. One install. IDE harness on every checkout. Spec-first hooks. CI with fairness and hallucination gates. Temporal on GCP with Phoenix traces and an Ops Portal audit trail. For UAE and regulated buyers: Falcon 3 in-border, PDPL scrub before the call, HITL stop-gates, bias suites, and an ISO-oriented evidence map — runnable controls, not promises."

> **SAY:** "Start locally on Ollama — zero cost, residency-friendly. Scale to cloud when the use case justifies it. Same framework throughout. Open source. Everything you saw is on GitHub."

---

**[End of demo — open to Q&A]**

**Likely UAE / compliance Q&A prompts:**
- "Is this certified for PDPL / ISO 42001?" → No — thematic control map + evidence artifacts; counsel / certification body own the claim.
- "Where does national data go on Pattern A?" → Your Ollama host / in-border Postgres / Phoenix — set `OLLAMA_BASE_URL` and residency checklist.
- "What if Falcon invents a field?" → Self-correction opt-in, then DLQ edit-and-resume; hallucination suite tracks unsupported claims in evals.

---

## Quick Reference — URLs and Commands

| What | Where |
|---|---|
| AgentSmith repo | `github.com/bobbyaqlaar/AgentSmith` |
| UAE regulatory map | `docs/uae-regulatory.md` |
| UAE sovereign starter | `templates/uae-sovereign/` |
| Falcon 3 smoke | `OLLAMA_BASE_URL=http://127.0.0.1:11434 python3 scripts/verify_sovereign_endpoint.py` |
| Fairness suite | `python3 scripts/run-evals.py --suite fairness` |
| Hallucination suite | `python3 scripts/run-evals.py --suite hallucination` |
| TTFT smoke | `python3 scripts/verify_ttft.py` |
| oil-price-demo repo | `github.com/bobbyaqlaar/oil-price-demo` |
| AgentSmith CD run (staging + production) | `github.com/bobbyaqlaar/AgentSmith/actions` → latest green CD: Ops Portal Deploy |
| oil-price-demo CI run (guardrails + eval) | `github.com/bobbyaqlaar/oil-price-demo/actions` → latest green CI: Python/FastAPI Guardrails |
| GCP Console — Cloud Run | `console.cloud.google.com` → project `agentsmith-500916` → Cloud Run |
| Ops Portal (production) | `https://agentsmith-portal-production-431995395208.us-central1.run.app` |
| Arize Phoenix (local) | `http://localhost:6006` |
| Streamlit demo | `http://localhost:8501` (start with `streamlit run demo/app.py`) |

## Start-the-demo checklist

- [ ] Phoenix running locally (`ai-dashboard-start`)
- [ ] Knowledge Graph up to date — run from oil-price-demo: `python3 $AGENTSMITH_DIR/scripts/map_codebase.py` (writes `.agent-rfc/fixtures/knowledge_graph.json`)
- [ ] Temporal server URL fetched: `gcloud run services describe temporal-server --region us-central1 --project agentsmith-500916 --format="value(status.url)"` — strip `https://`, append `:443`
- [ ] Streamlit app command ready in terminal with `TEMPORAL_ADDRESS` set to that value
- [ ] All browser tabs pre-opened and logged in
- [ ] GCP Console already on `agentsmith-500916` → Cloud Run
- [ ] Ops Portal session active (don't get caught at the login screen)
- [ ] oil-price-demo repo open in terminal at the correct path
- [ ] (UAE beat) `templates/uae-sovereign/models.yaml` and `docs/uae-regulatory.md` bookmarked
- [ ] (Optional) Ollama with `falcon3:1b` / `falcon3:3b` pulled for live sovereign smoke
