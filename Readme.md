# AgenticFramework

**One install. Every agent. Every project.**

AgenticFramework is a single-command setup that provisions the complete AI agent lifecycle environment on your machine or team server. Install it once and every repository you work in gets guardrails, observability, evaluation, self-improvement, and CI/CD — automatically.

---

## What It Sets Up

| Layer | What you get |
|---|---|
| **IDE Guardrails** | `.cursorrules`, `CLAUDE.md`, `.agents/skills/` — written for Cursor, Claude Code, and Antigravity on every `git checkout` |
| **Git Hooks** | Pre-commit safety checks, commit message linting, automatic semantic versioning, AST codebase mapping — globally, across every repo |
| **Observability** | Arize Phoenix tracing dashboard — one instance per machine or team, serving all projects with per-project namespacing |
| **Evaluations** | Golden dataset + LLM-as-judge scorecard that gates every PR, calibrated continuously from production traces |
| **Multi-Agent Orchestration** | Architect → Developer → Validator pipeline, running locally on Ollama or on cloud frontier models |
| **Knowledge Graph** | AST-driven codebase graph, auto-updated on every commit and checkout — zero context drift |
| **Self-Improvement** | Human-in-the-Loop promotion loop: production failures become test cases become guardrail rules |
| **Cost & Budget Guard** | Dual-tier circuit breaker — burst velocity limit + monthly spend cap with cross-platform notifications |
| **CI/CD** | GitHub Actions workflows for TypeScript/React, Python/FastAPI, and Go — written automatically per project |
| **Agent Identity** | Every span, log entry, and trace is tied to an orchestrator, sub-agents, and a real human owner |

---

## Quick Start

```bash
# 1. Install
curl -fsSL https://raw.githubusercontent.com/<org>/AgenticFramework/main/install-ai-stack.sh | bash

# 2. Activate
source ~/.zshrc

# 3. Set your identity
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"

# 4. Choose your mode
ai-mode-local    # 100% offline — Ollama on your GPU (free)
# or
ai-mode-hybrid   # Cloud frontier APIs — Claude + GPT-4o

# 5. Start the observability dashboard
ai-dashboard-start
# → http://localhost:6006

# 6. Apply to a project
cd /path/to/your/project
git init
# → hooks fire, .cursorrules written, CI workflows created, Knowledge Graph seeded
```

---

## The Ten Pillars

AgenticFramework is built around ten operational guardrails that together cover the full agent lifecycle.

**1. Requirements & Design** — Agents are blocked from writing code unless a spec exists in `.agent-rfc/`. Every change is mapped to a written requirement before execution begins.

**2. Build Architecture (Ponytail)** — Native platform libraries over custom abstractions. Minimal dependency trees. A five-step analysis before any new file is created.

**3. Tracing & Evaluations** — Every token, tool call, and latency metric is streamed to the Arize Phoenix dashboard via OpenTelemetry. Nothing is lost between sessions.

**4. Testing Guardrails** — Every change requires paired tests. CI enforces this on every pull request. Existing regression tests are never cleared to force a green build.

**5. Operations & Self-Improvement** — `.agent-history.log` captures structured events (INFO / MINOR / MAJOR / CRITICAL). MAJOR and CRITICAL entries are protected until a human resolves them via HITL.

**6. Interface Constraints (Caveman)** — Agents output code and data only. No pleasantries, summaries, or meta-commentary.

**7. Stack-Specific Rules** — TypeScript/React, Python/FastAPI, and Go rules injected into all three IDEs automatically on checkout.

**8. Observability Wire** — The OTel endpoint is embedded in `.cursorrules` so IDE-level agent requests stream to the dashboard without additional configuration.

**9. Multi-Agent Orchestration** — Stateful Architect → Developer → Validator pipeline with HITL pause support. Runs fully offline (Ollama) or on cloud frontier APIs with automatic network fallback.

**10. Cost-Optimisation Routing** — Token complexity and semantic analysis route each task to the cheapest capable model. A dual-tier circuit breaker prevents budget bleed.

