# AgentSmith — User Manual

**For:** Developers using AgentSmith day-to-day (solo / dev mode)

> **Scope:** this document owns day-to-day dev-mode usage and the
> **canonical command reference (§17)**. Framework introduction:
> [README.md](./README.md) · formal specification: [SPECS.md](./SPECS.md) ·
> operator lifecycle (teams, production, CI/CD, portal, enterprise):
> [OPERATIONS.md](./OPERATIONS.md) · versions: [CHANGELOG.md](./CHANGELOG.md)

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
# uv — builds the framework's Python environment, fetching the pinned
# interpreter itself (without it: Python 3.11+ with venv)
uv --version            # brew install uv

# Git 2.x
git --version

# For local mode — Ollama (https://ollama.com)
ollama --version

# For team Phoenix — Docker
docker --version
```

### Install the Framework

```bash
# While this repository is private (until it is product-ready) the release URL
# below returns 404 — even to people with access, because curl sends no GitHub
# login — and `curl | bash` on a 404 exits 0 having installed nothing. Install
# from a checkout instead, which needs no release download:
#   gh repo clone bobbyaqlaar/AgentSmith && ./AgentSmith/install-ai-stack.sh
curl -fsSL https://github.com/bobbyaqlaar/AgentSmith/releases/latest/download/install-ai-stack.sh | bash
```

The installer:
- Writes four git hook templates to `~/.git_templates/hooks/`
- Sets `git config --global init.templateDir`
- Builds the framework's own Python environment, `~/.agent-framework/.venv`, from `requirements.lock` (pinned and hashed — the same file CI installs) at the Python version in `.python-version`. Nothing is installed into your system Python; the git hooks run the framework's scripts with this environment
- Installs the `agentsmith` command into that environment and links it at `~/.local/bin/agentsmith`
- Writes nothing to your shell profile — and removes the `ai-*` shell functions older installs appended to `~/.zshrc`, `~/.bashrc` or `~/.profile`, keeping a `*.agentsmith-bak` copy
- Creates `~/.agent-framework/` for shared configuration, baseline fixtures and machine state (`state/`)

### Activate

Nothing to reload. `agentsmith` works in any new or existing terminal as long as
`~/.local/bin` is on your `PATH`; the installer prints the one line to add if it
is not. The old names are available as wrappers if you want them —
`source ~/.agent-framework/shell/ai-compat.sh` — but nothing needs them.

Verify the install:

```bash
agentsmith status
```

---

## 2. First-Time Setup

### Set Your Identity

Every agent run, trace, and log entry is tied to you as the owner. You do not
have to configure this.

Resolution order, most specific first:

```
.agenticframework/tenant.yaml  ->  tenant.owner      the tenant's declaration
  AGENT_OWNER_ID                                     a deliberate override
    git config user.email                            outside any tenant
```

Inside a tenant the declaration wins; anywhere else git already knows.

**Do not export it in `~/.zshrc`.** The installer used to, and "set once,
applies to every project on this machine" is exactly the problem: an ambient
export outranked every tenant's declared `tenant.owner`, on every repo, while
CI -- which has no shell profile -- got nothing at all. A declaration now wins
over the environment, and an ignored export is reported at worker startup
rather than silently dropped.

`AGENT_OWNER_ID` still works as a deliberate per-deployment override -- a
container, a CI job -- where no file declares the key.

### Choose Execution Mode

**Local mode** — 100% offline, no API costs. Requires Ollama.

```bash
# Ask the model registry what this install actually routes to, and pull it.
# Do NOT hardcode a model list — it comes from runtime/models.yaml, and inside
# a tenant repo it picks up that tenant's overrides too.
ollama pull $(agentsmith models --ollama)     # one-time

# Activate local mode
agentsmith mode local
```

`agentsmith check` verifies each required model is present and prints the exact
`ollama pull` command for any that is missing. At the framework defaults the
list is `qwen2.5 llama3.2:3b falcon3:3b smollm2` (~5 GB), but treat
`agentsmith models --ollama` as the answer rather than that snapshot.

**Hybrid mode** — Frontier models for complex tasks, open-source for routine ones. Requires API keys.

```bash
# Add to ~/.zshrc — keys are secrets, so they stay in your environment (or a
# tenant's .env), never in AgentSmith's state files
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Activate hybrid mode
agentsmith mode hybrid
```

A mode is recorded in `~/.agent-framework/state/mode`, so every process on the
machine sees it — a new terminal, your IDE, a git GUI, the hooks. An
`AI_STACK_MODE` exported in a shell still wins for processes started from that
shell; `agentsmith mode` warns when it finds one.

### Start the Dashboard

```bash
agentsmith dashboard start
# Open http://localhost:6006
```

### Run the Health Check

```bash
agentsmith check
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

The `post-checkout` hook fires on `git checkout` and `git clone` — **not** on
`git init`, because git does not run this hook for init. A brand-new project is
provisioned by opting in once and checking out:

```bash
git init && git add -A && git commit -m "init"
mkdir -p .agenticframework && touch .agenticframework/enabled
git checkout            # hook fires here
```

