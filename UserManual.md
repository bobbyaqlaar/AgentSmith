# AgentSmith — User Manual

**Version:** 1.0  
**For:** Developers and teams using AgentSmith day-to-day  
**See also:** [README.md](./README.md) for overview · [SPECS.md](./SPECS.md) for full specification

---

## Contents

1. [Installation](#1-installation)
2. [First-Time Setup](#2-first-time-setup)
3. [Applying to a Project](#3-applying-to-a-project)
4. [Daily Operations](#4-daily-operations)
5. [Execution Modes](#5-execution-modes)
6. [Writing Agent Specifications (RFCs)](#6-writing-agent-specifications-rfcs)
7. [Observability Dashboard](#7-observability-dashboard)
8. [Running Evaluations](#8-running-evaluations)
9. [Human-in-the-Loop (HITL) Self-Improvement](#9-human-in-the-loop-hitl-self-improvement)
10. [Multi-Repository & Monorepo](#10-multi-repository--monorepo)
11. [Team Setup](#11-team-setup)
12. [CI/CD via GitHub Actions](#12-cicd-via-github-actions)
13. [Agent Identity](#13-agent-identity)
14. [Cost & Budget Management](#14-cost--budget-management)
15. [Maintenance](#15-maintenance)
16. [Troubleshooting](#16-troubleshooting)
17. [Command Reference](#17-command-reference)

---

## 1. Installation

### Prerequisites

Install these before running the framework installer:

```bash
# Python 3.11+
python3 --version

# Git 2.x
git --version

# For local mode — Ollama (https://ollama.com)
ollama --version

# For team Phoenix — Docker
docker --version
```

### Install the Framework

```bash
curl -fsSL https://raw.githubusercontent.com/bobbyaqlaar/AgentSmith/main/install-ai-stack.sh | bash
```

The installer:
- Writes four git hook templates to `~/.git_templates/hooks/`
- Sets `git config --global init.templateDir`
- Installs all Python dependencies to your active Python environment
- Appends all `ai-*` shell functions to `~/.zshrc`
- Creates `~/.agent-framework/` for shared configuration and baseline fixtures

### Activate

```bash
source ~/.zshrc
```

Verify the install:

```bash
ai-stack-status
```

---

## 2. First-Time Setup

### Set Your Identity

Every agent run, trace, and log entry is tied to you as the owner. Set this once:

```bash
# Add to ~/.zshrc (the installer will prompt for these if not set)
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"
```

### Choose Execution Mode

**Local mode** — 100% offline, no API costs. Requires Ollama.

```bash
# Pull the three required models (one-time, ~15 GB total)
ollama pull llama3
ollama pull mistral
ollama pull gemma2

# Activate local mode
ai-mode-local
```

**Hybrid mode** — Frontier models for complex tasks, open-source for routine ones. Requires API keys.

```bash
# Add to ~/.zshrc
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Activate hybrid mode
ai-mode-hybrid
```

### Start the Dashboard

```bash
ai-dashboard-start
# Open http://localhost:6006
```

### Run the Health Check

```bash
ai-stack-check
```

A passing check confirms: Phoenix is running, your mode's dependencies are available, and no unresolved MAJOR/CRITICAL log entries exist in any active project.

---

## 3. Applying to a Project

### New Project

```bash
mkdir my-project && cd my-project
git init
git remote add origin https://github.com/org/my-project.git
```

The `post-checkout` hook fires on `git init` and automatically:
- Creates `.agent-rfc/` and `.agent-rfc/fixtures/`
- Writes `.cursorrules`, `CLAUDE.md`, `.agents/skills/`
- Detects your stack (TypeScript/React, Python/FastAPI, Go, or Generic)
- Writes the appropriate `.github/workflows/ci-*.yml`
- Seeds the Knowledge Graph by scanning your codebase
- Copies the baseline golden dataset from `~/.agent-framework/shared/` to `.agent-rfc/fixtures/golden_evals.json`
- Writes `.agenticframework/enabled` — this is what tells `pre-commit`,
  `commit-msg`, and `post-commit` that this repo has opted into
  AgentSmith. The framework's hooks are installed **globally**
  (`git config --global init.templateDir`), so they fire on every
  `git init`/`git clone` on your machine — those three hooks silently
  no-op in any repo that hasn't been through `post-checkout` at least once
  (or doesn't have `.agenticframework/tenant.yaml` from `ai-tenant-init`),
  so cloning an unrelated repo never trips your AgentSmith guardrails.

### Existing Project

```bash
cd /path/to/existing-project
git init   # safe on an existing repo — only writes missing files, never overwrites
```

### Public vs. Private Repositories

If your remote URL appears to be a public repository, the hook will prompt:

```
⚠️  This repo appears to be public. Add IDE config files to .gitignore?
    .cursorrules, CLAUDE.md, .agents/ contain system prompt content.
    Add to .gitignore? (y/n):
```

Answer `y` to keep your rules out of public view. In CI environments this defaults to `y` automatically.

### Verify the Project Setup

```bash
python3 scripts/verify_system.py
```

---

## 4. Daily Operations

### Starting a Session

```bash
ai-dashboard-start     # start Phoenix (skip if already running)
ai-stack-check         # confirm everything is healthy
```

### During Development

Work normally in your IDE. The framework operates silently in the background:

- **On every `git commit`**: pre-commit checks run, Knowledge Graph updates, semantic version tag applied
- **On every `git checkout`**: Knowledge Graph re-indexed, IDE rules refreshed if missing
- **In your IDE**: Cursor, Claude Code, and Antigravity all read your `.cursorrules` / `CLAUDE.md` / `.agents/skills/` automatically

### End of Session

```bash
ai-dashboard-stop      # optional — Phoenix can stay running between sessions
```

---

## 5. Execution Modes

### Local Offline Mode

```bash
ai-mode-local
```

- All LLM calls → Ollama at `http://localhost:11434/v1`
- Architect tasks → Mistral
- Developer tasks → Llama3
- Validator → pure Python logic
- Traces → Local Phoenix
- Cost → zero

### Hybrid Cloud Mode

```bash
ai-mode-hybrid
```

- Architect tasks → Claude 3.5 Sonnet (complex design)
- Developer tasks → routed by cost router: GPT-4o for complex code, Llama3-70b (Groq) for standard tasks, Gemma2 for formatting/docs
- Fallback → automatic if network drops (detected via socket ping to `1.1.1.1`)
- Traces → Local Phoenix (data never leaves your machine)

### Switching Mid-Session

```bash
ai-mode-local     # switch to offline — takes effect immediately
ai-mode-hybrid    # switch back to cloud — health check runs
```

### Disabling All Hooks

For corporate codebases or environments where hooks are not permitted:

```bash
ai-stack-off
# Unhooks git templates, mutes all pre-commit and post-commit logic
# Re-enable with: ai-mode-local or ai-mode-hybrid
```

---

## 6. Writing Agent Specifications (RFCs)

Before an agent can modify code in any file, a corresponding spec must exist in `.agent-rfc/`.

### Create a Spec

```bash
# Naming convention: NNN-short-description.md
touch .agent-rfc/001-user-authentication.md
```

Minimum required content:

```markdown
# RFC 001 — User Authentication

## Objective
Implement JWT-based authentication for the API.

## Files to Modify
- `src/auth/handler.ts`
- `src/middleware/auth.ts`

## Acceptance Criteria
- [ ] Tokens expire after 24 hours
- [ ] Refresh token flow implemented
- [ ] All endpoints protected by default
```

### Monorepo: Sub-Package Specs

Place service-level RFCs inside the relevant sub-package:

```
apps/api/.agent-rfc/001-auth.md       ← API-specific
apps/web/.agent-rfc/001-login-ui.md   ← Web-specific
.agent-rfc/001-shared-contracts.md    ← Cross-cutting
```

---

## 7. Observability Dashboard

### Starting the Dashboard

```bash
ai-dashboard-start
# Opens at http://localhost:6006
```

### Navigating the UI

**Traces tab** — Every agent execution appears here as a parent span with nested sub-spans. Filter by:
- `project.name` — see one project's activity
- `agent.owner_id` — see all your activity across projects
- `agent.name` — see a specific agent role (Architect, Developer, Validator)
- `ai_stack_mode` — compare local vs. hybrid behaviour

**Experiments tab** — Eval scorecard results from `ai-test-evals` runs. See correctness scores, tool accuracy, and latency trends over time, per project.

**Annotations tab** — HITL approvals and rejections. Annotating a span here triggers `sync-ui-feedback.py` to promote it into your golden dataset on the next `ai-test-evals` run.

### Annotating a Span for HITL

1. Open the **Traces** tab
2. Click on a trace that represents a production interaction you want to promote
3. In the right panel, click **Annotations**
4. Add label: `hitl_approved` = `true` (approve) or `label` = `good` / `bad`
5. On next `ai-test-evals`, this trace is automatically pulled into your golden dataset

### Stopping the Dashboard

```bash
ai-dashboard-stop
```

Data is persisted to SQLite (local) or PostgreSQL (team). No data is lost when the server stops.

---

## 8. Running Evaluations

### What Evals Do

`ai-test-evals` runs your golden dataset cases through the active agent pipeline, scores each output using the LLM judge (default: Claude 3.5 Sonnet), and reports a scorecard. In CI this gates merges; locally it gives you visibility into quality trends.

### Run Locally

```bash
ai-test-evals
```

This does three things in sequence:
1. Calls `sync-ui-feedback.py` — pulls any HITL annotations from Phoenix and promotes them to the golden dataset
2. Calls `run-evals.py` — runs all golden dataset cases and scores them
3. Reports results to stdout and to `http://localhost:6006/experiments`

### Understanding the Scorecard

| Metric | What it measures |
|---|---|
| Correctness Score | How accurately the agent's output matches the reference output |
| Tool Accuracy Rate | Whether the agent called the expected tool vs. a hallucinated path |
| Latency / Token Trends | Whether prompt changes have caused the agent to loop or inflate cost |

### Changing the Judge Model

No code change required — set the environment variable:

```bash
export AGENT_JUDGE_MODEL="claude-3-5-sonnet-20241022"   # default
export AGENT_JUDGE_MODEL="gpt-4o"
export AGENT_JUDGE_MODEL="llama3-70b-8192"              # local/Groq
```

### Greenfield Projects (No Golden Dataset Yet)

On a new project where `.agent-rfc/fixtures/golden_evals.json` doesn't exist or has fewer than 3 cases, the eval step skips gracefully with a warning. No build failure. The quality gate activates automatically once the golden dataset is populated.

---

## 9. Human-in-the-Loop (HITL) Self-Improvement

### The Loop

When an agent produces a failure in production — a bad code output, an incorrect tool call, a swallowed exception — the failure is captured in `.agent-history.log` as a MAJOR or CRITICAL entry. A human reviews it, approves the correct fix, and promotes it. The framework then:

1. Adds the case to `golden_evals.json` as a permanent regression test
2. Distills the failure pattern into a one-sentence guardrail rule (via LLM)
3. Appends the rule to `custom_judge_criteria.json` (capped at 10 rules, FIFO)
4. Re-runs evals to confirm the fix holds

### Promote via Terminal

```bash
ai-stack-promote <case-id> "<input query>" "<human-approved output>"

# Example:
ai-stack-promote case_003 \
  "Handle database connection drop" \
  "log.Error('DB dropped', err); retry.Backoff(ctx, 3)"
```

### Promote via Phoenix UI

1. Open `http://localhost:6006`
2. Find the failing span in the **Traces** tab
3. Add annotation: `hitl_approved = true`
4. Run `ai-test-evals` — the framework pulls the annotation and promotes it automatically

### Resolving MAJOR / CRITICAL Log Entries

MAJOR and CRITICAL entries in `.agent-history.log` are never automatically pruned. Once you have resolved the underlying issue and promoted a fix:

```bash
ai-stack-promote <case-id> "<query>" "<fix>"
# promote-learning.py writes hitl_resolved: true, hitl_resolved_by, hitl_resolved_at
```

`ai-stack-check` will stop reporting the entry as unresolved.

---

## 10. Multi-Repository & Monorepo

### Multi-Repository (Multiple Separate Git Roots)

The framework is installed once at the machine level. All repositories share:
- The same git hooks (`~/.git_templates/hooks/`)
- The same shell commands
- The same Phoenix dashboard instance
- The same baseline golden dataset (`~/.agent-framework/shared/golden_evals_base.json`)

Each repository has its own:
- `.agent-rfc/` specs and fixtures
- `.agent-history.log`
- Knowledge Graph (`knowledge_graph.json`)
- Budget cache (`token_velocity_cache.json`)

To apply the framework to any existing repository:

```bash
cd /path/to/repo && git init
```

### Monorepo (One Git Root, Multiple Packages)

The framework generates one Knowledge Graph for the entire monorepo. Sub-packages are addressed by path:

```python
# Agent queries knowledge graph for a specific sub-package
kg.fetch_subgraph_context_window("apps/api/auth_module.py")
```

For service-level RFC scoping, create a `.agent-rfc/` directory inside the sub-package:

```
my-monorepo/
├── .agent-rfc/               ← cross-cutting architecture RFCs
├── apps/
│   ├── api/
│   │   └── .agent-rfc/       ← API-specific RFCs
│   └── web/
│       └── .agent-rfc/       ← Web-specific RFCs
```

When an agent works on a file in `apps/api/`, it reads the API-level `.agent-rfc/` first, then falls back to the root `.agent-rfc/` for cross-cutting rules.

### Shared RFC Store Across Repositories (Optional)

For teams wanting RFC specs visible across multiple repos:

```bash
# In ~/.zshrc
export AGENT_SHARED_RFC_DIR="$HOME/team-shared-rfcs"
# or a network path
export AGENT_SHARED_RFC_DIR="/mnt/team-storage/agent-rfcs"
```

When set, agents and `run-evals.py` also read from this directory alongside the local `.agent-rfc/`.

---

## 11. Team Setup

### Option A — Each Developer Runs Local Phoenix

Every developer installs the framework independently and runs their own Phoenix instance. Traces are not shared.

```bash
# Each developer
curl -fsSL https://raw.githubusercontent.com/bobbyaqlaar/AgentSmith/main/install-ai-stack.sh | bash
ai-mode-hybrid
ai-dashboard-start
```

### Option B — Shared Team Phoenix (Recommended)

Run a single Phoenix + PostgreSQL instance on a team server. All developers point at it.

**On the server:**

```bash
# Clone the framework repo
git clone https://github.com/bobbyaqlaar/AgentSmith.git
cd AgentSmith

# Start the shared stack
docker compose up -d

# Confirm it's running
curl http://localhost:6006
```

**On each developer machine:**

```bash
# Add to ~/.zshrc
export AGENT_PHOENIX_ENDPOINT="http://<server-ip>:6006"

# Framework picks this up automatically — no other changes needed
source ~/.zshrc
```

**Filtering by developer in the shared UI:**

In Phoenix, filter traces by `agent.owner_id` to see one developer's activity, or by `project.name` to see one project's activity across the whole team.

### Syncing Framework Updates Across the Team

When you update the framework rules (e.g., new `.cursorrules` content or updated hooks):

```bash
# On your machine — pull latest framework
cd AgentSmith && git pull

# Re-run the installer to update hooks and templates
./install-ai-stack.sh
source ~/.zshrc

# Tell team members to do the same, then apply to their repos:
git init   # inside each project directory
```

---

## 12. CI/CD via GitHub Actions

### What Gets Created Automatically

When you first run `git init` (or `git checkout`) in a project, the `post-checkout` hook writes a CI workflow appropriate for your stack:

| Stack | File created |
|---|---|
| TypeScript/React | `.github/workflows/ci-ts-react.yml` |
| Python/FastAPI | `.github/workflows/ci-python-fastapi.yml` |
| Go | `.github/workflows/ci-go.yml` |

The workflow runs on every pull request and includes:
- Type checking / linting / tests
- Eval scorecard (skips gracefully if no golden dataset exists)

### Required GitHub Secrets

In your GitHub repository → **Settings → Secrets and variables → Actions**, add:

| Secret | Required | Notes |
|---|---|---|
| `OPENAI_API_KEY` | Yes (if using OpenAI judge) | Used by `run-evals.py` |
| `ANTHROPIC_API_KEY` | Yes (if using Claude judge) | Default judge is Claude |
| `AGENT_PHOENIX_ENDPOINT` | Optional | Team Phoenix URL for persisting CI scorecard results |
| `AI_STACK_SLACK_WEBHOOK` | Optional | CI failure alerts |

### Enforcing Branch Protection

In **Settings → Branches → Add rule** for `main`:

- ✅ Require status checks to pass: `validate`
- ✅ Require at least 1 approving review
- ✅ Dismiss stale reviews on new commits
- ✅ Require linear history

Or via the GitHub CLI:

```bash
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["validate"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field restrictions=null
```

### Setting the Eval Quality Threshold

The default pass threshold is 80%. Adjust in the workflow file:

```yaml
- name: "Guardrail: Run Eval Scorecards"
  run: python3 scripts/run-evals.py --fail-below 0.85   # 85% threshold
```

### Post-Deploy Promotion

Tenant repos get two CD workflows from `workflow-templates/` (via `post-checkout` or `ai-tenant-init`):

- **`cd-staging.yml`** — runs on push to `develop` (staging eval gate at 0.75)
- **`cd-production.yml`** — runs on push to `main` after a reviewed promotion PR

Production CD runs `sync-ui-feedback.py` after deploy, then opens a **PR** for any golden-dataset fixture updates (never pushes directly to `main`). See [OPERATIONS.md §C.3](./OPERATIONS.md#c3--promote-staging--production).

---

## 13. Agent Identity

### Setting Up Your Identity

```bash
# Add to ~/.zshrc
export AGENT_OWNER_ID="you@example.com"
export AGENT_OWNER_NAME="Your Name"
```

These are inherited by all agent scripts, log entries, and OTel spans automatically.

### What Gets Tagged

Every agent execution attaches:

| Attribute | Example |
|---|---|
| `agent.owner_id` | `you@example.com` |
| `agent.owner_name` | `Your Name` |
| `agent.name` | `Architect`, `Developer`, `Validator` |
| `agent.role` | `orchestrator`, `subagent`, `validator` |
| `agent.session_id` | UUID per workflow run |
| `agent.parent` | Parent agent name for sub-agents |
| `llm.model_name` | `claude-3-5-sonnet-20241022`, `llama3` |
| `project.name` | Derived from git remote |
| `ai_stack_mode` | `local`, `hybrid`, `local_fallback` |

### Filtering in Phoenix

To see all your activity across all projects:
```
agent.owner_id = "you@example.com"
```

To see the full trace of a specific workflow run:
```
agent.session_id = "<uuid>"
```

To see all sub-agent calls under a specific orchestrator:
```
agent.parent = "Architect"
```

### Identity in HITL Records

When you promote a fix, the HITL record captures who approved it:

```json
{
  "hitl_resolved": true,
  "hitl_resolved_by": "you@example.com",
  "hitl_resolved_at": "2026-06-22T11:05:00Z"
}
```

This creates a full audit trail: who ran the agent, what failed, who approved the fix, when.

---

## 14. Cost & Budget Management

### How Cost Routing Works

Every prompt is analysed before it reaches an LLM:

1. Token count via `tiktoken` — prompts over 8,000 tokens go to Claude regardless of complexity
2. Semantic keyword scan — architecture, migration, race condition → GPT-4o or Claude
3. Low complexity + formatting/docs → Gemma2 (cheapest)
4. Default → Llama3-70b (balanced)

### Budget Thresholds

Edit `.agent-rfc/fixtures/token_velocity_cache.json` to tune your limits:

```json
{
  "config": {
    "burst_window_minutes": 5,
    "burst_max_tokens": 50000,
    "monthly_budget_usd": 150.00,
    "cost_per_million_input_tokens_usd": 2.50,
    "cost_per_million_output_tokens_usd": 10.00
  }
}
```

### What Happens When a Threshold is Breached

**Burst breach** (>50k tokens in 5 minutes):
- Desktop notification fires immediately (macOS, Linux, Windows)
- Slack/Teams alert dispatched in background
- `sys.exit(1)` kills the agent loop instantly

**Monthly cap breach** (accumulated spend ≥ monthly limit):
- Same notification + alerts
- All cloud execution paths halted
- Monthly accumulator resets automatically on the 1st of the next month

### Monitoring Spend

Open Phoenix and use the Experiments view. Sort by `metrics.tokens.total` to see which agent runs are consuming the most budget.

For enterprise aggregators (Datadog/Grafana Loki), the JSON-Lines logs from `agent_logger.py` stream to stdout and can be ingested directly.

---

## 15. Maintenance

### Bi-Weekly: Log Rotation Check

INFO and MINOR log entries rotate automatically at 10,000 entries. MAJOR and CRITICAL entries are never removed until HITL resolved. No manual action required unless you want to inspect:

```bash
# Count unresolved entries
grep -c '"hitl_resolved": false' .agent-history.log
```

### Monthly: Knowledge Graph Pruning

When files are deleted or renamed, orphan nodes can accumulate in the graph:

```bash
python3 -c "
from scripts.local_knowledge_graph import AgentKnowledgeGraph
kg = AgentKnowledgeGraph()
isolated = [n for n, attr in kg.graph.nodes(data=True)
            if attr.get('type') == 'CodebaseFile' and kg.graph.degree(n) == 0]
kg.graph.remove_nodes_from(isolated)
kg.save_graph_to_disk()
print(f'Pruned {len(isolated)} orphan nodes.')
"
```

### As Needed: Upgrade Local GPU Models

```bash
ollama pull llama3
ollama pull mistral
ollama pull gemma2
```

### As Needed: Scrub a Project

Removes `.cursorrules`, `CLAUDE.md`, `.agents/` from a project directory
(searched up to 3 levels deep). Useful before handing off a repo or
cleaning up. `.agent-history.log` is **not** touched — it's left in place.

```bash
ai-stack-scrub /path/to/project
# Lists every exact path it found and will delete, THEN prompts for
# confirmation — not just the top-level directory name. This matters
# because -maxdepth 3 can reach into sibling projects underneath whatever
# directory you point it at (e.g. running it from $HOME).
```

### As Needed: Upgrade the Framework

```bash
curl -fsSL https://raw.githubusercontent.com/bobbyaqlaar/AgentSmith/main/install-ai-stack.sh | bash
source ~/.zshrc

# Re-apply to existing projects
cd /path/to/project && git init
```

---

## 16. Troubleshooting

### Phoenix Won't Start

```bash
# Check if port 6006 is already in use
lsof -i :6006

# Kill existing process and restart
ai-dashboard-stop
ai-dashboard-start
```

### Ollama Models Not Found

```bash
# Check which models are loaded
curl -s http://localhost:11434/api/tags | python3 -m json.tool

# Pull missing models
ollama pull llama3
```

### Hooks Not Firing on an Existing Repo

```bash
# The template dir must be set before init; verify:
git config --global init.templateDir

# If empty, re-run:
ai-mode-local   # or ai-mode-hybrid

# Re-apply to the repo:
cd /path/to/repo && git init
```

### Commit Blocked by Pre-Commit Hook

The hook blocks commits that contain:
- Unresolved AI markers: `ponytail:`, `TODO: agent`, `@agent-ignore`
- Empty catch blocks in TypeScript/JavaScript
- Double blank identifiers in Go (`_, _ :=`)

Fix the flagged code, then commit again. To bypass in an emergency:

```bash
DISABLE_AI_STACK=true git commit -m "emergency: ..."
```

### Commit Message Rejected

Messages must follow Conventional Commits format:

```
feat(auth): add JWT refresh token support
fix(api): handle null user response
docs: update installation guide
```

### Circuit Breaker Tripped

```bash
# Check what triggered it
tail -n 20 .agent-history.log | python3 -m json.tool

# Reset the burst window (clears the 5-minute token cache only)
echo '{"config": {}, "monthly_accumulated_spend_usd": 0, "current_month_identifier": "", "events": []}' \
  > .agent-rfc/fixtures/token_velocity_cache.json
```

---

## 17. Command Reference

### Mode & Environment

| Command | Description |
|---|---|
| `ai-mode-local` | Activate 100% local offline mode (Ollama). Runs health check. |
| `ai-mode-hybrid` | Activate hybrid cloud mode. Runs health check. |
| `ai-stack-off` | Disable all hooks and templates. |
| `ai-stack-check` | Full health check: Phoenix, Ollama or API keys, unresolved log entries. |
| `ai-stack-status` | Print: mode, muted flag, network connectivity. |

### Dashboard

| Command | Description |
|---|---|
| `ai-dashboard-start` | Start Arize Phoenix on `$AGENT_PHOENIX_PORT` (default 6006). |
| `ai-dashboard-stop` | Stop Phoenix. |

### Evaluation & Self-Improvement

| Command | Arguments | Description |
|---|---|---|
| `ai-test-evals` | — | Sync HITL feedback from Phoenix, then run eval scorecard. |
| `ai-stack-promote` | `<id> <query> <output>` | Promote a production fix to the golden dataset and re-run evals. |

### Maintenance

| Command | Arguments | Description |
|---|---|---|
| `ai-stack-scrub` | `[directory]` | Interactive removal of runtime artefacts from a project directory — lists every exact path it will delete before prompting for confirmation. |
| `ai-stack-upgrade` | `[--to VERSION]` | Copies vendored scripts from `~/.agent-framework/scripts` into the current tenant repo, bumps `.agenticframework/tenant.yaml`'s `framework.version`, commits the change. Fails loudly (and stops) if the commit itself fails, rather than reporting "Upgrade complete" regardless. |
| `ai-stack-uninstall` | — | Enterprise-safe machine-level removal: restores `git init.templateDir` to its pre-install value, removes the managed block from your shell rc, optionally removes `~/.agent-framework` and `~/.git_templates`. Prompts for confirmation at each destructive step. |

### Multi-Tenancy (see OPERATIONS.md for the full walkthrough)

| Command | Arguments | Description |
|---|---|---|
| `ai-tenant-init` | `<id> [--stack STACK] [--isolation shared\|dedicated]` | Scaffolds `.agenticframework/tenant.yaml` and per-environment CI/CD workflows in the current repo. |
| `ai-tenant-promote` | `<id> --from staging --to production` | Verifies the staging eval gate, then opens a `develop → main` promotion PR. No direct push to `main`. Refuses if `<id>` doesn't exactly match the current repo's `.agenticframework/tenant.yaml` — a same-prefix tenant id (e.g. `acme` vs. `acme-sandbox`) is not a match. |

### Runtime Flags (Environment Variables)

| Variable | Effect |
|---|---|
| `DISABLE_AI_STACK=true` | All hooks exit immediately without running |
| `SEMVER_LOOP_GUARD=true` | Prevents infinite loop in post-commit semver tagging |
| `AI_BREAK_GLASS_TOKEN=<token>` | Required by `ai-stack-off` when the installed org policy sets `bypass_policy: break-glass` (enterprise pack, see OPERATIONS.md). Must be a real IT-issued, HMAC-signed token with an expiry — not just any non-empty string — validated against `BREAK_GLASS_HMAC_KEY` on the machine. |
| `OPS_PORTAL_URL` / `AUDIT_LOG_WRITE_TOKEN` | When both are set, `ai-tenant-init` and `ai-tenant-promote` best-effort write signed events to the Ops Portal's audit log. If unset, or the write fails, the event is appended to `~/.agent-framework/local-audit-fallback.log` instead of being dropped. |

---

This manual covers solo/team dev-mode usage. For multi-tenancy, the production
runtime, the Ops Portal, and the enterprise pack (SSO, audit log, signed hook
bundles, dedicated worker pools), see **[OPERATIONS.md](./OPERATIONS.md)**.

*For the full technical specification including data schemas, component inventory, and design decisions, see [SPECS.md](./SPECS.md).*