---

## Supported Stacks

| Stack | Detected by | CI workflow |
|---|---|---|
| TypeScript / React | `package.json` | `ci-ts-react.yml` |
| Python / FastAPI | `requirements.txt` / `pyproject.toml` | `ci-python-fastapi.yml` |
| Go | `go.mod` | `ci-go.yml` |
| Generic | *(fallback)* | *(hooks only, no CI workflow)* |

---

## Execution Modes

### Local Offline
Everything runs on your machine. No API keys. No cost.

```
Ollama (llama3 / mistral / gemma2)  ←→  Local Phoenix (:6006)
```

### Hybrid Cloud
Frontier models for complex tasks, open-source for everything else. Automatic fallback to local if the network drops.

```
Claude 3.5 Sonnet / GPT-4o  ←→  Open-source via Groq/Together  ←→  Local Phoenix
```

Switch modes instantly — no restart, no config file edits:

```bash
ai-mode-local     # switch to offline
ai-mode-hybrid    # switch to cloud
ai-stack-status   # show current state + network connectivity
```

---

## Multi-Repository & Monorepo

The framework installs once at the machine level. Every repository on the machine inherits the git hooks automatically. No per-project setup steps.

```bash
# Apply to any existing repo instantly
cd /path/to/existing-repo && git init
```

Monorepos are fully supported. Each sub-package can have its own `.agent-rfc/` for service-level specs, with a root `.agent-rfc/` for cross-cutting architecture decisions.

---

## Observability

All projects on the machine share a single Arize Phoenix instance. Traces are namespaced by `project.name` — filter in the UI to see any individual project.

For teams, run Phoenix as a shared service with the included Docker Compose file (PostgreSQL-backed):

```bash
docker compose up -d
# All team members set: export AGENT_PHOENIX_ENDPOINT="http://<server-ip>:6006"
```

---

## Evaluation & Self-Improvement

The golden dataset starts with framework-provided baseline cases and grows automatically from production traces via the HITL loop. Every approved production trace becomes a new test case that gates future PRs — creating a compounding quality flywheel.

```
Dev evals (PR gate)  ←←←  Golden dataset  →→→  Production calibration (HITL loop)
```

Run evals locally:
```bash
ai-test-evals
```

Promote a production fix to the golden dataset:
```bash
ai-stack-promote <case-id> "<input query>" "<correct output>"
```

---

## Agent Identity

Every agent run is fully traceable to a human owner across all projects and sessions:

```bash
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"
```

Every OTel span, log entry, and HITL record carries `agent.owner_id`, `agent.name`, `agent.role`, `agent.session_id`, and parent-child span linkage between orchestrators and sub-agents. Filter Phoenix by `agent.owner_id` to see all activity across all your projects.

---

## CI/CD

GitHub Actions workflows are written automatically by the `post-checkout` hook and enforce the same guardrails as your local environment:

- Type checking, linting, and tests on every pull request
- Eval scorecard with configurable quality threshold
- Graceful skip on greenfield projects until a golden dataset exists
- Post-deploy promotion of approved production traces back into the golden dataset

Required GitHub secrets: `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`. `AGENT_PHOENIX_ENDPOINT` is optional.

---

## Example: Building an Oil Price Tracker & Chemical Order Agent

This walkthrough shows the complete happy path — from an empty folder to a production-ready multi-agent system — using AgenticFramework. The app tracks and predicts oil prices and automatically places orders for chemicals whose prices are directly linked to oil, triggered when the predicted price crosses a configured threshold.

### What the System Does

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  Ingestion Agent │───►│ Prediction Agent  │───►│  Decision Agent     │
│                 │    │                  │    │                     │
│ Fetches oil     │    │ Time-series model │    │ Compares predicted  │
│ price data from │    │ forecasts next    │    │ price vs. threshold │
│ market APIs     │    │ 7-day price range │    │ per chemical        │
└─────────────────┘    └──────────────────┘    └──────────┬──────────┘
                                                           │
                                                           ▼
                                               ┌─────────────────────┐
                                               │   Order Agent       │
                                               │                     │
                                               │ Places purchase     │
                                               │ orders via supplier │
                                               │ API when threshold  │
                                               │ is breached         │
                                               └─────────────────────┘
