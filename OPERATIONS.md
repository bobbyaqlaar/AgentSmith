# AgentSmith — Operations Guide

**Covers:** install → configure → test → operate, for everything beyond solo
dev mode: multi-tenancy, the production runtime, the Ops Portal, the In-App
Widget, and the enterprise pack.

**See also:** [README.md](./README.md) for the high-level overview ·
[UserManual.md](./UserManual.md) for day-to-day solo/team dev-mode usage ·
[SPECS.md](./SPECS.md) for the full formal specification.

Every command and code path in this document has been run against real
infrastructure while building it — real Postgres, real Redis, a real local
OIDC provider, a real `kind` Kubernetes cluster, real GPG keys — not just
read from source. Where something is a known limitation (not yet wired),
it's called out explicitly rather than glossed over.

---

## Contents

1. [Prerequisites](#1-prerequisites)
2. [Step-by-Step: Setup → Run → Test → Eval → Deploy → Operate](#2-step-by-step-setup--run--test--eval--deploy--operate) — uses `examples/oil-price-agent` throughout; includes a [manual UI walkthrough](#23b--manual-test-walkthrough-the-uis) (Phoenix, Ops Portal incl. DLQ replay, In-App Widget)
3. [Part A — Solo Dev Install (recap)](#part-a--solo-dev-install-recap)
4. [Part B — Team-Shared Phoenix with Auth](#part-b--team-shared-phoenix-with-auth)
5. [Part C — Multi-Tenancy](#part-c--multi-tenancy)
6. [Part D — Production Runtime](#part-d--production-runtime)
7. [Part E — Ops Portal](#part-e--ops-portal)
8. [Part F — In-App Widget](#part-f--in-app-widget)
9. [Part G — Enterprise Pack](#part-g--enterprise-pack)
10. [Testing Checklist](#9-testing-checklist)
11. [Day-2 Operations](#10-day-2-operations)
12. [Troubleshooting](#11-troubleshooting)
13. [Spec Cross-Reference](#12-spec-cross-reference)

---

## 1. Prerequisites

### Two working directories — always know which one you're in

Every command in this guide runs in one of exactly two places:

| Directory | What it is | Example path |
|---|---|---|
| **AgentSmith root** | The framework repo itself — Ops Portal, Docker Compose, shared infra | `$AGENTSMITH_DIR/` |
| **Tenant app root** | Your own agentic app repo, created by `ai-tenant-init` | `$REPO_DIR/my-oil-price-app/` |

Commands that affect the shared platform (portal, Postgres, Phoenix) run from the **AgentSmith root**. Commands that affect a specific agent app (hooks, evals, CI, sync scripts) run from the **tenant app root**. Each section below is labelled with which one applies.

### System tools

| Tool | Needed for | Check |
|---|---|---|
| Python 3.11+ | Everything | `python3 --version` |
| Git 2.x | Everything | `git --version` |

> **One-time git config** — set your default branch name to `main` globally so every `git init` uses it:
> ```bash
> git config --global init.defaultBranch main
> ```
| Docker 20+ | Team Phoenix, Ops Portal Postgres, dedicated worker pool testing | `docker --version` |
| Node.js 20+ | Ops Portal, In-App Widget | `node --version` |
| `gh` CLI | `ai-tenant-promote` (opens the promotion PR) | `gh --version` |
| GnuPG | Enterprise hook bundle signing | `gpg --version` |
| Temporal CLI | `temporal server start-dev` (local dev workflow engine) | `brew install temporal` · `temporal --version` |
| `kubectl` | Dedicated tenant worker pools | `kubectl version --client` |
| Ollama | Local/offline dev mode | `ollama --version` |

Production runtime extras — run from the **AgentSmith root** (macOS system Python is externally managed; use a venv):

```bash
# Run from: AgentSmith root (e.g. $AGENTSMITH_DIR/)
python3 -m venv .venv
source .venv/bin/activate
pip install psycopg2-binary redis temporalio langgraph-checkpoint-postgres cryptography
```

To auto-activate when you `cd` into the AgentSmith root, add to `~/.zshrc`:

```bash
function cd() { builtin cd "$@" && [[ "$PWD" == "$AGENTSMITH_DIR"* && -f .venv/bin/activate ]] && source .venv/bin/activate; }
```

### `~/.zshrc` — environment variables

These must be set before running `install-ai-stack.sh` or any `ai-*` commands. Add them to `~/.zshrc` (or `~/.bashrc`) so they persist across sessions:

```bash
# ── Directories ───────────────────────────────────────────────────────────────────
export REPO_DIR="$HOME/repos"            # root directory for all your repos; adjust if different
export AGENTSMITH_DIR="$REPO_DIR/AgenticFramework"  # AgentSmith framework root

# ── Identity — required; every span, log entry, and audit event attributes to this ──
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"

# ── LLM providers — add whichever you use (at least one required for hybrid mode) ───
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GROQ_API_KEY="gsk_..."           # optional: fast/cheap inference via Groq

# ── Observability ──────────────────────────────────────────────────────────────────
export AGENT_PHOENIX_ENDPOINT="http://localhost:6006"  # change to team server URL if shared
export OTEL_EXPORTER_OTLP_ENDPOINT="${AGENT_PHOENIX_ENDPOINT}/v1/traces"  # set by ai-dashboard-start; listed here for manual overrides

# ── Budget and routing ─────────────────────────────────────────────────────────────
export AGENT_MONTHLY_USD_CAP="50"               # hard cap across all projects (dev mode)
export AGENT_JUDGE_MODEL="claude-3-5-sonnet-20241022"  # LLM used to grade evals

# ── Production runtime (only needed when running runtime/ against real backends) ───
export DATABASE_URL="postgresql://user:pass@localhost:5433/agenticframework"
export REDIS_URL="redis://localhost:6379/0"     # only if IDEMPOTENCY_BACKEND=redis
export TEMPORAL_ADDRESS="localhost:7233"        # only if WORKER_BACKEND=temporal
export IDEMPOTENCY_BACKEND="postgres"           # postgres | redis | memory
export BUDGET_BACKEND="postgres"                # postgres | redis

# ── HITL and trace redaction (production only) ────────────────────────────────────
export HITL_ENCRYPTION_KEY="<32-byte-hex>"      # generate: openssl rand -hex 32
export HITL_BLOB_DIR="/var/agentsmith/hitl"     # or set HITL_BLOB_S3_BUCKET for S3

# ── Ops Portal machine-to-machine ──────────────────────────────────────────────────
export OPS_PORTAL_URL="http://localhost:3000"
# OPS_PORTAL_SYNC_TOKEN — bearer token sent by local scripts (sync-portal-history.py,
# verify_system.py, llm_gateway.py) as "Authorization: Bearer <token>" when calling the
# portal's /api/sync/history and /api/runs/ingest endpoints.
# Must match the OPS_PORTAL_SYNC_TOKEN value set in AgenticFramework/.env (the portal
# checks that .env value against every inbound request).
# Generate: openssl rand -hex 32  — then set the same value in both places.
export OPS_PORTAL_SYNC_TOKEN="<same value as AgenticFramework/.env OPS_PORTAL_SYNC_TOKEN>"

# ── Enterprise pack (only needed in enterprise mode) ──────────────────────────────
# BREAK_GLASS_HMAC_KEY — HMAC-SHA256 signing key used to validate break-glass tokens
# locally (no network call). Break-glass tokens have the form <actor>:<expires>.<sig>;
# IT issues them by signing the payload with this key. The same key must be present on
# every machine where hook bypass is permitted.
# IT generates this key once (openssl rand -hex 32) and distributes it to authorized
# machines. Individual developers should NOT generate their own value.
export BREAK_GLASS_HMAC_KEY="<IT-issued value — do not generate locally>"
```

### `.env` files — there are two, in different places

**Do not confuse these.** They serve different purposes and live in different directories.

#### a. AgentSmith root `.env` — Ops Portal + Docker Compose

> **Where:** `AgenticFramework/.env` (the framework repo root — same folder as `docker-compose.yml`)
> **How:** `cp portal/.env.example .env` from the AgentSmith root, then edit.

This file is read by `docker compose` and the Ops Portal. It is **not** copied into tenant apps.

```bash
# Run from: AgentSmith root
cp portal/.env.example .env
```

```bash
# AgenticFramework/.env — fill in after copying from portal/.env.example
#
# ⚠️  Docker Compose .env rules: values are raw strings — do NOT surround
# values with quotes. "abc" sets the value to literally "abc" (with quotes),
# not abc. Use bare values only: KEY=value, not KEY="value".

# Postgres — shared by Ops Portal, LLM Gateway budget backend, and DLQ
DATABASE_URL=postgresql://phoenix:phoenix@localhost:5433/agenticframework

# Ops Portal basic auth (required — portal refuses to serve any page without these)
# OPS_PORTAL_PASSWORD is compared directly against the HTTP Basic Auth header by
# portal/middleware.ts. Choose a strong random value; this is the only credential
# protecting the portal UI. Generate: openssl rand -base64 24
OPS_PORTAL_USER=ops
OPS_PORTAL_PASSWORD=<strong-password>    # generate: openssl rand -base64 24

# Bearer token for CD pipelines and local scripts → portal ingest
# This is the server-side value the portal expects on POST /api/sync/history and
# POST /api/runs/ingest. The same value must be exported as OPS_PORTAL_SYNC_TOKEN
# in ~/.zshrc (for local scripts) and set as a GitHub Actions secret (for CD).
# Generate: openssl rand -hex 32
OPS_PORTAL_SYNC_TOKEN=<random-secret>    # generate: openssl rand -hex 32

# Audit log — two separate secrets serve two different roles (SPECS.md §30):
# AUDIT_LOG_WRITE_TOKEN — bearer token gating POST /api/audit/append.
#   Used by install-ai-stack.sh to post hook-bypass events to the portal.
#   Not needed in ~/.zshrc. Generate: openssl rand -hex 32
# AUDIT_LOG_HMAC_KEY — HMAC-SHA256 key used to sign every audit event at write
#   time (portal/lib/auditLog.ts). At read time the portal re-signs and compares;
#   a mismatch means the row was tampered with. Second layer after the DB triggers
#   that block UPDATE/DELETE on audit_log. SERVER-SIDE ONLY — never export to
#   ~/.zshrc or tenant apps. ROTATION WARNING: old events stay signed with the old
#   key and will fail re-verification after a rotation. Generate: openssl rand -hex 32
AUDIT_LOG_WRITE_TOKEN=<random-secret>    # generate: openssl rand -hex 32
AUDIT_LOG_HMAC_KEY=<random-secret>       # generate: openssl rand -hex 32  — rotate with care

# HITL blob encryption (production trace redaction — SPECS.md §27)
HITL_ENCRYPTION_KEY=<32-byte-hex>        # generate: openssl rand -hex 32

# Notification webhooks (optional — DLQ alerts on new entries)
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
# TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...

# SSO/OIDC (enterprise pack — leave commented for basic-auth mode)
# SSO_ENABLED=true
# SSO_ISSUER=https://corp.okta.com
# SSO_CLIENT_ID=
# SSO_CLIENT_SECRET=
# SSO_REDIRECT_URI=https://ops.example.com/api/auth/callback
# SSO_SESSION_SECRET=
```

#### b. Tenant app `.env` — your agentic app's runtime config

> **You don't have a tenant app directory yet.** This section is a reference template —
> skip it for now and return here after you run `ai-tenant-init` in §2.1. At that point
> you'll have a directory to put this file in.

> **Where:** `my-tenant-app/.env` (your own app repo root — **not** the AgentSmith root)
> **How:** created manually or by `ai-tenant-init` scaffolding; never committed — add `.env` to your tenant app's `.gitignore`.

This file is loaded by the tenant worker at runtime and by `scripts/sync-portal-history.py` when syncing to the Ops Portal.

```bash
# my-tenant-app/.env — tenant-specific runtime variables

TENANT_ID=my-tenant                      # must match tenant.yaml

# LLM gateway (production) — same API keys you have in ~/.zshrc, but scoped to this app
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Observability — point at the shared AgentSmith Phoenix/Ops Portal
AGENT_PHOENIX_ENDPOINT=http://localhost:6006
OPS_PORTAL_URL=http://localhost:3000
OPS_PORTAL_SYNC_TOKEN=<same value as AgenticFramework/.env OPS_PORTAL_SYNC_TOKEN>

# Production runtime backends
DATABASE_URL=postgresql://user:pass@localhost:5433/my-tenant-db
REDIS_URL=redis://localhost:6379/0
TEMPORAL_ADDRESS=localhost:7233

# Workflow engine (temporal | celery)
WORKER_BACKEND=temporal
IDEMPOTENCY_BACKEND=postgres
BUDGET_BACKEND=postgres

# HITL encryption — must match the value in AgenticFramework/.env
HITL_ENCRYPTION_KEY=<same value as AgenticFramework/.env HITL_ENCRYPTION_KEY>
ENVIRONMENT=production                   # development | staging | production
```

### GitHub Actions secrets

Set these in **Settings → Secrets and variables → Actions** for each tenant repo:

| Secret | Required for | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | CI eval judge, hybrid-mode tests | One of these two is required |
| `OPENAI_API_KEY` | CI eval judge, hybrid-mode tests | One of these two is required |
| `AGENT_PHOENIX_ENDPOINT` | Trace export from CI | Optional — CI passes without it |
| `OPS_PORTAL_URL` | CD → portal history sync | Optional — sync skipped if absent |
| `OPS_PORTAL_SYNC_TOKEN` | CD → portal history sync | Required if `OPS_PORTAL_URL` is set |
| `DEPLOY_COMMAND` | Production deploy step | Platform-specific (Fly, Railway, ECS, etc.) |
| `ROLLBACK_COMMAND` | Rollback on smoke failure | Optional — prints guidance if absent |

---

## 2. Step-by-Step: Setup → Run → Test → Eval → Deploy → Operate

This section is the linear, copy-pasteable path from a clean machine to a
tenant running in production with CI/CD and monitoring in place. **Every
step uses the same worked example — `examples/oil-price-agent`** — so you
can follow along with one concrete app instead of a generic placeholder;
swap in your own tenant repo once you've seen the shape end to end. Each
step links into the detailed Part (A–G) for background — read this section
to execute, read the Parts when something needs explaining.

Testing is covered twice, deliberately: [§2.3](#23--test-every-feature-cli)
is CLI-only (the same commands CI runs, no browser needed) — start there if
you're scripting/automating. [§2.3b](#23b--manual-test-walkthrough-the-uis)
is a click-through of every UI surface (Phoenix, Ops Portal, the In-App
Widget) using the example app's data, including the HITL/DLQ "edit a
failing payload and replay it" flow — start there if you want to actually
see what an operator sees.

### 2.1 — Setup

```bash
# Install (Part A) — vendors scripts/hooks/templates to ~/.agent-framework,
# sets git's global init.templateDir (developer mode; use --mode enterprise
# to skip that — see Part G).
curl -fsSL https://raw.githubusercontent.com/bobbyaqlaar/AgentSmith/main/install-ai-stack.sh | bash
source ~/.zshrc

# Identity — every span/log/audit entry attributes to this
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"

# Mode — pick one (switch anytime)
ai-mode-local     # 100% offline, Ollama, zero cost
ai-mode-hybrid    # cloud frontier models, needs ANTHROPIC_API_KEY/OPENAI_API_KEY

# Health check — confirms Phoenix, mode deps, no unresolved issues
ai-stack-check
```

Production-runtime extras, only if you'll exercise Part D for real — run from the **AgentSmith root**:

```bash
# Run from: AgentSmith root
source .venv/bin/activate   # activate the venv created in §1 Prerequisites
pip install psycopg2-binary redis temporalio langgraph-checkpoint-postgres cryptography
```

**Standing infra:** if Docker is available, `ai-dashboard-start` manages a
machine-wide stack (Phoenix + Postgres + Ops Portal, `restart:
unless-stopped`) shared across every repo on this machine — not just the
one you're in. Vendored to `~/.agent-framework/observability/` during
install (`docker-compose.yml` + `init-db/` + `portal/`, copied from this
repo's own — see `docker-compose.yml`'s header for the manual equivalent).
Without Docker, or in a repo that opts out (next paragraph), it falls back
to a plain-process Phoenix launch with no Postgres/Ops Portal — unchanged
from the original solo-dev behavior.

**Per-repo opt-out:** `touch .agenticframework/no-shared-infra` before
`git init`/`ai-tenant-init` in a repo that needs full isolation (a client
demo, an air-gapped environment, or just not wanting this repo's traces on
the shared instance). `ai-dashboard-start` then always uses the standalone
plain-process Phoenix path for that repo, and `ai-tenant-init` won't nudge
you toward the shared Ops Portal's env vars in its scaffolding output.

---

> **Starting a new tenant app — nothing to copy manually.**
>
> For any repo that is not based on the oil-price-demo example, the full
> scaffolding is handled automatically — no files need to be copied from
> the AgenticFramework directory:
>
> | What you get | How it arrives |
> |---|---|
> | `.agent-rfc/`, `.cursorrules`, `CLAUDE.md`, `.agents/skills/`, Knowledge Graph seed | `post-checkout` hook fires on `git init -b main` |
> | `.agenticframework/tenant.yaml`, `.github/workflows/ci-*.yml`, `cd-staging.yml`, `cd-production.yml` | `ai-tenant-init <id> --stack <stack>` |
> | `.env` | You create from the §1b template |
> | `runtime/` (LLM gateway, base workflow, idempotency, DLQ, …) | **Never copied** — accessed via `$AGENTSMITH_DIR/runtime` at run time |
>
> What you write yourself: `worker.py`, `workflows/`, `workflows/activities.py`
> — use `examples/oil-price-agent/` as a structural reference only.
>
> ```bash
> mkdir $REPO_DIR/my-app && cd $REPO_DIR/my-app
> git init -b main                               # hooks fire automatically
> ai-tenant-init my-app --stack python-fastapi   # scaffolds tenant.yaml + CI/CD
> # create .env from §1b template, then write your worker.py and workflows/
> ```

---

### 2.2 — Run the example app

The example app lives inside the AgenticFramework repo as a reference, but
you should run it as a proper standalone tenant — in its own directory,
outside the framework root, with its own git history and `.env`. This
mirrors exactly how you'd set up any real tenant app.

**Step 1 — Create the tenant project outside the framework root**

```bash
# Run from: anywhere outside AgenticFramework/
mkdir $REPO_DIR/oil-price-demo && cd $REPO_DIR/oil-price-demo
git init -b main    # post-checkout hook fires: installs .agent-rfc/, .cursorrules,
                    # CLAUDE.md, .agents/skills/, CI workflow templates,
                    # Knowledge Graph seed, .agenticframework/enabled marker
```

**Step 2 — Copy the example app files into the new directory**

```bash
# Run from: $REPO_DIR/oil-price-demo
cp -r $AGENTSMITH_DIR/examples/oil-price-agent/. .

# Copy the model registry — defines which LLM each model_hint routes to.
# Without this, the worker falls back to built-in defaults which may reference
# deprecated model IDs and cause 400 errors from the Anthropic/OpenAI API.
cp $AGENTSMITH_DIR/runtime/models.yaml .
```

**Step 3 — Create the tenant `.env`**

```bash
# Run from: $REPO_DIR/oil-price-demo
cat > .env << 'EOF'
TENANT_ID=oil-price-demo
ANTHROPIC_API_KEY=sk-ant-...          # or OPENAI_API_KEY
AGENT_PHOENIX_ENDPOINT=http://localhost:6006
OPS_PORTAL_URL=http://localhost:3000
OPS_PORTAL_SYNC_TOKEN=<same value as AgenticFramework/.env OPS_PORTAL_SYNC_TOKEN>
DATABASE_URL=postgresql://phoenix:phoenix@localhost:5433/agenticframework
REDIS_URL=redis://localhost:6379/0
TEMPORAL_ADDRESS=localhost:7233
WORKER_BACKEND=temporal
IDEMPOTENCY_BACKEND=postgres
BUDGET_BACKEND=postgres
HITL_ENCRYPTION_KEY=<same value as AgenticFramework/.env HITL_ENCRYPTION_KEY>
ENVIRONMENT=development
EOF
echo ".env" >> .gitignore
```

**Step 4 — Start the shared infra (if not already running)**

```bash
# Run from: AgenticFramework/
ai-dashboard-start    # Phoenix at :6006, Postgres, Ops Portal at :3000
```

**Step 5 — Run the app**

*A. Without Temporal* — exercises LLM Gateway + budget/cost path only (fastest, no extra services):

```bash
# Run from: $REPO_DIR/oil-price-demo
source $AGENTSMITH_DIR/.venv/bin/activate
set -a && source .env && set +a   # load tenant .env into current shell

python3 -c "
import sys, asyncio
sys.path.insert(0, '$AGENTSMITH_DIR/runtime')
from llm_gateway import LLMGateway
async def main():
    gw = LLMGateway(tenant_id='oil-price-demo')
    result = await gw.complete(
        prompt='Given oil prices [70,71,69,72], predict the next price as JSON.',
        model_hint='validator'
    )
    print(result.text, result.cost_usd)
asyncio.run(main())
"
```

This produces a real trace in Phoenix and a real budget record — enough to
drive the §2.3b Ops Portal walkthrough without standing up Temporal at all.

*B. With Temporal* — the full durable-workflow path, including the HITL gate and DLQ:

```bash
# Run from: $REPO_DIR/oil-price-demo

# Temporal CLI (server) — separate from the Python SDK; install once:
brew install temporal          # macOS — see https://docs.temporal.io/cli for other platforms

# Temporal Python SDK — install into the venv if not already present:
pip install temporalio

# Copy the helper scripts from the framework example (if not already there)
cp $AGENTSMITH_DIR/examples/oil-price-agent/trigger_workflow.py .
cp $AGENTSMITH_DIR/examples/oil-price-agent/resolve_hitl.py .

temporal server start-dev &   # or: docker run -p 7233:7233 temporalio/auto-setup

set -a && source .env && set +a
python3 worker.py &            # starts the Temporal worker (background)

python3 trigger_workflow.py    # submits the workflow and waits for result
```

The `95` outlier in the default price series is deliberate — it's >3 standard
deviations from the rest, which trips the HITL gate. The workflow pauses and
waits for an approval signal for up to 24h. Resolve it from a second terminal:

```bash
# Second terminal — Run from: $REPO_DIR/oil-price-demo
set -a && source .env && set +a
python3 resolve_hitl.py           # approve (default)
python3 resolve_hitl.py --reject  # or reject
```

### 2.3 — Test every feature (CLI)

Run these from the framework repo root (not your tenant project) to
validate the framework itself; see [§9 Testing Checklist](#9-testing-checklist)
for the exact same commands wired into CI.

```bash
# Hooks: opt-in gate + enterprise RFC gate (throwaway repos, no side effects)
python3 scripts/verify_system.py --check-hooks

# Knowledge Graph: rebuild via map_codebase.py and assert non-empty with known nodes (Pillar 2 / P10a)
python3 scripts/verify_system.py --check-kg

# Trace redaction: staging (hashed) + production (truncated + HITL blob) profiles
ENVIRONMENT=staging    python3 scripts/verify_system.py --check-redaction
ENVIRONMENT=production python3 scripts/verify_system.py --check-redaction

# LLM Gateway budget reservation race, idempotency store, DLQ — needs a throwaway Postgres
docker run -d --name pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_USER=test -e POSTGRES_DB=test -p 5432:5432 postgres:16-alpine
export DATABASE_URL="postgresql://test:test@localhost:5432/test"
export IDEMPOTENCY_BACKEND=postgres
pytest runtime/test/ -v
python3 scripts/verify_system.py --check-idempotency
python3 scripts/verify_system.py --check-dlq

# On-prem deployment template — compose/proxy/Helm syntax, no live cluster needed
python3 scripts/verify_system.py --check-onprem-deploy

# Ops Portal: RBAC/cross-tenant isolation + audit log HMAC/tamper detection
cd portal && npm install && npx tsc --noEmit
npm run db:migrate
npm test                                    # authz.test.ts — no DB-dependent assertions
AUDIT_LOG_HMAC_KEY=test-key npm run test:db  # auditLog.test.ts — needs $DATABASE_URL
npm run build
cd ..

# In-App Widget: XSS-attribute-injection regression suite + "running" status rendering
cd templates/in-app-widget && npm install && npm test && cd ../..

docker rm -f pg-test
```

A passing run here is the same bar CI enforces — see `.github/workflows/self-test.yml`'s `python`, `python-behaviour`, `portal`, and `widget` jobs.

### 2.3b — Manual test walkthrough: the UIs

Three surfaces, walked through in the order an operator would actually
hit them after a problem report comes in: trace-level detail (Phoenix) →
cross-tenant ops view (Ops Portal) → what the end user sees (In-App
Widget). Assumes §2.2's Option A or B already produced at least one real
trace/spend record for `oil-price-demo`, and `ai-dashboard-start` is
running (Phoenix + Postgres + Ops Portal).

**1. Phoenix — `http://localhost:6006`**

- Open the **Traces** tab for the `default` project. You should see the
  span from §2.2's `gw.complete()` call (or the full workflow's three
  spans if you ran Option B), each carrying `tenant.id=oil-price-demo`,
  `llm.model_name`, `llm.gateway.cost_usd`.
- Click into a span → confirm `input.value`/`output.value` are visible in
  `development`/`staging` profiles (or redacted, per §D.2, if you set
  `ENVIRONMENT=production` for the call).
- **Annotations tab** (only relevant if you ran Option B and a HITL gate
  fired): this is the *other* HITL mechanism — the golden-dataset
  promotion loop (UserManual.md §9), distinct from the production
  workflow-pause HITL gate you resolved via `hitl_approved` signal above.
  Annotating a span here is what `ai-test-evals`/`sync-ui-feedback.py`
  later promotes into `golden_evals.json`.

**2. Ops Portal — `http://localhost:3000`** (basic auth: `$OPS_PORTAL_USER`/`$OPS_PORTAL_PASSWORD` from `.env`)

- **Tenant list** (`/`) — confirm `oil-price-demo` is listed (auto-registered
  on first trace/spend) with non-zero spend.
- **Tenant detail** (`/tenants/oil-price-demo`) — click the tenant. Confirm:
  - **Spend this month** / **Budget cap** metric cards (cap shows `—` until
    `tenant.yaml`'s `gateway.budget_cap_usd` is synced — see §2.5).
  - **Run status** — reflects the *last* `gw.complete()` call's outcome
    for this tenant: **Operational** after a successful call, **Degraded**/
    **Failed** otherwise. **Important:** a workflow parked on a HITL/
    recoverable-step wait (Option B's `95` outlier) does **not** show
    **Working** during that wait — `_report_run_status("running", ...)` is
    only called for the few seconds an actual `gw.complete()` call is
    in flight, not for the duration of `workflow.wait_condition`'s 24h
    signal wait, which calls nothing. **Working** is real and demonstrated
    in the In-App Widget step below, but it's not automatically tied to
    "a human hasn't responded to HITL yet" — a tenant that wants the
    widget to show in-progress for the *entire* HITL wait would need to
    call `gw._report_run_status(run_id, "running", workflow_id=...)`
    themselves at the start of the wait (there's no built-in mechanism
    that does this for you, since `run_with_hitl_gate`/
    `run_with_recoverable_step` only touch the DLQ, never `agent_runs`).
  - **Phoenix: reachable** badge, plus **Last 24h: N trace(s)** with an error
    rate badge once there's enough trace volume to compute one (§P2c).
- **Dead-letter queue** (`/dlq`) — see the dedicated HITL/DLQ walkthrough
  immediately below; this is the newest, most hands-on part of the portal.
- **Audit log** (`/audit`) — confirms every admin action above (if you're
  logged in as admin) is recorded with an HMAC signature.

**2a. HITL/DLQ — edit a failing payload and replay it (the CRM-style example)**

This demonstrates `run_with_recoverable_step` without needing a full
Temporal cluster — simulating the exact "agent hallucinated a field name"
scenario directly against `runtime/dead_letter.py`, the same code path a
real recoverable-step failure goes through:

```bash
# 1. Simulate the failure landing in the DLQ, as if a tool call had just
#    rejected {"account_status": "active"} (schema wants "status"). Uses
#    the same agenticframework database the Ops Portal reads (the repo
#    root .env sets POSTGRES_USER/PASSWORD; 5433 is the host-side port
#    docker-compose.yml publishes for the AgentSmith Postgres):
set -a; source .env; set +a
DATABASE_URL="postgresql://${POSTGRES_USER:-phoenix}:${POSTGRES_PASSWORD:-phoenix}@localhost:5433/agenticframework" \
  python3 -c "
import sys; sys.path.insert(0, 'runtime')
from dead_letter import DeadLetterQueue, REASON_VALIDATION_ERROR
dlq = DeadLetterQueue()
entry = dlq.enqueue(
    payload={'customer_id': 102, 'account_status': 'active'},
    error='account_status is not a valid property',
    tenant_id='oil-price-demo',
    reason=REASON_VALIDATION_ERROR,
)
print('Created DLQ entry:', entry.task_id)
"
```

- Open **`/dlq`** in the portal — `oil-price-demo` now shows 1 pending entry.
- Click through to **`/dlq/oil-price-demo`** — the entry renders with an
  editable JSON textarea pre-filled with the failing payload and the
  `validation_error` reason badge.
- Edit the textarea: change `"account_status": "active"` to `"status":
  "active"`.
- Click **Discard** instead of Replay for this manual entry (it has no
  `workflow_id`, since it wasn't created by a real parked workflow — Replay
  would correctly report `resumable: false` since there's no tenant
  `replay_webhook_url` configured yet either). To see a *real* resumable
  entry and an actual live-workflow resume, run §2.2 Option B with the
  `95` outlier, let it park on the HITL gate, then check `/dlq/oil-price-demo`
  while it's waiting — that entry, if you wire up `runtime/replay_webhook_server.py`
  per §D.4, *is* resumable.

**3. In-App Widget**

```bash
# Mint a read-only widget token for the example tenant
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" -X POST http://localhost:3000/api/tenants/oil-price-demo/widget-token
# => {"token": "...", "note": "Store this now..."}
```

Serve `widget.js` locally and open a throwaway HTML file against it:

```bash
cd templates/in-app-widget && python3 -m http.server 8099 &
cat > /tmp/widget-demo.html << 'EOF'
<script src="http://localhost:8099/widget.js"></script>
<agent-status tenant-id="oil-price-demo" token="PASTE_TOKEN_HERE" portal-url="http://localhost:3000"></agent-status>
EOF
open /tmp/widget-demo.html   # or just open the file in a browser manually
```

(For a real embed, self-host `widget.js` from a tagged release per
`templates/in-app-widget/README.md` — the throwaway local server above is
for this walkthrough only.) You should see a colored dot + label:
**Operational** (green) after a successful call, **Degraded**/**Failed**
otherwise — confirming the exact status the Ops Portal's tenant detail
page showed above, from the end user's vantage point.

To see the **Working** (blue, in-progress) state specifically — confirmed
live, not just theoretical — report a `"running"` status directly and
reload the widget before reporting a terminal one:

```bash
set -a; source .env; set +a
OPS_PORTAL_URL=http://localhost:3000 OPS_PORTAL_SYNC_TOKEN="$OPS_PORTAL_SYNC_TOKEN" python3 -c "
import sys; sys.path.insert(0, 'runtime')
from llm_gateway import LLMGateway
LLMGateway(tenant_id='oil-price-demo')._report_run_status('manual-demo-run', 'running')
"
# Reload the widget HTML now — it shows Working. Then:
OPS_PORTAL_URL=http://localhost:3000 OPS_PORTAL_SYNC_TOKEN="$OPS_PORTAL_SYNC_TOKEN" python3 -c "
import sys; sys.path.insert(0, 'runtime')
from llm_gateway import LLMGateway
LLMGateway(tenant_id='oil-price-demo')._report_run_status('manual-demo-run', 'success')
"
# Reload again — back to Operational.
```

### 2.4 — Run evals

```bash
# Sync HITL annotations from Phoenix, then score against the golden dataset
ai-test-evals

# Same, explicitly, with a fail threshold (what CI actually runs)
python3 scripts/run-evals.py --fail-below 0.80

# Promote a production fix into the golden dataset (HITL-approved only)
ai-stack-promote <case-id> "<input query>" "<correct output>"

# Shadow-eval a sample of production traces (async, post-hoc — never blocks
# the live request; see SPECS.md §9). Needs real production-environment
# spans in Phoenix to have anything to sample.
python3 scripts/shadow-eval.py --sample-rate 0.05
```

Eval thresholds by environment (enforced in the CD workflows, not just
locally): development is warn-only, staging fails below 0.75, production
fails below 0.80 (SPECS.md §8/§24).

### 2.5 — Deploy

**Through GitHub CI/CD (cloud):**

```bash
# Scaffold a tenant repo with CI/CD wired in (Part C) — or, for the example,
# this is already done: examples/oil-price-agent/.agenticframework/tenant.yaml
cd my-project
ai-tenant-init my-tenant --stack python-fastapi   # or ts-react | go
git add .github .agenticframework && git commit -m "chore: scaffold tenant CI/CD"
git push -u origin main

# Configure once in GitHub: Settings → Environments → create "staging" and
# "production", each with required reviewers + environment-scoped secrets
# (DEPLOY_COMMAND, ANTHROPIC_API_KEY/OPENAI_API_KEY, OPS_PORTAL_* if syncing).
```

Then the pipeline runs itself on the branch flow already wired by `ai-tenant-init`:

| You do | Workflow that fires | Gate |
|---|---|---|
| Push a feature branch / open a PR | `ci-<stack>.yml` | lint, format check, test, eval scorecard (warn-only) |
| Merge to `develop` | `cd-staging.yml` | optional GHCR image build → eval fail-gate at 0.75 + post-deploy smoke test |
| `ai-tenant-promote my-tenant --from staging --to production` | Opens a `develop → main` PR | re-verifies the staging eval gate before opening it; **exact tenant-id match required** — refuses if `.agenticframework/tenant.yaml`'s id doesn't match exactly |
| PR reviewed + merged to `main` | `cd-production.yml` | optional GHCR image build → eval fail-gate at 0.80 + smoke test; **blocks + runs `rollback-notify` on smoke failure** (no automatic rollback execution — see §D.5 "Wire your platform") |

`cd-staging.yml`/`cd-production.yml`'s deploy step is
`.github/actions/deploy-placeholder` — set the `DEPLOY_COMMAND` secret on
the tenant's GitHub Environment to wire in your platform; unset, it no-ops
and prints platform-specific guidance (Fly/Railway/ECS/GCP Run). See §D.5
for the exact commands and the GHCR image-build step that runs before it.

---

**GCP deploy — step-by-step checklist (Cloud Run, any tenant):**

This is the copy-pasteable path to get both the worker and the demo UI running on Cloud Run.
The variables you need to substitute are listed at the top — set them once and all commands
below use them automatically.

```
YOUR_GCP_PROJECT_ID   — your GCP project ID (e.g. my-project-123)
YOUR_GITHUB_ORG       — GitHub org or username that owns the tenant repo (e.g. acme-corp)
YOUR_GITHUB_REPO      — tenant repo name (e.g. oil-price-demo)
YOUR_WORKER_SERVICE   — Cloud Run service name for the worker (e.g. oil-price-worker-staging)
YOUR_UI_SERVICE       — Cloud Run service name for the demo UI (e.g. oil-price-demo-ui)
YOUR_TENANT_ID        — value of TENANT_ID env var in the worker (e.g. oil-price-demo)
YOUR_TEMPORAL_HOST    — host:port of your running Temporal server (e.g. temporal.example.com:7233)
YOUR_REGION           — Cloud Run region (e.g. us-central1)
```

**Step 1 — WIF setup (run once per GCP project; add a repo binding per additional repo):**

WIF is set up at the GCP project level, not per repo. If you are deploying a second repo
to the same GCP project (e.g. `oil-price-demo` to the same project as `AgentSmith`),
skip the pool/provider/SA creation and only run the **repo binding** command — the pool,
provider, and service account roles already exist.

*First repo on this GCP project (full setup):*
```bash
export GCP_PROJECT_ID=YOUR_GCP_PROJECT_ID
export GCP_PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format='value(projectNumber)')
export GITHUB_ORG=YOUR_GITHUB_ORG
export GITHUB_REPO=YOUR_GITHUB_REPO

gcloud iam workload-identity-pools create "github-actions-pool" \
  --project="$GCP_PROJECT_ID" --location="global"

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="$GCP_PROJECT_ID" --location="global" \
  --workload-identity-pool="github-actions-pool" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository"

gcloud iam service-accounts create "github-deployer" --project="$GCP_PROJECT_ID"

gcloud iam service-accounts add-iam-policy-binding \
  "github-deployer@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --project="$GCP_PROJECT_ID" --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$GCP_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/$GITHUB_ORG/$GITHUB_REPO"

for ROLE in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:github-deployer@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
    --role="$ROLE"
done

# Copy this output — it becomes GCP_WORKLOAD_IDENTITY_PROVIDER in Step 2:
echo "projects/$GCP_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider"
```

*Additional repo on the same GCP project (repo binding only):*
```bash
export GCP_PROJECT_ID=YOUR_GCP_PROJECT_ID
export GCP_PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format='value(projectNumber)')
export GITHUB_ORG=YOUR_GITHUB_ORG
export GITHUB_REPO=YOUR_GITHUB_REPO   # the new repo to authorize

gcloud iam service-accounts add-iam-policy-binding \
  "github-deployer@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --project="$GCP_PROJECT_ID" --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$GCP_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/$GITHUB_ORG/$GITHUB_REPO"

# GCP_WORKLOAD_IDENTITY_PROVIDER and GCP_SERVICE_ACCOUNT are the same values
# already set on the first repo — reuse them on the new repo's GitHub Environments.

# ⚠️  Also update the provider's attribute-condition to include the new repo:
gcloud iam workload-identity-pools providers update-oidc github-provider \
  --project="$GCP_PROJECT_ID" --location=global \
  --workload-identity-pool=github-actions-pool \
  --attribute-condition="assertion.repository in ['$GITHUB_ORG/YOUR_EXISTING_REPO', '$GITHUB_ORG/$GITHUB_REPO']"
# Without this update the new repo gets: unauthorized_client: rejected by attribute condition
```

**Step 2 — Set secrets on both GitHub Environments (`staging` AND `production`):**

Go to: **https://github.com/YOUR_GITHUB_ORG/YOUR_GITHUB_REPO/settings/environments**

Create `staging` and `production` environments (if they don't exist), then on each add:

| Secret | Value |
|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | output of the `echo` command in Step 1 |
| `GCP_SERVICE_ACCOUNT` | `github-deployer@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com` |
| `GCP_PROJECT_ID` | `YOUR_GCP_PROJECT_ID` |
| `DEPLOY_COMMAND` (staging) | `gcloud run deploy YOUR_WORKER_SERVICE --source . --region YOUR_REGION --project $GCP_PROJECT_ID --no-cpu-throttling --min-instances=1 --port=8080 --set-env-vars TENANT_ID=YOUR_TENANT_ID,TEMPORAL_ADDRESS=YOUR_TEMPORAL_HOST` |
| `DEPLOY_COMMAND` (production) | same, with the production service name substituted |
| `AGENT_MODEL_ARCHITECT` | `openai/gpt-oss-120b` (avoids Groq rate limits in eval) |

**Step 3 — Trigger the deploy:**

Push any commit to `develop` (or re-run the CD workflow manually in GitHub Actions):

```bash
# GitHub → YOUR_GITHUB_REPO → Actions → CD: Staging Deploy → Re-run all jobs
```

The `cd-staging.yml` workflow: authenticates via WIF → builds the worker image → deploys
`YOUR_WORKER_SERVICE` to Cloud Run.

The `cd-demo-ui.yml` workflow: authenticates via WIF → builds the demo UI from
`demo/Dockerfile` → deploys `YOUR_UI_SERVICE` to Cloud Run.

**Step 4 — Get the service URLs:**

```bash
gcloud run services describe YOUR_WORKER_SERVICE \
  --region YOUR_REGION --project YOUR_GCP_PROJECT_ID --format="value(status.url)"

gcloud run services describe YOUR_UI_SERVICE \
  --region YOUR_REGION --project YOUR_GCP_PROJECT_ID --format="value(status.url)"
```

**Step 5 — Smoke test the demo UI:**

Open the `YOUR_UI_SERVICE` Cloud Run URL in a browser. Select the **HITL — price spike**
preset and click **Start Workflow**. The UI should show the workflow running → pause for
HITL approval → display the result after you click **Approve**. See §D.5c for the full
HITL flow and what each button does.

**Step 6 — Promote to production:**

Once staging is verified:
```bash
# Open a develop → main PR and merge it
# cd-production.yml fires automatically, deploying the production worker service
# Update DEPLOY_COMMAND on the production environment to use the production service name
```

---

**On-premise / air-gapped (no cloud):**

```bash
cd examples/oil-price-agent   # or your own tenant repo
ai-onprem-deploy-scaffold     # writes deploy/onprem/
cp deploy/onprem/.env.example deploy/onprem/.env
# edit .env: APP_IMAGE_PROD (build your own, or point at the GHCR image
# cd-production.yml pushed), PROXY_ENGINE=traefik|envoy
deploy/onprem/scripts/up.sh
```

See §D.6 for canary/shadow traffic routing, Kubernetes/Helm for
high-compliance customers, and air-gapped image bundling.

### 2.6 — Operate

| Surface | What it shows | Where |
|---|---|---|
| **Phoenix** | This tenant's traces, evals, HITL annotation queue | `http://localhost:6006` (or your team server) |
| **Ops Portal** | Cross-tenant cost/spend + cap, real run status (incl. **Working**/in-progress), Phoenix error rate, per-tenant DLQ triage (edit/Replay/Discard), shadow-eval suggested promotions, signed audit log | `https://ops.example.com` (Part E) |
| **Demo UI (Streamlit)** | GUI for submitting oil-price workflows, viewing status, approving/rejecting HITL, seeing results — connects to the live Temporal server | Cloud Run: get URL via `gcloud run services describe YOUR_UI_SERVICE --region YOUR_REGION --project YOUR_GCP_PROJECT_ID --format="value(status.url)"` |
| **`.agent-history.log`** | Local append-only event log this tenant repo produces | `ai-stack-check` surfaces unresolved entries from it |
| **In-App Widget** | End-user-facing status badge (own tenant only, token-scoped) | embedded in the tenant's own app (Part F) |
| **GitHub Actions** | CI/CD run history, eval scorecard artifacts per run | the tenant repo's Actions tab |

**Demo UI quick-test after deploy:**
1. Open the `YOUR_UI_SERVICE` Cloud Run URL
2. Sidebar → pick **HITL — price spike** preset → click **Start Workflow**
3. Status refreshes automatically — workflow pauses at HITL gate
4. Click **Approve** → workflow completes → result (prediction, confidence, anomaly=True) appears in run history

**CLI alternative (no UI):** `scripts/resolve_hitl.py` in the oil-price-demo repo does
the same HITL signal from the terminal — useful for scripting or when the UI isn't deployed yet.

Day-to-day operational tasks (rotating tokens/keys, checking unresolved
issues, upgrading the framework version) are in [§10 Day-2 Operations](#10-day-2-operations).

---

## Part A — Solo Dev Install (recap)

Full detail is in [UserManual.md §1–2](./UserManual.md). The short version:

```bash
curl -fsSL https://raw.githubusercontent.com/bobbyaqlaar/AgentSmith/main/install-ai-stack.sh | bash
source ~/.zshrc
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"
ai-mode-local      # or ai-mode-hybrid
ai-dashboard-start
ai-stack-check
```

Everything below assumes this is done.

---

## Part B — Team-Shared Phoenix with Auth

An unauthenticated shared Phoenix instance is non-compliant (SPECS.md §15) —
the base `docker-compose.yml` binds Phoenix's own port to `127.0.0.1` only,
so by default it's **not reachable from other machines at all**.

### B.1 — Solo dev (unchanged)

```bash
docker compose up -d
curl http://localhost:6006/healthz   # works — you're on localhost
```

### B.2 — Team server: add the auth overlay

```bash
# Generate a bcrypt hash for the basic-auth password. The hash contains
# literal '$' characters that Compose's .env interpolation will otherwise
# corrupt — this one-liner escapes them correctly:
echo "PHOENIX_BASIC_AUTH_HASH=$(docker run --rm caddy:2-alpine caddy hash-password --plaintext '<your-password>' | sed 's/\$/\$\$/g')" >> .env
echo "PHOENIX_BASIC_AUTH_USER=ops" >> .env

# Base stack + auth overlay together (NOT just `docker compose up -d` —
# that alone leaves Phoenix loopback-only with no remote access at all)
docker compose -f docker-compose.yml -f docker-compose.auth.yml up -d
```

Verify:

```bash
curl http://localhost:6007/healthz                                    # 401, no creds
curl -u ops:<your-password> http://localhost:6007/healthz             # 200
```

Developers and CI then point at port **6007** (the auth sidecar), not 6006:

```bash
export AGENT_PHOENIX_ENDPOINT="http://ops:<password>@<server-ip>:6007"
```

See [docker-compose.yml](./docker-compose.yml) and
[docker-compose.auth.yml](./docker-compose.auth.yml) header comments for the
full rationale (why this is a separate file, not a Compose profile).

---

## Part C — Multi-Tenancy

A tenant is a customer application with its own independent repository,
agents, eval suite, and deployment track (SPECS.md §23).

### C.1 — Scaffold a new tenant repo

```bash
cd /path/to/your-tenant-repo   # must be a git repo
ai-tenant-init acme --stack python-fastapi
```

Stack options: `python-fastapi` (default), `go`, `ts-react`. Add
`--isolation dedicated` if this tenant needs its own worker pool (Part D.4).

This writes:
- `.agenticframework/tenant.yaml` — tenant id, isolation tier, framework version pin, per-environment Phoenix namespaces and eval thresholds
- `.github/workflows/ci-<stack>.yml`, `cd-staging.yml`, `cd-production.yml`

Re-running is idempotent — existing files are never overwritten.

### C.2 — Configure GitHub Environments

In the tenant repo: **Settings → Environments**, create `staging` and
`production`, each with:
- Required reviewers (production)
- Environment secrets: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `AGENT_PHOENIX_ENDPOINT`, `AGENT_OWNER_ID`

### C.3 — Promote staging → production

```bash
ai-tenant-promote acme --from staging --to production
```

This verifies the staging eval gate (`run-evals.py --fail-below 0.75`) and,
only if it passes, opens a `develop → main` PR via `gh pr create` — it never
pushes directly to `main`.

### C.4 — Dedicated isolation tier

If you scaffolded with `--isolation dedicated`, provision the tenant's own
Kubernetes worker pool:

```bash
cd runtime/k8s/dedicated-tenant
./render.sh acme my-registry/acme-worker:1.0.0 --apply

kubectl create secret generic agenticframework-secrets -n tenant-acme \
  --from-literal=DATABASE_URL="postgresql://..." \
  --from-literal=ANTHROPIC_API_KEY="..." \
  --from-literal=OPENAI_API_KEY="..." \
  --from-literal=AGENT_OWNER_ID="..."
```

The Deployment will sit at `CreateContainerConfigError` until that secret
exists — this is intentional, not a bug: it cannot silently start without
tenant-scoped credentials. See
[runtime/k8s/dedicated-tenant/README.md](./runtime/k8s/dedicated-tenant/README.md).

---

## Part D — Production Runtime

`scripts/multi_agent_system.py` / `local_agent_stack.py` are the **dev/IDE**
path. Production agent execution uses `runtime/` instead — never deployed
directly from this repo (tenant repos build their own worker image, §25).

### D.1 — LLM Gateway (budget + degrade ladder)

```python
from runtime.llm_gateway import LLMGateway

gateway = LLMGateway(tenant_id="acme", budget_cap_usd=150.0)
result = await gateway.complete(prompt="...", model_hint="developer")
```

Model registry: `runtime/models.yaml` (framework defaults) →
tenant-repo-root `models.yaml` (override) → `.agenticframework/tenant.yaml`
`gateway.routing_overrides` (per-role shorthand).

Budget backend — set before instantiating:

```bash
export BUDGET_BACKEND=postgres   # or redis, or memory (dev/CI only)
export DATABASE_URL="postgresql://..."
```

When the tenant's monthly spend breaches the cap, the gateway automatically
walks the `degrade_to` chain in `models.yaml` (e.g. `architect` →
`developer` → `validator` → `fast`/Ollama) rather than failing outright. If
the requested tier is already the free/local tier, a breach never blocks it.

Budget spend is reserved atomically **before** the provider call (an upper
bound from `max_tokens`), then reconciled to the actual cost afterward —
not read-checked-then-written-after, which would let concurrent in-flight
calls for the same tenant all slip past the cap before any of them recorded
spend. If a reservation would exceed the cap, `complete()` raises
`BudgetExceededError` immediately rather than making the provider call.

### D.2 — Trace redaction

```bash
export ENVIRONMENT=development   # explicit opt-in for local/IDE work — see note below
```

```python
from runtime.trace_redactor import TraceRedactor
provider.add_span_processor(TraceRedactor())
```

`$ENVIRONMENT` is resolved by the shared, **fail-closed**
`runtime/environment.py:get_environment()` — an unset or unrecognized value
(typo, blank, etc.) resolves to `"production"`, never to `"development"`.
This is a deliberate change from "missing var = least-restrictive
default": a worker that loses its `ENVIRONMENT` var should fail toward
*more* redaction and *more* durable checkpointing, not less. **Set
`ENVIRONMENT=development` explicitly for local/IDE work** — don't rely on
it being the default for an unset variable.

| `ENVIRONMENT` (resolved) | Behaviour |
|---|---|
| `development` (must be set explicitly) | No scrubbing |
| `staging` | Secrets/PII replaced with `[REDACTED:<hash8>]`; structure preserved |
| `production` (also the fallback for unset/unrecognized) | Scrubbed + truncated to 50 chars; full original payload stored in an AES-256-GCM-encrypted blob (`HITL_ENCRYPTION_KEY` / `HITL_ENCRYPTION_KEY_<TENANT>`), keyed per-span by `{trace_id}.{span_id}.{attr_key}` |

The tenant id used for HITL blob encryption is read from each span's own
`tenant.id` attribute, not bound once when the processor is constructed —
required for correctness on a shared (non-dedicated) worker pool processing
spans for more than one tenant in the same process.

CI check (also wired into `cd-staging.yml` / `cd-production.yml`):

```bash
ENVIRONMENT=production python3 scripts/verify_system.py --check-redaction
```

### D.3 — Postgres checkpointer (staging/production LangGraph)

```bash
export ENVIRONMENT=production
export DATABASE_URL="postgresql://..."
```

`scripts/multi_agent_system.py` uses the same `get_environment()` resolver
as D.2 above and will use a real `PostgresSaver` instead of `MemorySaver`
whenever the resolved environment is `staging`/`production` — **including
an unset or unrecognized `ENVIRONMENT`**, which now resolves to
`production` rather than `development`. It **raises** rather than silently
falling back if `DATABASE_URL` is missing in that case — `MemorySaver`
loses all HITL pause state on crash and is dev-only by design (SPECS.md §25,
§28). Local/IDE runs must set `ENVIRONMENT=development` explicitly to get
`MemorySaver` without a `DATABASE_URL`.

### D.4 — Temporal workflow pattern, HITL, and the recoverable-step DLQ

`runtime/workflows/base_workflow.py` has two related but distinct patterns:

- **`run_with_hitl_gate`** — the original approve/reject pattern: execute →
  if review is requested, wait on the `hitl_approved` signal (boolean) up
  to 24h → dead-letter terminally on timeout or rejection.
- **`run_with_recoverable_step`** — for failures a human can *fix*, not
  just approve/reject (e.g. an agent's tool call hallucinates a field name
  — `{"account_status": "active"}` where the schema expects `"status"` —
  and the actual fix is correcting the JSON, not approving/rejecting
  anything). On activity failure, the workflow **stays alive** (it does
  not terminate), enqueues a structured DLQ entry carrying its own
  `workflow_id`/`gate_id`, and waits on the `human_fix_payload` signal up
  to a caller-configurable timeout. Once a human edits the payload in the
  Ops Portal's DLQ view and clicks Replay, the SAME workflow resumes with
  the corrected payload — not a fresh execution. Bounded by
  `max_attempts` (default 5) so a human submitting fixes that keep failing
  doesn't park a workflow forever.

`examples/oil-price-agent/workflows/` shows the older HITL-gate pattern
applied to a concrete domain — copy that shape into your own tenant repo,
don't deploy the example directly.

```bash
pip install temporalio
cd examples/oil-price-agent
TENANT_ID=oil-price-demo TEMPORAL_ADDRESS=localhost:7233 python3 worker.py
```

**Important Temporal detail** (caught by a live test, not assumed):
`run_with_recoverable_step` passes `retry_policy=RetryPolicy(maximum_attempts=1)`
to the gated `execute_activity` call — without this, Temporal's *default*
retry policy retries the same failing payload indefinitely (with backoff)
until `start_to_close_timeout`, which is pointless for a validation error
and means the workflow doesn't even reach the DLQ-enqueue/wait step for
up to 10 minutes. The method's own attempt loop is the intended retry
mechanism (only after a human supplies a *different* payload), not
Temporal's.

`runtime/idempotency.py` and `runtime/dead_letter.py` are Postgres-backed
(`IDEMPOTENCY_BACKEND=postgres`/`redis`, `DATABASE_URL`/`REDIS_URL`) — both
create their own table on first use, same pattern as
`runtime/llm_gateway.py`'s budget backend. Verify against a throwaway
Postgres:

```bash
docker run -d --name pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_USER=test -e POSTGRES_DB=test -p 5432:5432 postgres:16-alpine
export DATABASE_URL="postgresql://test:test@localhost:5432/test"
python3 scripts/verify_system.py --check-idempotency
python3 scripts/verify_system.py --check-dlq
```

**Closing the HITL/DLQ loop end-to-end** — `runtime/dead_letter.py`'s
`enqueue()` now accepts `reason` (`validation_error`/`tool_call_error`/
`hitl_timeout`/`hitl_rejected`/`infra_error` — see the `REASON_*`
constants), `workflow_id`, and `gate_id`, and posts to
`SLACK_WEBHOOK_URL`/`TEAMS_WEBHOOK_URL` on enqueue if configured (a human
is pinged the moment something needs attention, not only when they check
`/dlq`). `enqueue()` is idempotent on `task_id`
(`ON CONFLICT DO NOTHING`) — protects against a Temporal retry of the
activity that calls `enqueue()` itself creating duplicate rows for one
failure. `replay(task_id, override_payload=...)` is the CRM-example path:
the override is what actually gets signaled/persisted, not the original
failing payload.

`DeadLetterQueue.replay(task_id)` still takes an optional `replay_handler`
callback at construction — without one, `replay()` only marks the entry
`status="replayed"` and logs the attempt; it does NOT automatically
resume anything. **`runtime/temporal_replay.py`'s `make_temporal_replay_handler(client)`
is the concrete Temporal implementation** — it signals the *live, still-
parked* workflow at `entry.workflow_id` (only resumable because
`run_with_recoverable_step` kept it alive, unlike a terminated
`run_with_hitl_gate` dead-letter) with `human_fix_payload(gate_id, fix)`.

**The portal-to-worker bridge is a per-tenant webhook, not a direct
Temporal connection** — the Ops Portal (Next.js) has no Temporal client
and isn't meant to gain one (this module is deliberately engine-agnostic;
a tenant could run Celery instead). When a human edits a payload in the
portal's `/dlq/<tenantId>` view and clicks Replay, the portal HMAC-signs
the edited payload and POSTs it to **that tenant's own**
`replay_webhook_url` (`tenants.replay_webhook_url`/`replay_webhook_secret`,
synced from `.agenticframework/tenant.yaml`'s `hitl.replay_webhook_url`/
`hitl.replay_webhook_secret` the same way `budget_cap_usd` is synced) —
deliberately per-tenant, so a human-in-the-loop fix always reaches the
specific team running that tenant's worker, never a single shared
endpoint serving every tenant. `runtime/replay_webhook_server.py` is the
reference receiver: verifies the HMAC signature, then calls
`DeadLetterQueue(replay_handler=make_temporal_replay_handler(client)).replay(task_id, override_payload=edited_payload)`.
It's a stdlib `http.server` reference, not a hardened production server —
same "pattern, not prescription" posture as `base_workflow.py`/`worker.py`;
adapt it into your actual web framework.

Concrete `.agenticframework/tenant.yaml` syntax for the sync (both keys
required together — `scripts/sync-portal-history.py` skips the sync with
a warning if only one is set, or if the URL isn't `http(s)`):

```yaml
hitl:
  replay_webhook_url: "https://your-internal-host:8090/replay"
  replay_webhook_secret: "a-random-shared-secret-matching-REPLAY_WEBHOOK_SECRET"
```

**Known limitation:** removing the `hitl` section from `tenant.yaml` does
not clear `replay_webhook_url`/`_secret` on the portal — `upsertTenant`'s
`COALESCE` (same as `budget_cap_usd`) means a sync only ever sets a value,
never unsets one. To fully disable replay routing for a tenant, clear the
columns directly: `UPDATE tenants SET replay_webhook_url = NULL,
replay_webhook_secret = NULL WHERE tenant_id = '<id>'`.

Discarding an entry (no replay) is safe directly from the portal — it
never needs to resume a live workflow — via `POST /api/dlq/:taskId/discard`.
Replaying always requires the round-trip above, even for entries without
a `workflow_id` (e.g. ones from `run_with_hitl_gate`'s terminal
dead-letter) — `DeadLetterQueue.replay()` still calls the configured
handler, which logs a no-op warning when there's no live workflow to
signal, same as before this redesign.

The Ops Portal's DLQ view (`GET /api/dlq`) reports `wired: false` until a
worker has constructed a `DeadLetterQueue` at least once against the same
`DATABASE_URL` — that's a genuine "has anything actually run against this
DB" signal, not a placeholder for an unimplemented backend.

**Verified live, not just unit-tested in isolation:** a real
`temporalio.testing.WorkflowEnvironment` test exercised the exact CRM
example end-to-end — workflow fails on the hallucinated field, stays
alive, `human_fix_payload` signal with the corrected JSON resumes it, and
the activity succeeds — confirming both the workflow-side mechanics and
that the `RetryPolicy(maximum_attempts=1)` fix is load-bearing (without
it, the same test hung for minutes on Temporal's default retry policy
before ever reaching the wait). Separately, the portal-to-webhook bridge
was verified against the real running Ops Portal container plus a stub
HMAC-verifying receiver: `POST /api/dlq/:taskId/replay` with an edited
payload produced a correctly-signed webhook call with the edited JSON
intact.

### D.5 — Wire your platform (CD deploy + rollback)

Before the deploy step, both CD workflows run
`.github/actions/build-push-ghcr`: if a `Dockerfile` exists at the repo
root, it builds and pushes `ghcr.io/<org>/<repo>:<sha>` using the
workflow's own `GITHUB_TOKEN` (no extra registry secret) and exports the
image ref as `$IMAGE_REF` for the deploy step below to consume — e.g.
`DEPLOY_COMMAND = "gcloud run deploy myapp-staging --image $IMAGE_REF"`.
No Dockerfile present → this step skips cleanly (exit 0, no CD failure),
same "optional infra never fails CD" posture as the Ops Portal history
sync. This is also the artifact `templates/onprem-deploy/` (D.6 below)
expects — point its `APP_IMAGE_PROD`/`_CANARY`/`_SHADOW` at the pushed
`$IMAGE_REF` tags instead of building separately for on-prem.

`cd-staging.yml`/`cd-production.yml`'s deploy step is
`.github/actions/deploy-placeholder` — a documented composite action, not
literal text to find-and-delete. It runs `secrets.DEPLOY_COMMAND` if set on
the tenant's GitHub Environment; unset, it no-ops and prints the platform
commands below. No workflow YAML edit needed to wire in a real deploy:

```bash
# Set on the tenant's GitHub Environment (Settings → Environments → staging/production):
DEPLOY_COMMAND   = "flyctl deploy --app myapp-staging"        # Fly.io
DEPLOY_COMMAND   = "railway up --environment staging"          # Railway
DEPLOY_COMMAND   = "aws ecs update-service --cluster staging --service myapp --force-new-deployment"  # AWS ECS
DEPLOY_COMMAND   = "gcloud run deploy myapp-staging --image $IMAGE"  # GCP Run
```

On a post-deploy smoke-test failure, `cd-production.yml` invokes
`.github/actions/rollback-notify`: posts to Slack/Teams
(`SLACK_WEBHOOK_URL`/`TEAMS_WEBHOOK_URL` secrets, optional), runs
`secrets.ROLLBACK_COMMAND` if set, then fails the job (red status
preserved either way — notification/rollback never silently swallows the
failure):

```bash
ROLLBACK_COMMAND = "fly releases list && fly deploy --image <prev-image>"  # Fly.io
ROLLBACK_COMMAND = "railway rollback"                                      # Railway
ROLLBACK_COMMAND = "aws ecs update-service --task-definition <prev-arn>"   # AWS ECS
```

Actual rollback *execution* stays tenant-supplied (this framework has no
opinion on which platform CLI to run) — same posture as the deploy step.
Verified against `act` (local GitHub Actions runner): both actions execute
correctly with and without a configured command, and a forced failure
correctly propagates a red job status after rollback/notify run.

### D.5b — GCP deployment specifics (Vertex AI credentials + worker hosting)

§D.5 above covers `DEPLOY_COMMAND` generically, with `gcloud run deploy` as
one example value — that's enough if your tenant app only talks to direct
Anthropic/OpenAI APIs. If it routes any `model_hint` to `provider:
vertex_ai` (e.g. the `vertex_gemini` role added to `runtime/models.yaml` in
§2 above), CI/CD needs two more things `DEPLOY_COMMAND` alone doesn't give
you: a way for GitHub Actions to authenticate to GCP, and a decision about
*what kind* of compute actually runs `worker.py`.

**1. Authenticating GitHub Actions to GCP.**

The CD workflows (`cd-staging.yml`, `cd-production.yml`) already include a
`.github/actions/gcp-auth` step — it runs before the image build and deploy
steps and skips gracefully if neither GCP secret is configured. You only
need to set the right secrets on each GitHub Environment:

| Secret | What to set | Notes |
|---|---|---|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/<project-number>/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider` | **Preferred** — see one-time setup below |
| `GCP_SERVICE_ACCOUNT` | `github-deployer@<project-id>.iam.gserviceaccount.com` | Required alongside WIF |
| `GCP_SA_KEY` | base64-encoded service-account JSON key | Fallback only — long-lived secret, harder to rotate |
| `GCP_PROJECT_ID` | `my-gcp-project` | Used in `DEPLOY_COMMAND` / `models.yaml` |

`VertexAIAdapter` resolves credentials via `google.auth.default()`
(`runtime/provider_dispatch.py`) — after `gcp-auth` runs, ADC is written to
the runner filesystem so any subsequent step (`gcloud`, `kubectl`, the Python
gateway) is automatically authenticated.

**One-time GCP setup (Workload Identity Federation — recommended):**
```bash
# Run locally with gcloud authenticated to the target project:
export GCP_PROJECT_ID=my-gcp-project
export GCP_PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format='value(projectNumber)')
export GITHUB_ORG=my-org
export GITHUB_REPO=oil-price-sample   # or AgentSmith

gcloud iam workload-identity-pools create "github-actions-pool" \
  --project="$GCP_PROJECT_ID" --location="global"
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="$GCP_PROJECT_ID" --location="global" \
  --workload-identity-pool="github-actions-pool" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository"
gcloud iam service-accounts create "github-deployer" --project="$GCP_PROJECT_ID"
gcloud iam service-accounts add-iam-policy-binding \
  "github-deployer@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --project="$GCP_PROJECT_ID" --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/$GCP_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/$GITHUB_ORG/$GITHUB_REPO"

# Grant deployer SA the rights it needs:
for ROLE in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:github-deployer@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
    --role="$ROLE"
done

# The WIF provider resource name to set as GCP_WORKLOAD_IDENTITY_PROVIDER:
echo "projects/$GCP_PROJECT_NUMBER/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider"
```

**Service-account JSON key (simpler fallback — prefer WIF above):** generate
one (`gcloud iam service-accounts keys create key.json --iam-account=...`),
store its base64-encoded contents as `GCP_SA_KEY` on the GitHub Environment.
For the deployed runtime's own ADC, mount it as a Cloud Run/GKE secret volume
and set `GOOGLE_APPLICATION_CREDENTIALS` — never bake the key into the image.

**2. What actually gets deployed.** `gcloud run deploy` deploys a
request/response HTTP service — but `worker.py` (and any tenant's
Temporal-backed worker) is a long-running poller with no HTTP listener at
all. Don't assume Cloud Run "just works" here without one of:

| Option | Fit | Caveat |
|---|---|---|
| **Cloud Run, `--no-cpu-throttling --min-instances=1`** | Works for low/moderate-throughput workers; closest to the `DEPLOY_COMMAND` pattern already documented | No autoscaling on queue depth; you're paying for one always-on instance regardless of task-queue load. `worker.py` already serves `GET /healthz` on `$PORT` (default 8080) so Cloud Run's health checks have something to hit |
| **GKE (or any k8s)** | Best fit for a long-running poller — a `Deployment` with no `Service`/ingress needed at all, scales on whatever metric you choose (queue depth via KEDA, etc.) | More infra to operate — bring your own cluster; not scaffolded by `ai-onprem-deploy-scaffold` |
| **Compute Engine (single VM/MIG)** | Simplest mental model, no container platform needed | Manual scaling, no rolling-deploy story beyond replacing the VM/instance template yourself |

Set `DEPLOY_COMMAND` on each GitHub Environment to whichever platform you
choose. The `gcp-auth` step runs first so `gcloud`/`kubectl` is already
authenticated when `DEPLOY_COMMAND` executes:

```bash
# Cloud Run (worker.py already has /healthz — OPERATIONS.md §D.5b):
DEPLOY_COMMAND = "gcloud run deploy YOUR_WORKER_SERVICE \
  --image $IMAGE_REF \
  --region YOUR_REGION \
  --project $GCP_PROJECT_ID \
  --no-cpu-throttling \
  --min-instances=1 \
  --port=8080 \
  --set-env-vars TENANT_ID=YOUR_TENANT_ID,TEMPORAL_ADDRESS=YOUR_TEMPORAL_HOST,TEMPORAL_TLS=true"

# GKE (Deployment must already exist — this just rolls the new image):
DEPLOY_COMMAND = "gcloud container clusters get-credentials YOUR_CLUSTER --region YOUR_REGION --project $GCP_PROJECT_ID \
  && kubectl set image deployment/YOUR_WORKER_DEPLOYMENT worker=$IMAGE_REF"
```

Set `GCP_PROJECT_ID` as a GitHub Environment variable (not secret — no
credential, just a project identifier) so `DEPLOY_COMMAND` can reference
`$GCP_PROJECT_ID` without hardcoding it in the workflow YAML or in
`runtime/models.yaml` (§29 "Cloud-Native Provider Adapters").

**Live-verification status**: the Vertex AI *call path* was verified
live against a real GCP project (`gemini-2.5-flash` via
`LLMGateway.complete(model_hint="vertex_gemini")` — §29). The
`gcp-auth` composite action is now **fully verified end-to-end** through
real GitHub Actions runs against GCP project `agentsmith-500916` on
2026-07-01: both `bobbyaqlaar/oil-price-demo` and `bobbyaqlaar/AgentSmith`
completed successful staging + production deploys to Cloud Run. The
three worker-hosting options (Cloud Run, GKE, Compute Engine) have been
exercised for Cloud Run only — verify `kubectl` invocations against your
own project before relying on them.

**Multi-repo WIF note:** the WIF provider's `--attribute-condition` is a
single expression that applies to all repos bound to the pool. When adding
a second repo to the same GCP project, update the condition from a single
`==` to an `in` list:
```bash
gcloud iam workload-identity-pools providers update-oidc github-provider \
  --project="$GCP_PROJECT_ID" --location=global \
  --workload-identity-pool=github-actions-pool \
  --attribute-condition="assertion.repository in ['ORG/REPO1', 'ORG/REPO2']"
```
Forgetting this update causes `unauthorized_client: The given credential is
rejected by the attribute condition` for the new repo even if its WIF principal
binding is correctly set.

### D.5b-2 — Cloud SQL Auth Proxy for portal database (Cloud Run)

When deploying a Next.js portal (or any app) to Cloud Run that needs to connect to Cloud SQL, **do not** configure TCP + SSL cert verification. Cloud Run natively supports the **Cloud SQL Auth Proxy** via the `--add-cloudsql-instances` flag — it injects a sidecar that creates a Unix socket, handles Google-managed mTLS transparently, and never exposes TCP.

**Why not `sslmode=require` or `sslmode=no-verify`:**
- `sslmode=require` with `node-postgres` attempts full leaf-cert chain verification; Cloud SQL's cert is Google-managed and not in Node's default CA bundle → `UNABLE_TO_VERIFY_LEAF_SIGNATURE`.
- `sslmode=no-verify` skips verification entirely — MITM-vulnerable, not acceptable for production.

**Correct approach — Cloud SQL Auth Proxy via Unix socket:**

1. **Grant the Compute SA `roles/cloudsql.client`:**
   ```bash
   PROJECT_NUMBER=$(gcloud projects describe agentsmith-500916 --format='value(projectNumber)')
   COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
   gcloud projects add-iam-policy-binding agentsmith-500916 \
     --member="serviceAccount:${COMPUTE_SA}" \
     --role="roles/cloudsql.client"
   ```

2. **Add `--add-cloudsql-instances` to the DEPLOY_COMMAND:**
   ```bash
   gcloud run deploy agentsmith-portal-staging \
     --image $IMAGE_REF --region us-central1 --project $GCP_PROJECT_ID \
     --platform managed --allow-unauthenticated \
     --add-cloudsql-instances=agentsmith-500916:us-central1:temporal-pg \
     --set-secrets=DATABASE_URL=ops-portal-db-url:latest,...
   ```

3. **DATABASE_URL must use the Unix socket path** (stored in Secret Manager, never hardcoded):
   ```
   postgresql://USER:PASSWORD@/DBNAME?host=/cloudsql/PROJECT:REGION:INSTANCE
   # e.g.:
   postgresql://postgres:***@/agenticframework?host=/cloudsql/agentsmith-500916:us-central1:temporal-pg
   ```
   No `sslmode` param needed — the proxy socket is always mutually authenticated.

4. **Secret Manager accessor on Compute SA** — `gcloud run deploy --set-secrets` is resolved at deploy time by the Compute SA (not the deployer SA). Each new secret must grant the Compute SA accessor before deploy:
   ```bash
   gcloud secrets add-iam-policy-binding SECRET_NAME \
     --member="serviceAccount:${COMPUTE_SA}" \
     --role="roles/secretmanager.secretAccessor"
   ```

### D.5c — Demo UI (Streamlit) — Cloud Run deployment

The `demo/` directory in your tenant repo contains a Streamlit app (`demo/app.py`) that
provides a GUI frontend for the pipeline. It connects directly to the **live** Temporal
server — it is not a simulation. No changes to the existing Temporal worker, Postgres, or
Ops Portal setup are required; the demo app is a thin UI layer on top.

**Architecture:**
```
Browser → Streamlit (Cloud Run: YOUR_UI_SERVICE)
              │
              ├── temporalio.client → Temporal server (start workflow, poll, signal)
              └── (no direct DB — reads Temporal workflow state only)
```

**Environment variables (set via `--set-env-vars` or Cloud Run console):**

| Variable | Default | Notes |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | Override to point at your live Temporal server |
| `TEMPORAL_TLS` | `` (empty) | Set to `"1"` if Temporal server uses TLS |
| `TENANT_ID` | *(required)* | Must match the tenant ID registered in the worker |
| `PORT` | `8080` | Set automatically by Cloud Run |

**CD workflow:** `.github/workflows/cd-demo-ui.yml` deploys on push to `develop`/`main`
when any file under `demo/**` changes. It uses the `gcp-auth` composite action (same WIF
flow as the worker CD) and runs:
```bash
gcloud run deploy YOUR_UI_SERVICE \
  --source . \
  --dockerfile demo/Dockerfile \
  --region YOUR_REGION \
  --project $GCP_PROJECT_ID \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars TEMPORAL_ADDRESS=YOUR_TEMPORAL_HOST,TENANT_ID=YOUR_TENANT_ID
```

**Manual deploy** (once GCP secrets are set on the `staging` environment):
```bash
# From inside the tenant repo root
gcloud run deploy YOUR_UI_SERVICE \
  --source . \
  --dockerfile demo/Dockerfile \
  --region YOUR_REGION \
  --project YOUR_GCP_PROJECT_ID \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars TEMPORAL_ADDRESS=YOUR_TEMPORAL_HOST,TENANT_ID=YOUR_TENANT_ID
```

**Get the service URL after deploy:**
```bash
gcloud run services describe YOUR_UI_SERVICE \
  --region YOUR_REGION --project YOUR_GCP_PROJECT_ID \
  --format="value(status.url)"
```

**HITL flow via the demo UI:**
1. Enter a price series (or pick a preset from the sidebar) → click **Start Workflow**
2. The Streamlit app calls `client.start_workflow("OilPricePredictionWorkflow", ...)`
3. Status auto-refreshes — when the workflow halts for HITL approval, an
   **Approve / Reject** panel appears
4. Clicking Approve/Reject sends `handle.signal("hitl_approved", True/False)` —
   identical to what `scripts/resolve_hitl.py` does from the CLI
5. The workflow completes; the result (prediction, confidence, anomaly flag) is
   displayed in the run history table

**Spike preset:** uses series `[70.0, 70.1, 69.9, 70.0, 70.1, 70.0, 70.2, 69.8, 70.1, 70.0, 110.0]`
(10 stable values ~70 then spike to 110). This definitively exceeds the 3σ anomaly threshold
because the stable prefix keeps mean and σ tight — a short series with the outlier included
inflates σ and can mask the spike.

**Prerequisites:** GCP secrets must be set on the `staging` GitHub Environment (P11b in
`FIXES_AND_CLEANUP.md`) before the CD workflow can deploy. See §D.5b for the WIF setup.

---

### D.6 — On-premise / air-gapped deployment

For tenants whose customers run the agent app on their own hardware
instead of a managed cloud platform — opt-in, never auto-written the way
the CI/CD workflow templates are:

```bash
ai-onprem-deploy-scaffold   # run inside the tenant repo — writes deploy/onprem/
```

This copies `templates/onprem-deploy/` (vendored to
`~/.agent-framework/templates/onprem-deploy/` by `install-ai-stack.sh`,
same mechanism as `agent-rules.yaml`) into the repo. The template is
**stack-agnostic by design**, consistent with the framework's own
position as something that "provides a ready-to-use framework from design
to deploy to operate to continuously improve other applications built
with different architectures" — it doesn't know or assume your agent
app's internal language/framework, only that it ships as one container
image, listens on one HTTP port with `GET /healthz`, reads config from env
vars only (never a cloud secret manager — see D.6's secrets note below),
and logs JSON-Lines to stdout (already `runtime/agent_logger.py`'s
convention everywhere else in this framework).

**Two deployment targets**, picked based on the customer:

| Target | When | Command |
|---|---|---|
| Docker Compose (`deploy/onprem/`) | ~80% of on-prem customers — single bare-metal server/VM | `./scripts/up.sh` |
| Kubernetes / Helm (`deploy/onprem/kubernetes/`) | High-compliance enterprise customers running their own managed cluster who won't run raw Docker | `helm install` |

**Canary + shadow traffic, on-prem.** Cloud load balancers (ALB, Cloud Run
traffic splitting) aren't available on a customer's private hardware, so
the proxy/ingress ships *inside* the deployment package — choose per
customer via `PROXY_ENGINE=traefik|envoy` (Compose) or
`--set proxyEngine=traefik|envoy-gateway` (Helm):

- **Traefik** — simpler config, smaller learning curve; uses Traefik's
  native `weighted` + `mirroring` service kinds.
- **Envoy** — more precise traffic-shaping (`weighted_clusters` +
  `request_mirror_policies`), the better fit if the customer already runs
  Envoy/Envoy Gateway elsewhere.

Both render their proxy config from `.env` via
`scripts/render-traefik-config.py`/`render-envoy-config.py` (a real dict
+ `yaml.safe_dump`, not string templating) — verified directly: rendering
with canary+shadow images set produces a valid weighted+mirrored Traefik
dynamic config and a valid Envoy `weighted_clusters`/
`request_mirror_policies` bootstrap, and `docker compose config --quiet`
validates the resulting compose merge for both proxy engines plus the
optional `with-db` (pgvector) profile. On Kubernetes, `helm lint` and
`helm template` (default + canary/shadow/db enabled + both proxy engines)
all render valid manifests using the **core** Gateway API's
`backendRefs[].weight` (canary) and `RequestMirror` filter (shadow) —
note the K8s path has one real limitation vs. Compose: core Gateway API's
mirror filter has no percentage field (always mirrors 100% of matched
traffic), unlike Traefik's/Envoy's own native mirroring used directly in
Compose, which do support a percent. See
`templates/onprem-deploy/kubernetes/README.md` for the vendor-extension
workaround if a customer needs partial mirroring specifically on K8s.

**Mirroring vs. shadow-eval (P1c) — these are two different things, don't
conflate them:** D.6's shadow *traffic* mirroring tests a new version of
the whole app against live request shape before promotion, at the
proxy/infrastructure layer — it has no idea what your app does with a
mirrored request. The framework's separate shadow-eval sampler
(`scripts/shadow-eval.py`, SPECS.md §9) does *application-level*,
side-effect-safe shadow evaluation: judging a 5% sample of already-served
production traces after the fact by reading Phoenix, never re-executing
anything. If your agent has side effects (writes, external API calls), do
not point `APP_IMAGE_SHADOW`/`shadow.enabled` at a build that isn't
dry-run-safe — that's on your app's build, this template can't make that
safe for you given it treats your image as a black box.

**Air-gapped bundling:** `scripts/bundle-airgapped.sh` (run where there's
internet access) pulls + `docker save`s every image the stack needs —
app versions, the chosen proxy image, pgvector if enabled — into one
`onprem-bundle.tar.gz`; `scripts/load-airgapped.sh` (run on the
air-gapped server) `docker load`s it with zero registry calls. Transfer
via USB drive, secure copy, or a private registry mirror.

**Secrets:** strictly `.env` (Compose) or a pre-existing Kubernetes
`Secret` referenced by `envSecretName` (Helm) — no AWS Secrets Manager /
GCP Secret Manager call anywhere in this template, matching
`runtime/environment.py`'s existing fail-closed `ENVIRONMENT` resolver
convention used framework-wide.

Full detail: `templates/onprem-deploy/README.md`,
`templates/onprem-deploy/kubernetes/README.md`.

---

## Part E — Ops Portal

Cross-tenant cost/issues dashboard. Full detail:
[portal/README.md](./portal/README.md).

### E.1 — Setup

```bash
cd portal
cp .env.example .env.local
npm install
npm run db:migrate      # applies db/schema.sql against DATABASE_URL
npm run dev             # http://localhost:3000
```

Minimum required env vars: `DATABASE_URL` (same Postgres as the LLM
Gateway's budget backend — the portal reads `llm_gateway_budget` directly,
read-only), `OPS_PORTAL_USER`, `OPS_PORTAL_PASSWORD`. The portal **refuses
to serve traffic** without basic-auth credentials configured (or, with SSO
enabled, without `SSO_SESSION_SECRET`) — there is no unauthenticated mode.

**Multi-user RBAC (optional):** set `OPS_PORTAL_USERS` instead of/alongside
`OPS_PORTAL_USER`/`PASSWORD` for per-user roles and tenant scoping:

```bash
OPS_PORTAL_USERS='[
  {"username":"alice","password":"...","role":"admin","tenants":"*"},
  {"username":"bob-readonly","password":"...","role":"viewer","tenants":["acme"]}
]'
```

For SSO, set `OPS_PORTAL_SSO_USERS` the same way, keyed by email instead of
username/password:

```bash
OPS_PORTAL_SSO_USERS='[{"email":"alice@corp.com","role":"admin","tenants":"*"}]'
```

Roles: `viewer` (read-only, scoped tenants), `operator` (+ create tenants,
mint widget tokens), `admin` (+ revoke widget tokens, read the audit log,
implicitly all tenants if `"tenants": "*"`). An authenticated SSO identity
not listed in `OPS_PORTAL_SSO_USERS` gets `viewer` with **zero** tenant
access, not full access — there is no implicit-admin fallback for "any
authenticated user." See SPECS.md §26 "Role-Based Access Control".

### E.2 — Wire tenant history sync

In each tenant's CD workflow (or a local `ai-stack-check` run):

```bash
curl -X POST https://ops.example.com/api/sync/history \
  -H "Authorization: Bearer $OPS_PORTAL_SYNC_TOKEN" -H "Content-Type: application/json" \
  -d '{"tenantId":"acme","entries":[{"entryId":"...","level":"CRITICAL","event":"...","timestamp":"...","raw":{}}]}'
```

A tenant auto-registers on its first sync — no separate provisioning step.

### E.3 — Audit log (enterprise pack, §30)

```bash
# .env.local
AUDIT_LOG_WRITE_TOKEN=...
AUDIT_LOG_HMAC_KEY=...     # rotate carefully — old events stay signed with the old key
```

```bash
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" "http://localhost:3000/api/audit?tenantId=acme"
```

Every event is HMAC-signed and the table has DB-level `UPDATE`/`DELETE`
triggers — `GET /api/audit` recomputes each signature on read and flags
`verified: false` on any row altered outside the app (even by someone who
disabled the trigger). `GET /api/audit` requires the `admin` role. Wired
call sites: `ai-tenant-init` → `tenant_created`, `ai-tenant-promote` →
`hitl_promotion`, `ai-stack-off` under an enterprise policy →
`hook_bypass`. Set `OPS_PORTAL_URL` and `AUDIT_LOG_WRITE_TOKEN` in the
shell environment those commands run in.

**Local fallback:** if `OPS_PORTAL_URL`/`AUDIT_LOG_WRITE_TOKEN` aren't set,
or the write to the portal fails (down, network error, non-2xx), the event
is appended to `~/.agent-framework/local-audit-fallback.log` as a JSON line
instead of being dropped silently. This is a local, unsigned trace for
manual reconciliation — it is not a substitute for the portal's audit log
and has no tamper protection.

### E.4 — SSO/OIDC (replaces basic auth, §30)

```bash
SSO_ENABLED=true
SSO_ISSUER=https://corp.okta.com
SSO_CLIENT_ID=...
SSO_CLIENT_SECRET=...
SSO_REDIRECT_URI=https://ops.example.com/api/auth/callback
SSO_SESSION_SECRET=<random 32+ byte string>
```

This is exclusive with basic auth, not additive — once `SSO_ENABLED=true`,
`OPS_PORTAL_USER`/`PASSWORD` no longer grant access. Machine-to-machine
endpoints (`/api/sync/*`, `/api/widget/*`, `/api/audit/append`) are
unaffected either way.

`SSO_ALLOW_INSECURE_HTTP=true` is for testing against a local non-TLS IdP
only — never set it in a real deployment.

Each SSO identity's role and tenant access are resolved via
`OPS_PORTAL_SSO_USERS` (see Part E.1 above) — logging in via SSO grants
`viewer`/no-tenants by default, not admin access, until the identity is
added to that list.

`POST /api/auth/logout` revokes the session server-side (not just the
client cookie) by recording the session's `jti` claim in the
`revoked_sessions` table; every subsequent request's session check calls
`GET /api/auth/session-status` to confirm the `jti` isn't revoked before
trusting an otherwise-valid cookie. This check fails open on a DB/network
error — it won't lock out every SSO user over a transient outage, given the
session's 8h TTL already bounds the exposure of a missed revocation.

---

## Part F — In-App Widget

Embeddable, read-only status component for tenant end users. Full detail:
[templates/in-app-widget/README.md](./templates/in-app-widget/README.md).

### F.1 — Mint a token

```bash
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" -X POST https://ops.example.com/api/tenants/acme/widget-token
# => { "token": "...", "note": "Store this now — it will not be shown again." }
```

Minting (and revoking) widget tokens requires the `admin` role.

### F.1a — Revoke a leaked token

The portal never retains a token's plaintext after minting (only its hash),
so revocation is by tenant, not by the specific token string — it revokes
**every** still-active token for that tenant:

```bash
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" -X DELETE https://ops.example.com/api/tenants/acme/widget-token
# => { "ok": true, "revoked": 2 }
```

Mint a replacement and update the tenant's embed snippet afterward.

### F.2 — Embed

```html
<!-- Self-hosted: download widget.js from a tagged release and serve it yourself -->
<script src="/static/widget.js"></script>
<agent-status tenant-id="acme" token="<token>" portal-url="https://ops.example.com"></agent-status>
```

The token is the **only** access-control boundary — `tenant-id` is a
display label. A forged `tenant-id` cannot read another tenant's data.

Status prefers the `agent_runs` table (populated by `runtime/llm_gateway.py`'s
best-effort `POST /api/runs/ingest` on call start/end) when an open or recent
run exists for the tenant, so `running` is a real, reachable status — not
just `success` / `degraded` / `failed`. Falls back to the most recent synced
`.agent-history.log` entry when no `agent_runs` row exists (e.g. a tenant
whose gateway predates this, or `OPS_PORTAL_URL` unset).

Tenant detail pages additionally show a 24h trace count and error rate
pulled live from the tenant's own Phoenix instance via GraphQL
(`portal/lib/phoenix.ts`'s `getRecentTraceStats()`) when `phoenixBaseUrl` is
configured — degrades silently (omits the line) if that Phoenix is
unreachable or has no `default` project yet.

---

## Part G — Enterprise Pack

Optional governance layer (SPECS.md §30). Full detail:
[enterprise/README.md](./enterprise/README.md).

### G.1 — Generate an org signing key (once)

```bash
gpg --full-generate-key
gpg --armor --export it-sec@example.com > org-public-key.asc   # distribute to MDM
```

### G.2 — Package and sign the hook bundle

```bash
# On a machine with hooks already installed:
./enterprise/package-hook-bundle.sh 1.0.0 \
  --gpg-key it-sec@example.com \
  --org-policy ./our-org-policy.yaml \
  --out ./dist
```

Produces `agenticframework-hooks-1.0.0.tar.gz` + `.sig`,
`agenticframework-org.yaml`, `mdm-deploy-hooks.sh`.

### G.3 — MDM deploys to every managed machine

```bash
./mdm-deploy-hooks.sh 1.0.0 --org-pubkey ./org-public-key.asc
```

This verifies the GPG signature **before** extracting anything — a
tampered or unsigned bundle is refused, not installed. Sets
`git config --global init.templateDir`, installs
`~/.agent-framework/agenticframework-org.yaml`.

### G.4 — Bypass policy enforcement

Once the org policy is installed, `ai-stack-off` enforces
`hooks.bypass_policy`:

| Policy | Behaviour |
|---|---|
| (no policy file) | Unrestricted — default dev mode |
| `disabled` | Always refuses; prints `break_glass_approvers` |
| `break-glass` | Refuses unless `AI_BREAK_GLASS_TOKEN` is set **and validates** |

`AI_BREAK_GLASS_TOKEN` is not just checked for presence — it must be a
real token IT issues, in the form `<actor>:<expires_epoch>.<hex_hmac>`,
validated locally against `BREAK_GLASS_HMAC_KEY` (a separate secret IT
distributes to managed machines, e.g. via the MDM-deployed org policy —
never the same value as the per-use token). A present-but-invalid or
expired token is refused exactly like a missing one. If
`BREAK_GLASS_HMAC_KEY` isn't configured on the machine, break-glass bypass
cannot be validated and is refused outright, regardless of what token is
supplied.

Every attempt (granted or denied) is audit-logged as `hook_bypass` —
best-effort to the Ops Portal when configured, falling back to
`~/.agent-framework/local-audit-fallback.log` otherwise so a bypass attempt
is never silently unrecorded (see Part E.3).

### G.5 — Uninstall on a managed machine

```bash
ai-stack-uninstall
```

Restores `git init.templateDir` to its value **before** AgentSmith
was installed (not just unset), removes the shell-rc block surgically
(your own customizations before/after it are untouched), warns if an
enterprise `bypass_policy: disabled` policy is present, prompts before
removing `~/.agent-framework` / `~/.git_templates`.

---

## 9. Testing Checklist

Minimal real validation for each subsystem (no mocks):

```bash
# Framework scripts + shell
find scripts runtime examples -name "*.py" -print0 | xargs -0 -n1 python3 -m py_compile
bash -n install-ai-stack.sh && zsh -n install-ai-stack.sh

# Knowledge Graph rebuild + non-empty assertion (Pillar 2 / P10a — wired into self-test.yml)
python3 scripts/verify_system.py --check-kg

# Ops Portal (includes a cross-tenant isolation regression suite — see SPECS.md §26)
cd portal && npx tsc --noEmit && npm test && npm run build

# In-App Widget (includes an XSS-attribute-injection regression test)
cd templates/in-app-widget && npm install && npm test

# Redaction (needs ENVIRONMENT set; staging/production exercise real scrubbing)
ENVIRONMENT=staging python3 scripts/verify_system.py --check-redaction
ENVIRONMENT=production python3 scripts/verify_system.py --check-redaction

# Hook bundle signing (needs a real GPG key; see Part G.1)
gpg --verify agenticframework-hooks-<version>.tar.gz.sig agenticframework-hooks-<version>.tar.gz

# On-prem deployment template (D.6) — compose/proxy/Helm syntax, no live cluster needed
python3 scripts/verify_system.py --check-onprem-deploy

# Dedicated worker pool manifests — kubectl (even --dry-run=client) needs a
# reachable cluster for API discovery; a free local one takes ~30s:
brew install kind && kind create cluster --name af-test
runtime/k8s/dedicated-tenant/render.sh acme nginx:alpine --apply
kubectl get pods -n tenant-acme   # CreateContainerConfigError until you create the Secret — expected
kind delete cluster --name af-test
```

For LLM Gateway / Postgres checkpointer / Ops Portal database code, spin up
a throwaway Postgres rather than trusting the code path untested:

```bash
docker run -d --name pg-test -e POSTGRES_PASSWORD=test -e POSTGRES_USER=test -e POSTGRES_DB=test -p 55432:5432 postgres:16-alpine
export DATABASE_URL="postgresql://test:test@localhost:55432/test"
# ... run your test, then:
docker rm -f pg-test
```

For `run_with_recoverable_step` (D.4) specifically — the workflow-side
mechanics (parking alive, retry-policy override, signal resume) can't be
exercised by a throwaway Postgres alone; it needs a real Temporal test
server:

```bash
pip install temporalio
python3 -c "
import asyncio
from temporalio.testing import WorkflowEnvironment
asyncio.run(WorkflowEnvironment.start_local())  # downloads/starts the test server once
"
# Then run a worker + workflow against env.client inside that context —
# see the pattern in FIXES_AND_CLEANUP.md's HITL/DLQ redesign section for
# a worked example (CRM-style hallucinated-field-name failure -> parked
# workflow -> human_fix_payload signal -> resumed with the correction).
```

---

## 10. Day-2 Operations

| Task | Command |
|---|---|
| Upgrade vendored scripts in a tenant repo | `ai-stack-upgrade --to <version>` |
| Promote staging → production | `ai-tenant-promote <id> --from staging --to production` |
| Rotate a widget token | Mint a new one (`POST .../widget-token`) — old one keeps working until explicitly revoked |
| Rotate the audit-log HMAC key | New events sign with the new key; old events will report `verified: false` against it — re-sign history or accept the discontinuity, document which |
| Rotate the org GPG signing key | Re-run `package-hook-bundle.sh` with the new key; redistribute the new public key to MDM before the next deploy |
| Check unresolved MAJOR/CRITICAL | `ai-stack-check`, or `GET /api/audit` / `GET /api/tenants` on the Ops Portal |
| Remove the framework from a machine | `ai-stack-uninstall` |

---

## 11. Troubleshooting

See [UserManual.md §16](./UserManual.md#16-troubleshooting) for dev-mode
issues (Phoenix, Ollama, hooks, commit message format, circuit breaker).
Production/enterprise-specific:

**`ai-tenant-promote` fails with "eval gate failed"** — the staging eval
score is below 0.75; fix the regression on `develop` before retrying.

**Ops Portal won't start** — check `DATABASE_URL` is set and reachable, and
either `OPS_PORTAL_USER`+`PASSWORD` or the full `SSO_*` set is present; the
portal intentionally refuses to boot half-configured.

**Widget shows "invalid or revoked token"** — the token was never minted,
was revoked, or you're pointing `portal-url` at the wrong portal instance.

**`mdm-deploy-hooks.sh` refuses with "BAD signature"** — the bundle was
modified after signing, or you're verifying against the wrong public key.
Re-package from a clean checkout; never patch a signed tarball.

**LangGraph raises "MemorySaver is prohibited"** — you set
`ENVIRONMENT=production`/`staging` without `DATABASE_URL`, **or you simply
didn't set `ENVIRONMENT` at all** — unset/unrecognized values resolve to
`production` (fail-closed, see D.2/D.3), not `development`. Either set
`DATABASE_URL`, or set `ENVIRONMENT=development` explicitly for a
throwaway/dev run.

---

## 12. Spec Cross-Reference

| Area | SPECS.md section | Implementation |
|---|---|---|
| Tenancy model | §23, §24 | `ai-tenant-init`, `ai-tenant-promote` in `install-ai-stack.sh` |
| Production runtime | §25, §29 | `runtime/` |
| Trace redaction | §27 | `runtime/trace_redactor.py` |
| Observability / Ops Portal | §15, §26 | `portal/` |
| In-App Widget | §15, §26 | `templates/in-app-widget/` |
| Enterprise pack | §30 | `enterprise/`, `portal/lib/auditLog.ts`, `portal/lib/oidc.ts` |
| Framework hygiene | §22 Phase 5 | `hooks/`, `scripts/generate-ide-config.py`, `.github/workflows/` |