The hook prints these instructions itself when it declines to provision. Once
opted in, it automatically:
- Creates `.agent-rfc/` and `.agent-rfc/fixtures/`
- Writes `.cursorrules`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.agents/skills/`, and seeds `.agent-history.log`
- Detects your stack (TypeScript/React, Python/FastAPI, Go, or Generic)
- Writes the appropriate `.github/workflows/ci-*.yml`
- Seeds the Knowledge Graph by scanning your codebase
- Copies the baseline golden dataset from `~/.agent-framework/shared/` to `.agent-rfc/fixtures/golden_evals.json`
- Writes `.agenticframework/enabled` — this is what tells `pre-commit`,
  `commit-msg`, and `post-commit` that this repo has opted into
  AgentSmith. The framework's hooks are installed **globally**
  (`git config --global init.templateDir`), so they land in every
  `git init`/`git clone` on your machine — but `post-checkout` itself
  skips any pre-existing repo (one that already has commit history) that
  hasn't opted in, and the other three hooks no-op without the marker.
  Cloning an unrelated repo therefore neither trips your AgentSmith
  guardrails nor gets AgentSmith files written into it.

### Existing Project

Pre-existing and freshly cloned repos are **not** provisioned automatically —
opt in explicitly, then re-fire the hook:

```bash
cd /path/to/existing-project
mkdir -p .agenticframework && touch .agenticframework/enabled
git checkout     # post-checkout now provisions — only writes missing files, never overwrites
```

Plain `git checkout`, with no path. `git checkout .` also fires the hook, but it
first reverts every uncommitted change in the working tree — in an existing
project, that is your work.

### Public vs. Private Repositories

If the repository is public (checked via `gh repo view` when the `gh` CLI is
available; otherwise any `github.com` remote is conservatively treated as
potentially public), the hook will prompt:

```
⚠️  This repo appears to be public. Add IDE config files to .gitignore?
    .cursorrules, CLAUDE.md, AGENTS.md, GEMINI.md,
    .github/copilot-instructions.md and .agents/ contain system prompt content.
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
agentsmith dashboard start     # start Phoenix (skip if already running)
agentsmith check         # confirm everything is healthy
```

### During Development

Work normally in your IDE. The framework operates silently in the background:

- **On every `git commit`**: pre-commit checks run, Knowledge Graph updates, semantic version tag applied
- **On every `git checkout`**: Knowledge Graph re-indexed, IDE rules refreshed if missing
- **In your IDE**: Cursor, Claude Code, Codex, Gemini CLI, Copilot and Antigravity read your `.cursorrules` / `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` / `.github/copilot-instructions.md` / `.agents/skills/` automatically

### End of Session

```bash
agentsmith dashboard stop      # optional — Phoenix can stay running between sessions
```

---

## 5. Execution Modes

### Local Offline Mode

```bash
agentsmith mode local
```

- All LLM calls → Ollama at `http://localhost:11434/v1`
- Routing is by **role**, not by hardcoded model name: `architect` →
  `developer` → `validator` → `fast`, resolved from `models.yaml` (see
  `agentsmith models --ollama` for the ids your install uses)
- Traces → Local Phoenix
- Cost → zero

### Hybrid Cloud Mode

```bash
agentsmith mode hybrid
```

- Same four roles, but pointed at cloud providers instead of Ollama. **The
  shipped `runtime/models.yaml` is local-only** — its Groq and Vertex AI
  entries are commented out with their verification notes, so hybrid mode does
  nothing until you uncomment one or declare cloud routes in a tenant
  `models.yaml`.
- Fallback → automatic if network drops (detected via socket ping to `1.1.1.1`)
- Traces → Local Phoenix (data never leaves your machine)

### Switching Mid-Session

```bash
agentsmith mode local     # switch to offline — takes effect immediately
agentsmith mode hybrid    # switch back to cloud — health check runs
```

### Disabling All Hooks

For corporate codebases or environments where hooks are not permitted:

```bash
agentsmith mode off
# Unhooks git templates, mutes all pre-commit and post-commit logic
# Re-enable with: agentsmith mode local or agentsmith mode hybrid
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
agentsmith dashboard start
# Opens at http://localhost:6006
```

### Navigating the UI

**Traces tab** — Every agent execution appears here as a parent span with nested sub-spans. Filter by:
- `project.name` — see one project's activity
- `agent.owner_id` — see all your activity across projects
- `agent.name` — see a specific agent role (Architect, Developer, Validator)
- `ai_stack_mode` — compare local vs. hybrid behaviour

**Experiments tab** — Eval scorecard results from `agentsmith evals` runs. See correctness scores, tool accuracy, and latency trends over time, per project.

**Annotations tab** — HITL approvals and rejections. Annotating a span here triggers `sync-ui-feedback.py` to promote it into your golden dataset on the next `agentsmith evals` run.

### Annotating a Span for HITL

1. Open the **Traces** tab
2. Click on a trace that represents a production interaction you want to promote
3. In the right panel, click **Annotations**
4. Add label: `hitl_approved` = `true` (approve) or `label` = `good` / `bad`
5. On next `agentsmith evals`, this trace is automatically pulled into your golden dataset