```

### Step 0 — Install the Framework *(once per machine)*

Before any project work, run the installer once on your machine. This is a machine-level operation — you never run it again for subsequent projects.

```bash
# Install
curl -fsSL https://raw.githubusercontent.com/<org>/AgenticFramework/main/install-ai-stack.sh | bash

# Activate shell functions
source ~/.zshrc

# Set your identity (all traces and logs will be attributed to you)
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"

# Install local GPU models (required for local mode; skip if using hybrid only)
ollama pull llama3 && ollama pull mistral && ollama pull gemma2

# Choose your mode and start the dashboard
ai-mode-hybrid        # or ai-mode-local for fully offline
ai-dashboard-start    # http://localhost:6006
```

From this point on, every `git init` or `git clone` on this machine automatically receives the full framework — hooks, IDE rules, CI workflows, and Knowledge Graph — with no further installation steps.

> **Already installed?** Skip to Step 1. The installer is idempotent — safe to re-run after framework upgrades.

---

### Step 1 — Create the Repository

```bash
mkdir oil-price-agent && cd oil-price-agent
git init
git remote add origin https://github.com/org/oil-price-agent.git
```

The `post-checkout` hook fires immediately:

```
🔧 AI Stack Hook: Analysing repository type... [Detected: PYTHON_FASTAPI]
✅ AI Stack Hook: Created .agent-rfc/ directory
✅ AI Stack Hook: Created stack-specific .cursorrules file
✅ AI Stack Hook: Created CLAUDE.md (Claude Code instructions)
✅ AI Stack Hook: Created Antigravity skill structure
✅ AI Stack Hook: Written ci-python-fastapi.yml into GitHub Workflows
🏗️  Constructing baseline Knowledge Graph architecture...
✅ Knowledge Graph seeded with 3 guardrail nodes
```

You now have a fully configured project with IDE rules for all three agents, a CI pipeline, and a baseline golden dataset — before writing a single line of code.

### Step 2 — Write the RFC Specification

Before any agent touches code, the spec must exist.

```bash
touch .agent-rfc/001-oil-price-tracker.md
```

```markdown
# RFC 001 — Oil Price Tracker & Chemical Order Agent

## Objective
Build a multi-agent system that monitors crude oil prices, forecasts 7-day
price movements using a time-series model, and places purchase orders for
chemicals (benzene, ethylene, propylene) when the predicted price drops
below a configured threshold.

## Agent Roles
- **Ingestion Agent**: Polls EIA / commodity API every 6 hours; stores to TimescaleDB
- **Prediction Agent**: Runs Prophet forecast on latest 90-day window; writes forecast to DB
- **Decision Agent**: Reads forecast; compares to per-chemical thresholds in config
- **Order Agent**: Calls supplier REST API to place purchase order; logs outcome

## Files to Create
- `agents/ingestion_agent.py`
- `agents/prediction_agent.py`
- `agents/decision_agent.py`
- `agents/order_agent.py`
- `orchestrator.py`
- `config/thresholds.yaml`
- `tests/test_decision_agent.py`

## Thresholds (initial)
| Chemical    | Order if predicted price ($/bbl oil eq.) | Order qty |
|-------------|------------------------------------------|-----------|
| Benzene     | < 72.00                                  | 500 MT    |
| Ethylene    | < 68.00                                  | 1,200 MT  |
| Propylene   | < 65.00                                  | 800 MT    |