### Stopping the Dashboard

```bash
agentsmith dashboard stop
```

Data is persisted to SQLite (local) or PostgreSQL (team). No data is lost when the server stops.

---

## 8. Running Evaluations

### What Evals Do

`agentsmith evals` runs your golden dataset cases through the active agent pipeline, scores each output using the LLM judge (the `judge` role in `models.yaml` — see "Changing the Judge Model" below), and reports a scorecard. In CI this gates merges; locally it gives you visibility into quality trends.

### Run Locally

```bash
agentsmith evals
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

The judge comes from the `judge` role in `models.yaml` — framework default
`falcon3:3b` on local Ollama, deliberately a different model from `architect`
so the grader is never the author of what it grades. To change it for good,
edit that role, or declare your own in a tenant `models.yaml`:

```yaml
models:
  judge:
    id: gemini-3-flash-preview
    provider: google_ai          # or anthropic | xai | groq | openai | ollama
    api_key_env: GEMINI_API_KEY
    fail_below: {golden: 0.80, fairness: 0.80}   # calibrate per judge
```

**The registry wins over `AGENT_JUDGE_MODEL`.** The environment variable
applies only where no `judge` role is declared at all — a scripts-only install
with no `models.yaml`. If it is set and a role exists, it is ignored and a
warning names both values.

This precedence is deliberate and was inverted after a real failure: a shell
profile carrying `export AGENT_JUDGE_MODEL="claude-3-5-sonnet-20241022"` graded
every local eval with that model, while CI — where the variable is unset — used
the declared role. Two graders against one threshold, with nothing reporting
the difference, and scores are not comparable across judges. A config file that
a shell profile can override is not a source of truth.

To try a different judge for one run, edit the role, run, and revert — or use a
scratch repo. There is deliberately no ambient override.

### Additional Suites (Reliability Pack)

Beyond the golden suite, the same entry point runs more suites (full operator
detail, thresholds, and CI wiring: OPERATIONS.md §3):

```bash
python3 scripts/run-evals.py --suite fairness        # paired cases + pair parity; FAIRNESS_FAIL_BELOW (quality, 0.80) + FAIRNESS_PARITY_FAIL_BELOW (worst pair, 1.0)
python3 scripts/run-evals.py --suite hallucination   # two gates: false-positive rate (HALLUCINATION_FAIL_ABOVE, 0.05) + detection miss on planted cases (any miss fails)
python3 scripts/run-evals.py --suite adversarial     # prompt-injection / jailbreak; ADVERSARIAL_FAIL_ABOVE (default 0.10)
python3 scripts/run-evals.py --suite rag_poison      # poisoned retrieved context; RAG_POISON_FAIL_ABOVE (default 0.10)
python3 scripts/verify_ttft.py                       # live Ollama time-to-first-token budget; TTFT_FAIL_ABOVE_MS (default 2000)
```

### Security harness (P12)

Multi-framework `SEC-*` checks (OWASP LLM · NIST AI RMF · MITRE ATLAS ·
ISO/IEC 42001). Canonical map: [`docs/security-framework-map.md`](./docs/security-framework-map.md).
Operator detail: OPERATIONS.md §2 “Multi-framework security harness”.

```bash
python3 scripts/verify_system.py --check-security
MODERATION_HOOK=optional python3 scripts/run-security-checks.py --mode ci --strict
python3 scripts/run-security-checks.py --mode smoke --evidence-pack ./security-evidence
```

Runtime knobs (gateway): `PROMPT_GUARD`, `INPUT_GUARDRAIL`, `MODERATION_HOOK`.
Tenant files under `.agent-rfc/security/` (risk register, tool allowlist, …).

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
agentsmith promote <case-id> "<input query>" "<human-approved output>"

# Example:
agentsmith promote case_003 \
  "Handle database connection drop" \
  "log.Error('DB dropped', err); retry.Backoff(ctx, 3)"
```

### Promote via Phoenix UI

1. Open `http://localhost:6006`
2. Find the failing span in the **Traces** tab
3. Add annotation: `hitl_approved = true`
4. Run `agentsmith evals` — the framework pulls the annotation and promotes it automatically

### Resolving MAJOR / CRITICAL Log Entries

MAJOR and CRITICAL entries in `.agent-history.log` are never automatically pruned. Once you have resolved the underlying issue and promoted a fix:

```bash
agentsmith promote <case-id> "<query>" "<fix>"
# promote-learning.py writes hitl_resolved: true, hitl_resolved_by, hitl_resolved_at
```

`agentsmith check` will stop reporting the entry as unresolved.

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

### Shared RFC Store Across Repositories — NOT IMPLEMENTED

This section used to tell you to `export AGENT_SHARED_RFC_DIR` and said that
"agents and `run-evals.py` also read from this directory". They do not. Nothing
in the framework reads that variable, and there is no shared-RFC store.