## Acceptance Criteria
- [ ] Forecast MAPE < 8% on 30-day back-test
- [ ] Order placed within 60s of threshold breach detection
- [ ] All API calls retried with exponential backoff (no swallowed errors)
- [ ] Full trace in Phoenix for every forecast + order cycle
```

### Step 3 — Start the Stack

```bash
ai-mode-hybrid        # Claude 3.5 Sonnet for architecture, Llama3 for implementation
ai-dashboard-start    # http://localhost:6006
ai-stack-check        # confirm everything is healthy
```

### Step 4 — The Architect Agent Designs the System

In your IDE (Cursor, Claude Code, or Antigravity), the agent reads the RFC automatically before planning. It queries the Knowledge Graph for existing dependencies, then proposes the minimal architecture:

```
🧠 [Architect Agent] Reading .agent-rfc/001-oil-price-tracker.md...
🧠 [Architect Agent] Querying Knowledge Graph for existing modules...
🧠 [Architect Agent] Applying PONYTAIL: using Prophet (standard), httpx (standard), psycopg2 (standard)
🧠 [Architect Agent] No custom abstractions required — native async + standard retry library sufficient

Blueprint:
  orchestrator.py          ← LangGraph StateGraph, 4 nodes
  agents/ingestion_agent.py ← httpx + psycopg2, no ORM
  agents/prediction_agent.py ← Prophet, outputs JSON forecast to DB
  agents/decision_agent.py  ← pure logic, reads config/thresholds.yaml
  agents/order_agent.py     ← httpx with tenacity retry, logs to .agent-history.log
```

The Architect span appears instantly in Phoenix under `project.name = "oil-price-agent"`.

### Step 5 — The Developer Agent Implements

The Developer agent writes code under Caveman constraints — code blocks only, no commentary. Each file written triggers a Knowledge Graph update linking the new node to its imports.

```python
# agents/decision_agent.py  (excerpt — written by Developer Agent)
import yaml
from dataclasses import dataclass
from typing import Optional

@dataclass
class OrderSignal:
    chemical: str
    predicted_price: float
    threshold: float
    order_qty_mt: int

def evaluate_thresholds(forecast: dict, config_path: str = "config/thresholds.yaml") -> list[OrderSignal]:
    with open(config_path) as f:
        thresholds = yaml.safe_load(f)

    signals = []
    for chemical, cfg in thresholds["chemicals"].items():
        predicted = forecast.get(chemical)
        if predicted is None:
            continue
        if predicted < cfg["threshold_usd_bbl"]:
            signals.append(OrderSignal(
                chemical=chemical,
                predicted_price=predicted,
                threshold=cfg["threshold_usd_bbl"],
                order_qty_mt=cfg["order_qty_mt"]
            ))
    return signals
```

### Step 6 — The Validator Agent Catches Issues

The Validator scans the generated code against March of Nines rules. On the first pass it catches a problem in the order agent:

```
🚨 [Validator Agent] Checking agents/order_agent.py...
❌ Validator Error: except block at line 47 is empty — swallowed exception detected
   → Routing back to Developer Agent for correction
```

The Developer agent fixes it, adding proper error logging and retry logic. The corrected version passes:

```
✅ [Validator Agent] All March of Nines checks passed
✅ [Validator Agent] Retry logic present (tenacity.retry)
✅ [Validator Agent] No empty catch blocks
✅ Multi-agent workflow APPROVED
```

### Step 7 — Commit and Watch the Hooks Run

```bash
git add .
git commit -m "feat(agents): implement oil price ingestion, prediction, and order pipeline"
```

```
📝 AI Guardrails: Validating commit message format...
✅ Commit message lint passed

🚨 AI Guardrails: Reviewing staged code before commit...
✅ Guardrail Audit Passed. Codebase is clean.

🔍 [Codebase Mapper] Executing AST structural sweep...
✅ Knowledge Graph updated: 6 new CodebaseFile nodes, 14 DEPENDS_ON edges

✅ Local Semantic Tag v0.1.0 generated successfully
[2026-06-22 11:34:01] Successful Commit: v0.1.0 - feat(agents): implement oil price...
```

### Step 8 — Open a Pull Request

GitHub Actions picks up the commit automatically:

```
CI: Python/FastAPI Guardrails

✅ ruff check .
✅ pytest (12 tests passed)
⚠️  Eval scorecard: golden dataset has 2 cases — below minimum threshold (3).
    Quality gate will activate on next PR once dataset is populated.
    Tip: run 'ai-test-evals' locally to add cases.
```

The PR is ready to merge. The eval quality gate is already watching — it will enforce correctness thresholds from the next PR onward.

### Step 9 — Production: The Agent Places Its First Order

The system runs in production. A forecast cycle completes:

```
Predicted WTI crude: $67.40/bbl  (7-day horizon)
→ Benzene threshold: $72.00  — BREACH DETECTED (predicted $67.40 < $72.00)
→ Ethylene threshold: $68.00 — BREACH DETECTED (predicted $67.40 < $68.00)
→ Propylene threshold: $65.00 — no breach

Placing order: Benzene 500 MT  ... ✅ Order #BNZ-20260622-001 confirmed
Placing order: Ethylene 1200 MT ... ✅ Order #ETH-20260622-001 confirmed
```

Every step streams to Phoenix. Open `http://localhost:6006`, filter by `project.name = "oil-price-agent"` and expand the trace to see:

- `ingestion_node` → fetch duration, rows written to DB
- `prediction_node` → Prophet runtime, MAPE score, forecast values
- `decision_node` → threshold evaluation, chemicals triggered
- `order_node` → API latency, order IDs, retry count

### Step 10 — Self-Improvement: A Bad Prediction Gets Promoted

One week later, the Prediction Agent underestimates a price spike. The order is placed unnecessarily (false positive). You review the Phoenix trace, annotate it:

```
Phoenix UI → Traces → prediction_node span → Annotations
  hitl_approved = true
  label = bad
```

Then run:

```bash
ai-test-evals
```

```
🔄 Syncing Human-in-the-Loop approvals from Phoenix UI...
🎯 Found HITL annotation for Span ID: 3f8a2c...
   Input: "Predict WTI price given 90-day window with geopolitical event flag"
   Issue: Model did not account for supply shock in feature set
🚀 LLM distilling failure pattern...
   → Rule: "Prediction agent must include geopolitical_event_flag as a feature input when available in the ingestion dataset."
✅ Golden dataset updated: case_004 added
✅ Custom judge criteria updated (8/10 rules)

🎯 Running regression scorecard...
   Correctness: 91% ✅  |  Tool Accuracy: 96% ✅  |  Latency: nominal ✅
```

The rule is now enforced on every future PR. The next developer who touches the prediction agent will be blocked by CI if they remove the geopolitical event flag — the system learned from the real-world failure and codified it automatically.

---

## Key Commands

| Command | What it does |
|---|---|
| `ai-mode-local` | Switch to 100% offline Ollama mode |
| `ai-mode-hybrid` | Switch to cloud frontier mode |
| `ai-stack-off` | Disable all hooks (corporate / clean mode) |
| `ai-stack-check` | Health check: Phoenix, Ollama/API keys, unresolved log entries |
| `ai-stack-status` | Current mode, muted flag, network connectivity |
| `ai-dashboard-start` | Start Arize Phoenix at localhost:6006 |
| `ai-dashboard-stop` | Stop Phoenix |
| `ai-test-evals` | Sync HITL feedback + run eval scorecard |
| `ai-stack-promote <id> <query> <output>` | Promote a production fix to the golden dataset |
| `ai-stack-scrub [dir]` | Remove runtime artefacts from a project directory |

---

## Prerequisites

| Requirement | Version |
|---|---|
| macOS / Linux / Windows | — |
| Python | 3.11+ |
| Git | 2.x |
| Ollama *(local mode only)* | Latest |
| Docker *(team Phoenix only)* | 20+ |
| Node.js *(TS/React projects)* | 20+ |
| Go *(Go projects)* | 1.22+ |

---

## Configuration

All configuration is via environment variables in `~/.zshrc` — no config files to edit manually.