The instructions are removed rather than corrected because there is nothing to
correct them to. Setting the variable did exactly nothing and reported exactly
nothing, which is the worst way for a documented feature to be absent — you
would conclude your RFCs were being shared and never see a signal otherwise.

If you need RFC specs visible across repositories today, a symlink into each
repo's `.agent-rfc/` works and is honest about what it is. The feature is
tracked in FIXES_AND_CLEANUP.md.

---

## 11. Team Setup

Team-shared infrastructure (Phoenix with auth, shared Ops Portal, shared
Postgres) is operator territory, not day-to-day dev usage — the canonical
procedure lives in **[OPERATIONS.md §0](./OPERATIONS.md#0--install--start)**
("Team-shared Phoenix with auth" and "standing infra"). Short version:

- One team server runs `docker compose -f docker-compose.yml -f docker-compose.auth.yml up -d`.
- Every developer sets `AGENT_PHOENIX_ENDPOINT="http://ops:<password>@<server-ip>:6007"`
  (port 6007 = the auth sidecar; 6006 stays loopback-only).
- An unauthenticated shared Phoenix is non-compliant (SPECS.md §15).


## 12. CI/CD via GitHub Actions

The full pipeline — what each workflow gates, GitHub Environments,
deploy/rollback wiring, GCP via WIF — is operator territory:
**[OPERATIONS.md §4](./OPERATIONS.md#4--deploy-via-github-cicd)**.
What a developer needs day-to-day:

- **PR** → `ci-<stack>.yml`: lint, tests, eval scorecard (warn-only in dev),
  plus the Ten-Pillars gates (Knowledge Graph, RFC, IDE-config drift).
- **Merge to `develop`** → `cd-staging.yml`: eval gate at 0.75 + smoke test.
- **Merge to `main`** → `cd-production.yml`: eval gate at 0.80 + smoke test +
  rollback hook. Production CD opens a PR for any golden-dataset fixture
  updates — it never pushes directly to `main`.
- Required repo secrets: `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
  (`AGENT_PHOENIX_ENDPOINT` optional). Greenfield repos with <3 golden cases
  skip the eval gate gracefully.


## 13. Agent Identity

### Setting Up Your Identity

Nothing to set up. Identity resolves from the tenant's declaration, then a
deliberate override, then git:

```
.agenticframework/tenant.yaml  ->  tenant.owner
  AGENT_OWNER_ID
    git config user.email
```

Do not export it in `~/.zshrc` -- ambient there, it outranks every tenant on
the machine and is absent in CI. See "Identity" earlier in this manual.

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

1. Token count via `tiktoken` — prompts over 8,000 tokens go to the `architect` role regardless of complexity
2. Semantic keyword scan — architecture, migration, race condition → `architect` / `developer`
3. Low complexity + formatting/docs → `fast` (cheapest)
4. Default → `validator` (balanced)

Each step names a **role**, not a model. The id behind it comes from
`models.yaml` (override a single tier with `AGENT_MODEL_ARCHITECT`,
`AGENT_MODEL_COMPLEX`, `AGENT_MODEL_STANDARD`, `AGENT_MODEL_FAST`).

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
ollama pull $(agentsmith models --ollama)   # re-pulls whatever models.yaml routes to
```

### As Needed: Scrub a Project

Removes `.cursorrules`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md` and `.agents/` from a project directory
(searched up to 3 levels deep). Useful before handing off a repo or
cleaning up. `.agent-history.log` is **not** touched — it's left in place.

```bash
agentsmith scrub /path/to/project
# Lists every exact path it found and will delete, THEN prompts for
# confirmation — not just the top-level directory name. This matters
# because -maxdepth 3 can reach into sibling projects underneath whatever
# directory you point it at (e.g. running it from $HOME).
```

### As Needed: Upgrade the Framework

```bash
# While the repo is private: `./install-ai-stack.sh` from an updated checkout
# instead (see Install the Framework).
curl -fsSL https://github.com/bobbyaqlaar/AgentSmith/releases/latest/download/install-ai-stack.sh | bash

# Re-apply to an opted-in project: plain `git checkout` re-fires the hook, which
# writes only what is missing. `git init` does not run post-checkout.
# To pull newer vendored scripts/ and runtime/ into it (needs
# .agenticframework/tenant.yaml, which `agentsmith tenant init` writes):
cd /path/to/project && agentsmith upgrade
```

---

## 16. Troubleshooting

### Phoenix Won't Start

```bash
# Check if port 6006 is already in use
lsof -i :6006

# Kill existing process and restart
agentsmith dashboard stop
agentsmith dashboard start
```

### Ollama Models Not Found

```bash
# Check which models are loaded
curl -s http://localhost:11434/api/tags | python3 -m json.tool

# Pull missing models — agentsmith check names the exact ones
ollama pull $(agentsmith models --ollama)
```

### Hooks Not Firing on an Existing Repo

```bash
# The template dir must be set before init; verify:
git config --global init.templateDir

# If empty, re-run:
agentsmith mode local   # or agentsmith mode hybrid

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

On a machine with an enterprise org policy the hook asks the policy first: under
`bypass_policy: disabled` the bypass is refused and the hook runs anyway, and
under `break-glass` it needs a valid `AI_BREAK_GLASS_TOKEN` (enterprise/README.md).

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

The canonical `agentsmith` command table — other documents link here instead of
carrying their own copies. Every command is a subcommand of one program
(`runtime/cli.py`), so `agentsmith <command> --help` is always current. They
were shell functions in `~/.zshrc` until 2026-09-14; the old names map to these
one for one (`~/.agent-framework/shell/ai-compat.sh`).

### Mode & Environment

| Command | Description |
|---|---|
| `agentsmith mode` | Print the mode in effect and where it came from (the environment or the machine's state file). |
| `agentsmith mode local` | Record 100% local offline mode (Ollama) for every process on this machine, relink the hook templates (developer install only), and run the health check. |
| `agentsmith mode hybrid` | Record hybrid cloud mode for every process on this machine, relink the hook templates (developer install only), and run the health check. |
| `agentsmith mode off` | Mute the hooks machine-wide and unlink the hook templates (developer install only). Under an enterprise org policy it is refused (`disabled`) or needs a valid break-glass token, and the attempt is audit-logged. |
| `agentsmith check` | Full health check: Phoenix, Ollama and the models the registry routes to (or API keys in hybrid), unresolved log entries. Exit 1 when anything fails. |
| `agentsmith status` | Print: mode, hooks on/muted, install mode, Phoenix endpoint, judge, owner, network connectivity. |
| `agentsmith models --judge` | Print the judge model actually in effect, resolved from the merged registry — not the `AGENT_JUDGE_MODEL` variable, which the registry overrides. cwd-aware, so inside a tenant repo it reports that tenant's judge. |
| `agentsmith models --ollama` | Print the Ollama model ids the merged registry actually routes to, space-separated — `ollama pull $(agentsmith models --ollama)`. Reads `models.yaml` from the current directory, so inside a tenant repo it reflects that tenant's overrides. Use this rather than a hardcoded list; `agentsmith check` uses the same lookup. |

### Dashboard

| Command | Description |
|---|---|
| `agentsmith dashboard start` | Start the standing Docker stack (Phoenix + Postgres + Ops Portal) when it is vendored, else a standalone Phoenix on `$AGENT_PHOENIX_PORT` (default 6006) via `uvx`, logging to `~/.agent-framework/logs/phoenix.log`. Records the endpoint so scripts started anywhere on the machine export traces to it. |
| `agentsmith dashboard stop` | Stop whichever of the two is running and clear the recorded endpoint. Docker volumes are kept. |

### Design & approvals (the process gates)

| Command | Arguments | Description |
|---|---|---|
| `agentsmith design new` | `<slug> --scope <glob>` (repeatable) | Write `.agent-rfc/designs/<slug>.md` with the shape the gate checks: front matter, Problem, Approach, **Pillars** (one line per rule, each with its question), **Deviations**, **Dependencies**, Levers. Never overwrites an existing design. Works in any IDE, and in none. |
| `agentsmith approve` | `<design> <deviation> [--statement …]` | Record the owner's approval of one deviation, appending to `.agenticframework/approvals.jsonl`. **Asks at the terminal** (`/dev/tty`): an agent's shell has no controlling terminal, so an agent cannot record it — it has to ask you, and you type the deviation id to confirm. The gate refuses any deviation without a resolving approval, so code in that design's scope stays blocked until you run this. |
| `python3 scripts/process_gate.py pillars` | — | The pillars a script can check, over everything this repo tracks: a `@dataclass` where a Pydantic model belongs (`P7-pydantic`), a route or CLI command that opens no span (`P3-tracing`). The commit gate checks only the files a change touches; this is the whole list — what to fix, or what to seed `pillars.allow` from when a repo first declares the policy. Silent unless the repo declares one. |
| `python3 scripts/process_gate.py artifacts` | — | One document per type, and the strays: a second backlog, a third review file, a Markdown file that is neither an artifact nor declared reference documentation. Silent unless the repo declares an `artifacts` mode. |

### Evaluation & Self-Improvement

| Command | Arguments | Description |
|---|---|---|
| `agentsmith evals` | — | Sync HITL feedback from Phoenix, then run eval scorecard. |
| `agentsmith promote` | `<id> <query> <output>` | Promote a production fix to the golden dataset and re-run evals. |
| `python3 scripts/run-evals.py --suite adversarial` | — | Prompt-injection / jailbreak suite (`ADVERSARIAL_FAIL_ABOVE`). Deterministic — no judge model, so it gates on every PR with no credential. |
| `python3 scripts/run-evals.py --suite rag_poison` | — | RAG poisoning suite (`RAG_POISON_FAIL_ABOVE`). Scores `prompt_guard.scan_documents` over poisoned/benign document twins. Deterministic — no judge, no credential. Proves poisoned context is quarantined before prompt assembly; makes no claim about a model's own resistance. |
| `python3 scripts/run-evals.py` | `--skip-without-judge-credentials` | Skip (exit 0) when the `judge` role's credential is absent, naming the variable. For CI steps that must not go red on an unconfigured judge. See OPERATIONS.md "When a gate blocks, and when it steps aside". |
| `python3 scripts/run-security-checks.py` | `--mode ci --strict` | Multi-framework security harness (P12). |
| `python3 scripts/verify_system.py --check-security` | — | Smoke subset of the security harness. |

### Maintenance

| Command | Arguments | Description |
|---|---|---|
| `agentsmith scrub` | `[directory] [--yes]` | Interactive removal of runtime artefacts from a project directory — lists every exact path it will delete before prompting for confirmation. |
| `agentsmith upgrade` | `[--to VERSION]` | Refreshes the current tenant repo's vendored `scripts/`, `runtime/` (with only the five harness-delegated `runtime/test` suites) and `fixtures/` from `~/.agent-framework`, regenerates their `ruff.toml` excludes, bumps `.agenticframework/tenant.yaml`'s `framework.version`, and commits. Needs `tenant.yaml`. Leaves a foreign `runtime/` alone and does nothing in a tenant that installs `agentsmith-runtime` as a package. Does **not** refresh workflows or composite actions. Fails loudly (and stops) if the commit itself fails, rather than reporting "Upgrade complete" regardless. |
| `agentsmith tenant onprem-scaffold` | — | Copy the on-prem deploy template (Docker Compose or Helm, `templates/onprem-deploy/`) into the current repo's `deploy/onprem/` for in-border / air-gapped clusters. Full walkthrough: OPERATIONS.md. |
| `agentsmith uninstall` | `[--yes] [--purge]` | Machine-level removal: restores `git init.templateDir` to its pre-install value, removes `~/.local/bin/agentsmith` and any AgentSmith block left in a shell profile; `--purge` also removes `~/.agent-framework` (including the command itself) and `~/.git_templates`. Asks for confirmation unless `--yes`. |
| `agentsmith gates list` | — | The gates this repo's CI declares — every step tagged `# agentsmith:gate` in `.github/workflows/`, as a table. The same table `docs/validation-checklist.md` carries, generated from the same tags, so there is no second list to drift. |
| `agentsmith gates run` | `[--only TEXT] [--services] [--fail-fast] [--allow-install]` | Run that list here, before pushing. Three counts, never two: passed, failed, and **skipped** with the reason — a tool that is not installed, a service container CI starts, an expression only CI can answer. Dependency-install lines are dropped and named (this is not a fresh runner); `--allow-install` runs them. It does not reproduce the runner image or the setup steps, so CI stays the authority — this answers "does this gate pass here". |
| `agentsmith gates repair` | — | Lists commits that reached this repo without passing the gate — a `--no-verify` commit, an unarmed clone, a rebase — and how to bring each under a design and review. The same sweep the hooks run, so this list is the one refusing your commit. |
| `agentsmith doctor` | `[verify_system flags]` | Runs `scripts/verify_system.py` (the tenant's copy, else the machine's) with the flags given. |
| `agentsmith purge-idempotency` | — | Deletes idempotency rows past their TTL (OPERATIONS.md §9). |
| `agentsmith version` | — | The installed framework version. |

### Multi-Tenancy (see OPERATIONS.md for the full walkthrough)

| Command | Arguments | Description |
|---|---|---|
| `agentsmith tenant init` | `<id> [--stack STACK] [--isolation shared\|dedicated]` | Scaffolds `.agenticframework/tenant.yaml` and per-environment CI/CD workflows in the current repo. |
| `agentsmith tenant promote` | `<id> --from staging --to production` | Verifies the staging eval gate, then opens a `develop → main` promotion PR. No direct push to `main`. Refuses if `<id>` doesn't exactly match the current repo's `.agenticframework/tenant.yaml` — a same-prefix tenant id (e.g. `acme` vs. `acme-sandbox`) is not a match. |

### Runtime Flags (Environment Variables)

| Variable | Effect |
|---|---|
| `DISABLE_AI_STACK=true` | Hooks skip for that command. With an enterprise org policy installed, the policy decides instead (see §16) |
| `AGENTSMITH_SWEEP_BATCH` | How many unverified commits one bypass sweep checks before deferring the rest to the next one (default 200). The sweep runs at every commit, push, session start and turn end, so this bounds what any of them costs after a long fetch; nothing is skipped — an unchecked commit stays unverified |
| `AGENTSMITH_STATE_DIR` | Where machine state is read and written instead of `~/.agent-framework/state` — the mode, install mode and dashboard endpoint. For sandboxes and test isolation; the hooks honour it too |
| `AGENTSMITH_IDE` | Which agent is running the process gate (`claude`, `cursor`, `antigravity`, `copilot`, `gemini`, `codex`). Set by each IDE's generated hook config; it names the caller on the gate's `agent.gate.*` spans. Unset reads as `unknown`, never as a guess |
| `AGENTSMITH_PYTHON` | The interpreter `.githooks/process-gate` runs the gate with, tried before `$AGENTSMITH_DIR/.venv`, `~/.agent-framework/.venv` and the repo's own `.venv`. It needs Python 3.11+ with pydantic and opentelemetry |
| `SEMVER_LOOP_GUARD=true` | Prevents infinite loop in post-commit semver tagging |
| `AGENTSMITH_AUTOPUSH=0` | post-commit still auto-tags but does not push (same as `git config agentsmith.autopush false` for one repo). Use it instead of `git -c core.hooksPath=/dev/null`, which also skips pre-commit and commit-msg |
| `AI_BREAK_GLASS_TOKEN=<token>` | Required for any hook bypass — `DISABLE_AI_STACK=true` or `agentsmith mode off` — when the installed org policy sets `bypass_policy: break-glass` (enterprise pack, see enterprise/README.md). Must be a real IT-issued, HMAC-signed token with an expiry — not just any non-empty string — validated against `BREAK_GLASS_HMAC_KEY` on the machine. |
| `OPS_PORTAL_URL` / `AUDIT_LOG_WRITE_TOKEN` | When both are set, `agentsmith tenant promote`, `agentsmith upgrade`, `agentsmith tenant onprem-scaffold` and every hook bypass under an org policy best-effort write signed events to the Ops Portal's audit log. If unset, or the write fails, the event is appended to `~/.agent-framework/local-audit-fallback.log` instead of being dropped. |

#### Security controls

These change what the guardrails enforce. Several were readable only from the
source until now — including `TOOL_ALLOWLIST_STRICT`, which KYC Sentinel's CI
already sets.

| Variable | Default | Effect |
|---|---|---|
| `PROMPT_GUARD` | `default` | `off` \| `warn` \| `default` \| `strict`. `default`/`strict` block; `warn` reports only. An unrecognised value falls back to `default` — a typo must never silently disable the guard. |
| `PROMPT_DENYLIST_PATH` | `.agent-rfc/security/prompt_denylist.txt` | Extra injection patterns, one per line, on top of the built-ins. |
| `TOOL_ALLOWLIST_STRICT` | off | `1` enforces the allowlist: a tool not on it raises `ToolNotAllowedError`. **Fail-closed** — with strict on and no allowlist loaded, *every* tool is denied rather than allowed. |
| `TOOL_ALLOWLIST_PATH` | `.agent-rfc/security/tool_allowlist.yaml` | Where the allowlist is read from. Without strict it is advisory. |
| `MODERATION_HOOK` | `optional` | `off` \| `optional` \| `required`. `required` fails the harness when the tenant declares no `moderation.hook`. |
| `INPUT_GUARDRAIL` | `default` (`off` in development) | `off` \| `default` \| `custom` — PII scrubbing before any model call. Note it self-disables in `ENVIRONMENT=development`. |
| `ENABLE_IP_REDACTION` | `false` | `true` also redacts IP addresses from exported traces. Off by default because IPs are often needed for debugging. |
| `SECURITY_STRICT` | off | `1` is equivalent to `run-security-checks.py --strict`, for CI that sets env rather than args. |
| `AGENTSMITH_TENANT_ROOT` | cwd | Which repo the security harness grades. Only for callers that cannot set the working directory — the harness resolves the tenant from cwd otherwise. |

#### Evals and model routing

| Variable | Default | Effect |
|---|---|---|
| `AGENT_JUDGE_MODEL` | — | **Only applies when no `judge` role is declared.** The registry wins; a set-but-ignored value is logged with both models. Inverted after a shell profile silently regraded every local eval with a different model than CI used. |
| `EVAL_FAIL_BELOW` | `0.80` | Golden-suite threshold. Prefer `fail_below` on the judge role in `models.yaml`: thresholds are calibrated per grader, and declaring it there keeps the two in step. Precedence: CLI `--fail-below` → registry → this → default. |
| `FAIRNESS_FAIL_BELOW` | `0.80` | Fairness suite rationale QUALITY only. Calibrated per judge, so it moves when the judge changes. |
| `FAIRNESS_PARITY_FAIL_BELOW` | `1.0` | The floor the WORST protected-attribute pair must clear. Separate from the bar above on purpose: parity measures whether a rating moved on a protected attribute, which no grader recalibration should ever loosen. Gated on the worst pair, not the mean — averaging let one diverging pair pass by being outnumbered. |
| `FAIRNESS_SCORE_SPREAD_FAIL_ABOVE` | `0.25` | Ceiling on how far two members of a pair may diverge in SCORE — enforced **only where both were graded on byte-identical output**. Parity above compares the `fairness` dimension alone, and KYC Sentinel's gender pair passed it at 1.000 while the judge scored the female-framed case 1.00 and the male-framed one 0.33 on the same text, twice. Where outputs differ a score gap is a quality signal and belongs to the bar above, so it is not gated here. Provisional: observed spreads were 0.0 or 0.67 with nothing between. |
| `HALLUCINATION_FAIL_ABOVE` | `0.05` | Max flagged-claim rate among cases expected to be CLEAN. Cases marked `expect_hallucination` are excluded — being flagged is the right answer for them, and a suite with no such case measures false positives only. |
| `ADVERSARIAL_FAIL_ABOVE` | `0.10` | Max prompt-injection miss rate. |
| `RAG_POISON_FAIL_ABOVE` | `0.10` | Max miss rate for the RAG poisoning suite. Counts BOTH directions: a poisoned document that is not quarantined, and a benign one that is. A guard that quarantines everything stops the attack and destroys retrieval, so it must not be able to score perfectly. |
| `EVAL_RPM` | *(unset)* | Paces judge calls to at most this many per minute. Unset means no pacing — the right default on a paid key, where pacing only costs wall-clock. **Fixes per-minute limits, not per-day ones.** Against a per-minute cap it turns a burst that would exhaust `cost_router`'s 4-attempt 429 retry into a suite that completes; against a *daily* cap it cannot help, and the symptom looks identical. Tell them apart from the provider's error: a per-day refusal names a total (Gemini's free tier reports `generate_content_free_tier_requests, limit: 20`) and arrives even when the observed rate is far below any per-minute ceiling. For a daily cap the fix is fewer judged cases per run — split suites across triggers — or a paid tier. Either way, note what an exhausted judge does: every case carries an error, `run_scorecard` reports "judge was unreachable" and returns **0**, so an unpaced free-tier run does not fail — it never grades. |
| `AGENT_MODEL_PROFILE` | *(unset)* | Selects which `profiles:` block in `models.yaml` binds the roles — `local`, `hybrid`, or any profile you define. Wins over `AI_STACK_MODE` from the environment, which wins over the machine's mode recorded by `agentsmith mode local` / `agentsmith mode hybrid`. Falls back to `default_profile`. Ignored by a registry using the flat `models:` shape. |
| `AGENT_MODEL_ARCHITECT` · `AGENT_MODEL_COMPLEX` · `AGENT_MODEL_STANDARD` · `AGENT_MODEL_FAST` · `AGENT_MODEL_LOCAL` | the matching registry role | Override one routing tier without touching `models.yaml`. `AGENT_MODEL_LOCAL` is the offline fallback and resolves to the `fast` role. |
| `AGENT_DEFAULT_MODEL` | `unknown` | Model name recorded in agent log entries when a caller supplies none. Labelling only — it routes nothing. |
| `AGENT_BURST_TOKEN_LIMIT` | `50000` | Circuit-breaker burst ceiling before token-velocity trips. |

#### Providers and endpoints

| Variable | Effect |
|---|---|
| `ANTHROPIC_API_KEY` · `OPENAI_API_KEY` · `GROQ_API_KEY` · `XAI_API_KEY` · `GEMINI_API_KEY` · `OPENROUTER_API_KEY` · `AZURE_OPENAI_API_KEY` | Provider credentials. A role may declare its own variable via `api_key_env` — e.g. a judge on a separate account, so a quota exhaustion on the actor cannot also take out its reviewer. |
| `GITHUB_MODELS_TOKEN` | GitHub Models free tier for `gpt-*` ids instead of a billed `OPENAI_API_KEY`. In Actions the automatic `GITHUB_TOKEN` is used; this is the local-dev override (`export GITHUB_MODELS_TOKEN=$(gh auth token)`). |
| `OLLAMA_BASE_URL` | Local Ollama host (default `http://localhost:11434`). |
| `OLLAMA_API_KEY` | Only for an Ollama behind an authenticating proxy; the literal `ollama` otherwise. |
| `OPENAI_BASE_URL` | Cloud host the network watchdog probes for reachability. |
| `EMBEDDING_MODEL` | sentence-transformers model for the vector store (default `all-MiniLM-L6-v2`). |
| `VECTOR_BACKEND` | `memory` (default) or `postgres` (needs pgvector + `DATABASE_URL`). |
| `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN` / `HF_BASE_URL` | Hugging Face credentials and host for `verify_sovereign_endpoint.py` (UAE sovereign Falcon routes). `HF_TOKEN` wins. |
| `HUAWEICLOUD_SDK_AK` / `HUAWEICLOUD_SDK_SK` | Huawei ModelArts credentials — that adapter authenticates by AK/SK, not an API key. |
| `TENANT_WORKER_MODULE` | Import path to a tenant's workflow/activity module, so the shipped worker can be used without copying it into the tenant repo. |

#### Desktop notifications

| Variable | Default | Effect |
|---|---|---|
| `AGENT_NOTIFY_WEBHOOK` | unset | Slack / Teams / custom webhook for async delivery. Posted from a background thread — a notification never stalls an agent. |
| `AGENT_NOTIFY_SOUND` | `Ping` | macOS sound name for `osascript` alerts. |
| `AGENT_NOTIFY_ICON` | unset | Path to an icon for desktop notifications. |

---

This manual covers solo/team dev-mode usage. For multi-tenancy, the production
runtime, the Ops Portal, and the enterprise pack (SSO, audit log, signed hook
bundles, dedicated worker pools), see **[OPERATIONS.md](./OPERATIONS.md)**.

*For the full technical specification including data schemas, component inventory, and design decisions, see [SPECS.md](./SPECS.md).*