| Variable | Default | Purpose |
|---|---|---|
| `AI_STACK_MODE` | `local` | `local` / `hybrid` / `disabled` |
| `AGENT_OWNER_ID` | — | Your email — ties all traces to you |
| `AGENT_OWNER_NAME` | — | Your display name |
| `AGENT_JUDGE_MODEL` | `claude-3-5-sonnet-20241022` | LLM used for eval scoring — change without editing code |
| `AGENT_PHOENIX_ENDPOINT` | `http://localhost:6006` | Phoenix URL (local or team-shared) |
| `OPENAI_API_KEY` | — | Required for hybrid mode |
| `ANTHROPIC_API_KEY` | — | Required for hybrid mode |
| `OS_LLM_BASE_URL` | `http://localhost:11434/v1` | Open-source LLM endpoint |
| `AI_STACK_SLACK_WEBHOOK` | — | Slack alerts on failover / budget breach |
| `AI_STACK_TEAMS_WEBHOOK` | — | MS Teams alerts |

---

## Beyond Solo Dev: Multi-Tenant, Production, and Enterprise

Everything above is the single-developer dev-mode path. The framework also
has a production/multi-tenant layer, built and tested against real
infrastructure (Postgres, Redis, Temporal, Kubernetes, a live OIDC provider):

| Layer | What it adds |
|---|---|
| **Multi-Tenancy** | `ai-tenant-init` / `ai-tenant-promote` scaffold an independent tenant repo with its own CI/CD, eval gates, and `staging → production` promotion flow |
| **Production Runtime** | `runtime/llm_gateway.py` (budget enforcement + degrade ladder), `runtime/trace_redactor.py` (environment-aware redaction), Temporal workflow patterns in `runtime/workflows/` |
| **Ops Portal** | `portal/` — cross-tenant cost/issues dashboard, history sync, audit log, SSO/OIDC login |
| **In-App Widget** | `templates/in-app-widget/` — embeddable end-user status component, token-scoped, no cross-tenant access |
| **Enterprise Pack** | `enterprise/` — GPG-signed hook bundles + MDM deployment, break-glass bypass policy enforcement, dedicated per-tenant Kubernetes worker pools |

See **[OPERATIONS.md](./OPERATIONS.md)** for step-by-step install, configuration, testing, and day-to-day operation of all of this — solo dev through enterprise.

---

## Documentation

- **[SPECS.md](./SPECS.md)** — Full formal specification: all pillars, components, data schemas, decision log
- **[UserManual.md](./UserManual.md)** — Day-to-day usage for solo/team dev mode: commands, workflows, maintenance
- **[OPERATIONS.md](./OPERATIONS.md)** — Step-by-step install/config/test/operate, including multi-tenancy, production runtime, Ops Portal, and the enterprise pack

---

## Repository Structure

```
AgenticFramework/
├── install-ai-stack.sh        # Entry point — run this once
├── scripts/                   # Python agent stack (dev lifecycle) + generate-ide-config.py
├── runtime/                   # Production runtime — llm_gateway, trace_redactor, worker, workflows/, k8s/
├── hooks/                     # Git hook templates
├── templates/                 # IDE config source of truth (agent-rules.yaml) + in-app-widget/
├── portal/                    # Ops Portal (Next.js)
├── enterprise/                # Org hook bundle signing, MDM deploy, bypass policy
├── examples/oil-price-agent/  # Reference tenant app (fork per customer, never deploy from here)
├── fixtures/                  # Baseline golden dataset + judge criteria
├── caddy/                     # Phoenix auth sidecar config
├── docker-compose.yml         # Team-shared Phoenix + PostgreSQL
├── docker-compose.auth.yml    # Optional overlay: HTTP basic auth in front of Phoenix
├── .github/workflows/         # Framework's own CI + release pipeline
├── Readme.md
├── SPECS.md
├── UserManual.md
└── OPERATIONS.md
```

---

## License

[MIT](./LICENSE)
