# AgentSmith — User Manual

**For:** Developers using AgentSmith day-to-day (solo / dev mode)

> **Scope:** this document owns day-to-day dev-mode usage and the
> **canonical command reference (the Command Reference section)**. Framework introduction:
> [README.md](../README.md) · formal specification: [docs/DESIGN.md](DESIGN.md) ·
> operator lifecycle (teams, production, CI/CD, portal, enterprise):
> [docs/UserManual.md](UserManual.md) · versions: [CHANGELOG.md](../CHANGELOG.md)

---

## Contents

1. [Installation](#installation)
2. [First-Time Setup](#first-time-setup)
3. [Applying to a Project](#applying-to-a-project)
4. [Daily Operations](#daily-operations)
5. [Execution Modes](#execution-modes)
6. [Writing Agent Specifications (RFCs)](#writing-agent-specifications-rfcs)
7. [Observability Dashboard](#observability-dashboard)
8. [Running Evaluations](#running-evaluations)
9. [Human-in-the-Loop (HITL) Self-Improvement](#human-in-the-loop-hitl-self-improvement)
10. [Multi-Repository & Monorepo](#multi-repository--monorepo)
11. [Team Setup](#team-setup)
12. [CI/CD via GitHub Actions](#cicd-via-github-actions)
13. [Agent Identity](#agent-identity)
14. [Cost & Budget Management](#cost--budget-management)
15. [Maintenance](#maintenance)
16. [Troubleshooting](#troubleshooting)
17. [Command Reference](#command-reference)

---

## Installation

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
# From a checkout instead (no release download): ./install-ai-stack.sh
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

## First-Time Setup

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

**Do not export it in `~/.zshrc`.** An ambient export would outrank every
tenant's declared `tenant.owner` on every repo, while CI — which has no shell
profile — gets nothing at all. A declaration wins over the environment, and an
ignored export is reported at worker startup rather than silently dropped.

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

## Applying to a Project

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

That provisions the rules and CI; it does not arm the design and review gates. To
bring an existing project under them, use `agentsmith tenant adopt` (Create an
AgentSmith-Governed Repo › Bring an existing repo under the gates).

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

## Daily Operations

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

## Execution Modes

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

## Writing Agent Specifications (RFCs)

Before an agent can modify code in any file, a corresponding spec must exist in `.agent-rfc/`.

`agentsmith tenant init` writes a template one at `.agent-rfc/001-scaffold.md` and
leaves it alone if you already have RFCs of your own. Replace every section before
an agent works from it — it is a shape, not a requirement. It is also what
satisfies the enterprise pre-commit guardrail, which requires at least one `*.md`
directly under `.agent-rfc/` (not in a subdirectory), and the `Refs: RFC-001`
trailer in the commit command the CLI prints is what satisfies the matching
commit-message rule.

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

## Observability Dashboard

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

## Running Evaluations

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
detail, thresholds, and CI wiring: the Test section):

```bash
python3 scripts/run-evals.py --suite fairness        # paired cases + pair parity; FAIRNESS_FAIL_BELOW (quality, 0.80) + FAIRNESS_PARITY_FAIL_BELOW (worst pair, 1.0)
python3 scripts/run-evals.py --suite hallucination   # two gates: false-positive rate (HALLUCINATION_FAIL_ABOVE, 0.05) + detection miss on planted cases (any miss fails)
python3 scripts/run-evals.py --suite adversarial     # prompt-injection / jailbreak; ADVERSARIAL_FAIL_ABOVE (default 0.10)
python3 scripts/run-evals.py --suite rag_poison      # poisoned retrieved context; RAG_POISON_FAIL_ABOVE (default 0.10)
python3 scripts/verify_ttft.py                       # live Ollama time-to-first-token budget; TTFT_FAIL_ABOVE_MS (default 2000)
```

### Security harness

Multi-framework `SEC-*` checks (OWASP LLM · NIST AI RMF · MITRE ATLAS ·
ISO/IEC 42001). Canonical map: [`docs/security-framework-map.md`](security-framework-map.md).
Operator detail: the Configure Features section “Multi-framework security harness”.

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

## Human-in-the-Loop (HITL) Self-Improvement

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

## Multi-Repository & Monorepo

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

There is no shared-RFC store: nothing in the framework reads an
`AGENT_SHARED_RFC_DIR` variable.

The instructions are removed rather than corrected because there is nothing to
correct them to. Setting the variable did exactly nothing and reported exactly
nothing, which is the worst way for a documented feature to be absent — you
would conclude your RFCs were being shared and never see a signal otherwise.

If you need RFC specs visible across repositories today, a symlink into each
repo's `.agent-rfc/` works and is honest about what it is. The feature is
tracked in docs/PRODUCT_BACKLOG.md.

---

## Team Setup

Team-shared infrastructure (Phoenix with auth, shared Ops Portal, shared
Postgres) is operator territory, not day-to-day dev usage — the canonical
procedure lives in **[the Install & Start section](UserManual.md)**
("Team-shared Phoenix with auth" and "standing infra"). Short version:

- One team server runs `docker compose -f docker-compose.yml -f docker-compose.auth.yml up -d`.
- Every developer sets `AGENT_PHOENIX_ENDPOINT="http://ops:<password>@<server-ip>:6007"`
  (port 6007 = the auth sidecar; 6006 stays loopback-only).
- An unauthenticated shared Phoenix is non-compliant (docs/DESIGN.md › Universal Observability Platform).

## CI/CD via GitHub Actions

The full pipeline — what each workflow gates, GitHub Environments,
deploy/rollback wiring, GCP via WIF — is operator territory:
**[the Deploy via GitHub CI/CD section](UserManual.md)**.
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

## Agent Identity

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

## Cost & Budget Management

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

## Maintenance

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
# If AgentSmith is private for you, this returns 404 and installs nothing —
# run `./install-ai-stack.sh` from an updated checkout instead (see Install
# the Framework).
curl -fsSL https://github.com/bobbyaqlaar/AgentSmith/releases/latest/download/install-ai-stack.sh | bash

# Re-apply to an opted-in project: plain `git checkout` re-fires the hook, which
# writes only what is missing. `git init` does not run post-checkout.
# To pull newer vendored scripts/ and runtime/ into it (needs
# .agenticframework/tenant.yaml, which `agentsmith tenant init` writes):
cd /path/to/project && agentsmith upgrade
```

---

## Troubleshooting

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

## Command Reference

The canonical `agentsmith` command table. Every command is a subcommand of one
program (`runtime/cli.py`), so `agentsmith <command> --help` is always current.
The older `ai-*` names map to these one for one
(`~/.agent-framework/shell/ai-compat.sh`).

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
| `python3 scripts/run-evals.py` | `--skip-without-judge-credentials` | Skip (exit 0) when the `judge` role's credential is absent, naming the variable. For CI steps that must not go red on an unconfigured judge. See docs/UserManual.md "When a gate blocks, and when it steps aside". |
| `python3 scripts/run-security-checks.py` | `--mode ci --strict` | Multi-framework security harness (P12). |
| `python3 scripts/verify_system.py --check-security` | — | Smoke subset of the security harness. |

### Maintenance

| Command | Arguments | Description |
|---|---|---|
| `agentsmith scrub` | `[directory] [--yes]` | Interactive removal of runtime artefacts from a project directory — lists every exact path it will delete before prompting for confirmation. |
| `agentsmith upgrade` | `[--to VERSION]` | Refreshes the current tenant repo's vendored `scripts/`, `runtime/` (with only the five harness-delegated `runtime/test` suites) and `fixtures/` from `~/.agent-framework`, regenerates their `ruff.toml` excludes, bumps `.agenticframework/tenant.yaml`'s `framework.version`, and commits. Needs `tenant.yaml`; refused in the framework's own checkout. Leaves a foreign `runtime/` alone and does nothing in a tenant that installs `agentsmith-runtime` as a package. Does **not** refresh workflows or composite actions. Fails loudly (and stops) if the commit itself fails, rather than reporting "Upgrade complete" regardless. |
| `agentsmith tenant onprem-scaffold` | — | Copy the on-prem deploy template (Docker Compose or Helm, `templates/onprem-deploy/`) into the current repo's `deploy/onprem/` for in-border / air-gapped clusters. Full walkthrough: docs/UserManual.md. |
| `agentsmith uninstall` | `[--yes] [--purge] [--legacy-profile-only]` | Machine-level removal: restores `git init.templateDir` to its pre-install value, removes `~/.local/bin/agentsmith` and any AgentSmith block left in a shell profile; `--purge` also removes `~/.agent-framework` (including the command itself) and `~/.git_templates`. `--legacy-profile-only` removes just the shell-function block an install before 2.0.0 appended to a shell profile, and touches nothing else. Asks for confirmation unless `--yes`. |
| `python3 scripts/verify_system.py --governed` | — | Is this repo actually governed? Lists every gap at once — the config, the four hooks, whether `core.hooksPath` points at them, the IDE hook configs, a committed knowledge graph, the artifact stubs — and separately whether the last `agentsmith gates run` was green **for this commit**. "Not installed" and "installed but never run" are different answers and it says which. |
| `agentsmith gates list` | — | The gates this repo's CI declares — every step tagged `# agentsmith:gate` in `.github/workflows/`, as a table. The same table `docs/validation-checklist.md` carries, generated from the same tags, so there is no second list to drift. |
| `agentsmith gates run` | `[--only TEXT] [--services] [--fail-fast] [--allow-install]` | Run that list here, before pushing. Three counts, never two: passed, failed, and **skipped** with the reason — a tool that is not installed, a service container CI starts, an expression only CI can answer. Dependency-install lines are dropped and named (this is not a fresh runner); `--allow-install` runs them. It does not reproduce the runner image or the setup steps, so CI stays the authority — this answers "does this gate pass here". |
| `agentsmith gates repair` | — | Lists commits that reached this repo without passing the gate — a `--no-verify` commit, an unarmed clone, a rebase — and how to bring each under a design and review. The same sweep the hooks run, so this list is the one refusing your commit. |
| `agentsmith doctor` | `[verify_system flags]` | Runs `scripts/verify_system.py` (the tenant's copy, else the machine's) with the flags given. |
| `agentsmith purge-idempotency` | — | Deletes idempotency rows past their TTL (the Maintain (Day-2 Operations) section). |
| `agentsmith version` | — | The installed framework version. |

### Multi-Tenancy (see docs/UserManual.md for the full walkthrough)

| Command | Arguments | Description |
|---|---|---|
| `agentsmith tenant init` | `<id> [--stack STACK] [--isolation shared\|dedicated] [--architecture STYLE] [--agentic] [--root DIR] [--ide NAME] [--force] [--allow-framework-root]`, or `--from INTAKE [--root DIR] [--force]` | Scaffolds `.agenticframework/tenant.yaml` and per-environment CI/CD workflows in the current repo. `--architecture` and `--agentic` are the same options `tenant adopt` takes — a new repo gets the structural style and, with `--agentic`, the agent layer (agents, allowlisted tools, the gateway, durable workflows, evals). `--from INTAKE` scaffolds from a portal intake instead — its tenant id, stack, options, IDEs and first RFC — and marks it used only once that RFC is written; it refuses the flags the intake decides. `--ide` (repeatable) writes a hook config for only the IDEs named, and records them as `workspace.ides` in `tenant.yaml` so `agentsmith sync` keeps the choice; omitted, every IDE with a verified config schema is written. `--force` overwrites existing files; `--allow-framework-root` scaffolds even inside the framework's own checkout, which is otherwise refused. |
| `agentsmith tenant adopt` | `<id> [--stack STACK] [--architecture STYLE] [--agentic] [--gate GLOB]… [--framework-ref TAG] [--root DIR] [--yes]` | Brings an existing repo under the gates: prints what it found and would do, then — on a yes — gates its code, keeps its hooks, CI, rules and design doc, and prints the adoption commit. |
| `agentsmith sync` | `[--root DIR] [--yes]` | Brings this repository's copies of the framework up to date — the gate hooks (adding any it lacks), the provider declaration, and (vendored tenants) the vendored trees — and prints a commit whose review the repository's own gates accept, because every file in it is one the framework wrote. Run it after upgrading AgentSmith. Refused in the framework's own checkout, which is what it copies from. |
| `agentsmith gate` | `<session-start\|pre-edit\|stop\|ci\|commit\|push> [--ide IDE]`, or `kg build\|impact [--staged\|--base REF]` | Answer one gate event in the neutral profile of the gate contract (`contract/gate/v3/protocol.md`; `ci` is contract 2's — a range on stdin, the verdict, a report, and the record sent to the portal when configured; `commit` and `push` are contract 3's; `kg build` rebuilds the knowledge graph and `kg impact` names the staged change's review scope as JSON): the event as JSON on stdin, the decision as JSON on stdout. This is what a tenant names as its provider; exit 3 means this machine cannot run the gate. `--ide` reads the payload in one IDE's dialect instead of the neutral profile — what the generated hook configs pass, and what an integrator needs when the caller is an IDE rather than the contract. |
| `agentsmith conformance` | `--provider "<command>" [--contract 1\|2\|3]`, or `--port record --sender "<command>" [--url-env NAME] [--token-env NAME]` / `--port record --receiver URL` | Build the contract's fixture repository, replay its cases against that command, and report per case. Run it against another platform's adapter, or against `agentsmith gate`. With `--port record`: run a gate provider against a loopback portal and judge what it sends (`--sender`), or send `contract/record/v1/cases.json` to a portal's ingest address with the test token in `GOVERNANCE_RECORD_TOKEN` and judge each answer (`--receiver` — it stores the valid record, so use a test portal). |
| `agentsmith gate --ide <id>` | `<event> --ide claude` | The same, for a payload in an IDE's dialect: the provider translates it and answers in it. The generated IDE hook configs pass this. |
| `agentsmith tenant promote` | `<id> --from staging --to production` | Verifies the staging eval gate, then opens a `develop → main` promotion PR. No direct push to `main`. Refuses if `<id>` doesn't exactly match the current repo's `.agenticframework/tenant.yaml` — a same-prefix tenant id (e.g. `acme` vs. `acme-sandbox`) is not a match. |

### Runtime Flags (Environment Variables)

| Variable | Effect |
|---|---|
| `DISABLE_AI_STACK=true` | Hooks skip for that command. With an enterprise org policy installed, the policy decides instead (see the Troubleshooting section) |
| `AGENTSMITH_SWEEP_BATCH` | How many unverified commits one bypass sweep checks before deferring the rest to the next one (default 200). The sweep runs at every commit, push, session start and turn end, so this bounds what any of them costs after a long fetch; nothing is skipped — an unchecked commit stays unverified |
| `AGENTSMITH_STATE_DIR` | Where machine state is read and written instead of `~/.agent-framework/state` — the mode, install mode and dashboard endpoint. For sandboxes and test isolation; the hooks honour it too |
| `AGENTSMITH_IDE` | Which agent is running the process gate (`claude`, `cursor`, `antigravity`, `copilot`, `gemini`, `codex`). Set by each IDE's generated hook config; it names the caller on the gate's `agent.gate.*` spans. Unset reads as `unknown`, never as a guess |
| `CLAUDE_PROJECT_DIR` | Set by Claude Code to the session's project directory. `.githooks/process-gate` uses it **only as a last resort** for which repository it was invoked in — `git rev-parse --show-toplevel` first, this next, `$PWD` last. It names the SESSION's project, which is not the repository being committed to when a session in one repo commits in another, so it is deliberately not preferred. Nothing sets it but the IDE. |
| `AGENTSMITH_TENANT_VISIBILITY` | Declares whether the repository being provisioned is `private`, `internal` or `public` (`internal` counts as private, as it does in `gh repo view`), instead of letting `hooks/post-checkout` detect it. Decides one thing: whether the IDE config files (`CLAUDE.md`, `.cursorrules`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.agents/`, `.agent-history.log`) are added to `.gitignore`, since they carry system prompt content. Unset detects as before — `gh repo view`, then any `github.com` remote is treated as potentially public. An unrecognised value warns and falls back to detection; it is never read as either answer. Set by `.github/scratch-tenants/build.sh`, whose fixture repos are public but must behave like the private tenants they stand in for |
| `AGENTSMITH_PORTAL_URL` / `AGENTSMITH_INTAKE_TOKEN` | Read by `agentsmith tenant init --from <intake>`: the portal's address, and the token shown once when the intake was created. The address must be `https`, or `http` to `localhost`; a redirect is refused, because the token would go with it. The token opens that one intake, once, for 24 hours. Leave it unset at a terminal and the CLI asks for it without echo — better than an `export`, which lands in your shell history. `AGENTSMITH_PORTAL_URL` is the same variable a CI job sets for `scripts/send_dev_record.py` |
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
bundles, dedicated worker pools), see **[docs/UserManual.md](UserManual.md)**.

*For the full technical specification including data schemas, component inventory, and design decisions, see [docs/DESIGN.md](DESIGN.md).*

---

# Part II — Operating AgentSmith

The procedures for running AgentSmith across its lifecycle: install and start, create a governed
repository, configure features, test, deploy through GitHub CI/CD, monitor, run evaluations in
production, operate the human-in-the-loop and dead-letter queues, improve, maintain and shut down.

Every command and code path in this part was run against real infrastructure while it was written
— real Postgres, real Redis, a real local OIDC provider, a real `kind` Kubernetes cluster, real GPG
keys. Where something is a known limitation it says so. The sections follow one worked example,
`examples/oil-price-agent`, so the shape is concrete before you swap in your own repository.

## Install & Start

### Two working directories — always know which one you're in

Every command in this guide runs in one of exactly two places:

| Directory | What it is | Example path |
|---|---|---|
| **AgentSmith root** | The framework repo itself — Ops Portal, Docker Compose, shared infra | `$AGENTSMITH_DIR/` |
| **Tenant app root** | Your own agentic app repo, created by `agentsmith tenant init` | `$REPO_DIR/my-oil-price-app/` |

Commands that affect the shared platform (portal, Postgres, Phoenix) run from the **AgentSmith root**. Commands that affect a specific agent app (hooks, evals, CI, sync scripts) run from the **tenant app root**. Each section below is labelled with which one applies.

### System tools

| Tool | Needed for | Check |
|---|---|---|
| uv (recommended), or Python 3.11+ | The framework's own environment, `~/.agent-framework/.venv` — built by `install-ai-stack.sh` from `requirements.lock` at the version in `.python-version`; uv fetches that interpreter itself, so Homebrew's Python is never used. Without uv, `python3 -m venv` is the fallback | `uv --version` (`brew install uv`) |
| Git 2.x | Everything | `git --version` |
| Docker 20+ | Team Phoenix, Ops Portal Postgres, dedicated worker pool testing | `docker --version` |
| Node.js 20+ | Ops Portal, In-App Widget | `node --version` |
| `gh` CLI | `agentsmith tenant promote` (opens the promotion PR) | `gh --version` |
| GnuPG | Enterprise hook bundle signing | `gpg --version` |
| Temporal CLI | `temporal server start-dev` (local dev workflow engine) | `brew install temporal` · `temporal --version` |
| `kubectl` | Dedicated tenant worker pools | `kubectl version --client` |
| Ollama | Local/offline dev mode | `ollama --version` |

> **One-time git config** — set your default branch name to `main` globally so every `git init` uses it:
> ```bash
> git config --global init.defaultBranch main
> ```

Production runtime extras for working in the checkout itself — run from the **AgentSmith root** (macOS system Python is externally managed; use a venv). This is separate from `~/.agent-framework/.venv`, which the installer builds and the git hooks use:

```bash
# Run from: AgentSmith root (e.g. $AGENTSMITH_DIR/)
python3 -m venv .venv
source .venv/bin/activate
pip install psycopg2-binary redis temporalio langgraph-checkpoint-postgres cryptography
```

To auto-activate when you `cd` into the AgentSmith root, add to `~/.zshrc`:

```bash
function cd() { builtin cd "$@" && [[ -f .venv/bin/activate ]] && source .venv/bin/activate; }
```

### `~/.zshrc` — environment variables

These must be set before running `install-ai-stack.sh` or any `agentsmith` commands. Add them to `~/.zshrc` (or `~/.bashrc`) so they persist across sessions. They are the only thing a shell profile is for now: the installer writes nothing to it, and the mode `agentsmith mode` records lives in `~/.agent-framework/state/`, not in an export:

```bash
# ── Directories ───────────────────────────────────────────────────────────────────
export REPO_DIR="$HOME/repos"            # root directory for all your repos; adjust if different
export AGENTSMITH_DIR="$REPO_DIR/AgenticFramework"  # AgentSmith framework root

# ── Identity — DO NOT set here ─────────────────────────────────────────────────────
# Resolves from .agenticframework/tenant.yaml `tenant.owner`, then
# AGENT_OWNER_ID, then `git config user.email`. Exported in a shell profile it
# is AMBIENT: it outranks every tenant's declaration on this machine and is
# absent in CI entirely. Set it per-deployment (a container, a CI job), or not
# at all.

# ── LLM providers — add whichever you use (at least one required for hybrid mode) ───
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export GROQ_API_KEY="gsk_..."           # optional: fast/cheap inference via Groq
export OPENROUTER_API_KEY="sk-or-..."   # optional: ONE key fronting many vendors
export XAI_API_KEY="xai-..."            # optional: Grok
export GEMINI_API_KEY="AIza..."         # optional: Google AI Studio (NOT vertex_ai,
                                        # which uses service-account OAuth instead)
# Prefer a repo-root .env over a shell profile for these. A profile is
# machine-wide and invisible: an AGENT_JUDGE_MODEL exported there silently
# graded every local eval with a different model than CI used.

# ── Observability ──────────────────────────────────────────────────────────────────
export AGENT_PHOENIX_ENDPOINT="http://localhost:6006"  # change to team server URL if shared
export OTEL_EXPORTER_OTLP_ENDPOINT="${AGENT_PHOENIX_ENDPOINT}/v1/traces"  # optional: without it, Python falls back to the endpoint `agentsmith dashboard start` recorded

# ── Budget and routing ─────────────────────────────────────────────────────────────
export AGENT_MONTHLY_USD_CAP="50"               # hard cap across all projects (dev mode)
# AGENT_JUDGE_MODEL — leave unset. The eval judge comes from the `judge` role
# in models.yaml (framework default: falcon3:3b, local — distinct from the
# architect model so the grader is never the author). Set this only to override
# a single run; exporting it from your profile overrides every tenant's own
# declared judge route.

# ── Production runtime (only needed when running runtime/ against real backends) ───
export DATABASE_URL="postgresql://user:pass@localhost:5433/agenticframework"
export REDIS_URL="redis://localhost:6379/0"     # only if IDEMPOTENCY_BACKEND=redis
export TEMPORAL_ADDRESS="localhost:7233"        # only if WORKER_BACKEND=temporal
export IDEMPOTENCY_BACKEND="postgres"           # postgres | redis | memory
export BUDGET_BACKEND="postgres"                # postgres | redis
# PG_POOL_MAX=5 — max pooled Postgres connections per DSN per worker process
# (runtime/pg_pool.py, shared by budget/idempotency/DLQ stores). Keep
# workers × PG_POOL_MAX + the portal's own pool (10) under the server's
# max_connections. Default is fine for most deployments.

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

# Audit log — two separate secrets serve two different roles (docs/DESIGN.md › Enterprise Install and Compliance Pack):
# AUDIT_LOG_WRITE_TOKEN — bearer token gating POST /api/audit/append.
#   Used by install-ai-stack.sh to post hook-bypass events to the portal.
#   Not needed in ~/.zshrc. Generate: openssl rand -hex 32
# AUDIT_LOG_HMAC_KEY — HMAC-SHA256 key used to sign every audit event at write
#   time (portal/lib/auditLog.ts). At read time the portal re-signs and compares;
#   a mismatch means the row is UNVERIFIED — either altered, or signed under a
#   different key (see the rotation warning below). Second layer after the DB triggers
#   that block UPDATE/DELETE on audit_log. SERVER-SIDE ONLY — never export to
#   ~/.zshrc or tenant apps. ROTATION WARNING: old events stay signed with the old
#   key and will fail re-verification after a rotation. Generate: openssl rand -hex 32
AUDIT_LOG_WRITE_TOKEN=<random-secret>    # generate: openssl rand -hex 32
AUDIT_LOG_HMAC_KEY=<random-secret>       # generate: openssl rand -hex 32  — rotate with care

# HITL blob encryption (production trace redaction — docs/DESIGN.md › Trace Redaction)
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
# SSO_REVOCATION_MODE=fail-open   # or fail-closed → HTTP 503 when session-status unreachable (SEC-SSO-001)
```

#### b. Tenant app `.env` — your agentic app's runtime config

> **You don't have a tenant app directory yet.** This section is a reference template —
> skip it for now and return here after you run `agentsmith tenant init` in the Create an AgentSmith-Governed Repo section. At that point
> you'll have a directory to put this file in.

> **Where:** `my-tenant-app/.env` (your own app repo root — **not** the AgentSmith root)
> **How:** created manually or by `agentsmith tenant init` scaffolding; never committed — add `.env` to your tenant app's `.gitignore`.

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
| whichever key the `judge` role declares | CI eval judge | **Not a fixed name.** It follows the `judge` role in the merged registry — `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, a role-level `api_key_env`, whatever that role points at. Run `--skip-without-judge-credentials` and the skip message names the exact variable. YAML cannot look up a secret by a name computed at runtime, so pass every plausible provider key through to the step and let the code decide — and **update that list when you repoint the judge**. A tenant that moved its judge to Gemini and left the list naming Anthropic/Groq/OpenAI had all three judged gates skip silently, reporting success, for every run. |
| `ANTHROPIC_API_KEY` · `OPENAI_API_KEY` | Hybrid-mode tests | Required only if a hybrid profile routes an actor role to them |
| `AGENT_PHOENIX_ENDPOINT` | Trace export from CI | Optional — CI passes without it |
| `OPS_PORTAL_URL` | CD → portal history sync | Optional — sync skipped if absent |
| `OPS_PORTAL_SYNC_TOKEN` | CD → portal history sync | Required if `OPS_PORTAL_URL` is set |
| `DEPLOY_COMMAND` | Production deploy step | Platform-specific (Fly, Railway, ECS, etc.) |
| `ROLLBACK_COMMAND` | Rollback on smoke failure | Optional — prints guidance if absent |

---

### Pinned / checksum-verified install (team environments)

```bash
# Pinned version (recommended for team environments).
# Set VERSION to a published tag — see github.com/bobbyaqlaar/AgentSmith/releases
# (this example is deliberately not a real tag: a number written here goes stale
#  the next release, and v1.1.1 sat here two majors behind the page's own links)
VERSION=vX.Y.Z
BASE=https://github.com/bobbyaqlaar/AgentSmith/releases/download/$VERSION

curl -fsSL "$BASE/install-ai-stack.sh" | bash
```

```bash
# With checksum verification (supply-chain safety). Verify BEFORE executing —
# the point is to not run the script until it matches.
curl -fsSL "$BASE/install-ai-stack.sh"        -o install-ai-stack.sh
curl -fsSL "$BASE/install-ai-stack.sh.sha256" -o install-ai-stack.sh.sha256
shasum -a 256 --check install-ai-stack.sh.sha256   # must print "OK"
bash install-ai-stack.sh
```

If a release is GPG-signed (`ORG_GPG_KEY_ID` configured on the release
workflow), `install-ai-stack.sh.sig` is published alongside it — verify that
instead for a real trust anchor. The `.sha256` only detects a corrupted or
truncated download; it is served by the same host as the script, so it proves
nothing about origin.

> **Substitute a real tag.** Every artifact above is published per-release, and
> an unpublished version 404s. `curl -fsSL … | bash` on a 404 **exits 0**:
> curl's error goes to stderr, bash receives an empty script and succeeds, and
> the pipeline reports the exit status of `bash`. Verified. So a wrong tag looks
> like a clean install that did nothing — which is how the version documented
> here stayed dead through a whole release cycle. Use
> `releases/latest/download/…` for "whatever is current" rather than a pin, and
> check `agentsmith status` afterwards rather than trusting the exit code.

### Machine install, mode, and standing infra

```bash
# Install (the Install & Start section) — vendors scripts/hooks/templates to ~/.agent-framework,
# sets git's global init.templateDir (developer mode; use --mode enterprise
# to skip that — see the Enterprise Pack section).
# From a checkout instead (no release download): ./install-ai-stack.sh
curl -fsSL https://github.com/bobbyaqlaar/AgentSmith/releases/latest/download/install-ai-stack.sh | bash
# Nothing to reload: `agentsmith` is linked at ~/.local/bin (the installer says
# if that is not on your PATH).

# Identity — nothing to export. Resolves from tenant.yaml `tenant.owner`,
# then AGENT_OWNER_ID, then `git config user.email`. In a shell profile it is
# ambient: it outranks every tenant on the machine and is absent in CI.

# Mode — pick one (switch anytime). Recorded for the whole machine, so an IDE,
# a git GUI and the hooks see it too; an AI_STACK_MODE export still wins in the
# shell that has it.
agentsmith mode local     # 100% offline, Ollama, zero cost
agentsmith mode hybrid    # cloud frontier models, needs ANTHROPIC_API_KEY/OPENAI_API_KEY

# Health check — confirms Phoenix, mode deps, no unresolved issues
agentsmith check
```

Production-runtime extras, only if you'll exercise the Configure Features section's production runtime for real — run from the **AgentSmith root**:

```bash
# Run from: AgentSmith root
source .venv/bin/activate   # activate the venv created in the Install & Start section Prerequisites
pip install psycopg2-binary redis temporalio langgraph-checkpoint-postgres cryptography
```

**Standing infra:** if Docker is available, `agentsmith dashboard start` manages a
machine-wide stack (Phoenix + Postgres + Ops Portal, `restart:
unless-stopped`) shared across every repo on this machine — not just the
one you're in. Vendored to `~/.agent-framework/observability/` during
install (`docker-compose.yml` + `init-db/` + `portal/`, copied from this
repo's own — see `docker-compose.yml`'s header for the manual equivalent).
Without Docker, or in a repo that opts out (next paragraph), it falls back
to a plain-process Phoenix launch with no Postgres/Ops Portal — unchanged
from the original solo-dev behavior.

**Per-repo opt-out:** `touch .agenticframework/no-shared-infra` before
`git init`/`agentsmith tenant init` in a repo that needs full isolation (a client
demo, an air-gapped environment, or just not wanting this repo's traces on
the shared instance). `agentsmith dashboard start` then always uses the standalone
plain-process Phoenix path for that repo, and `agentsmith tenant init` won't nudge
you toward the shared Ops Portal's env vars in its scaffolding output.

### Team-shared Phoenix with auth

An unauthenticated shared Phoenix instance is non-compliant (docs/DESIGN.md › Universal Observability Platform) —
the base `docker-compose.yml` binds Phoenix's own port to `127.0.0.1` only,
so by default it's **not reachable from other machines at all**.

#### Solo dev (unchanged)

```bash
docker compose up -d
curl http://localhost:6006/healthz   # works — you're on localhost
```

#### Team server: add the auth overlay

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

See [docker-compose.yml](../docker-compose.yml) and
[docker-compose.auth.yml](../docker-compose.auth.yml) header comments for the
full rationale (why this is a separate file, not a Compose profile).

---

---

## Create an AgentSmith-Governed Repo

A **tenant** is a customer application with its own independent repository,
agents, eval suite, and deployment track (docs/DESIGN.md › Tenancy Model (Independent Repositories)). New repos opt in
on the first `git checkout` of a fresh repo (git does not run the hook on `git init` itself); pre-existing/cloned repos opt in explicitly
(`mkdir -p .agenticframework && touch .agenticframework/enabled`, then any
checkout) — see README "Opt-in model".

> **Starting a new tenant app — nothing to copy manually.**
>
> For any repo that is not based on the oil-price-demo example, the full
> scaffolding is handled automatically — no files need to be copied from
> the AgenticFramework directory:
>
> | What you get | How it arrives |
> |---|---|
> | `.agent-rfc/`, `.cursorrules`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.agents/skills/`, Knowledge Graph seed | `post-checkout` hook fires on `git init -b main` |
> | `.agenticframework/tenant.yaml`, `.github/workflows/` (ci-*, cd-*, eval-* reusable workflows), `.github/actions/` (composite actions the CD workflows call) | `agentsmith tenant init <id> --stack <stack>` |
> | `.env` | You create from the the Install & Start section tenant-app `.env` template |
> | `runtime/` (LLM gateway, base workflow, idempotency, DLQ, …) | **Never copied** — accessed via `$AGENTSMITH_DIR/runtime` at run time |
>
> Every file in the first row above is a `templates/agent-rules.yaml` render,
> including the design/validation playbooks (below) — one hook, one
> generator, so both onboarding paths get them: a fresh `git init` and an
> explicit opt-in on a pre-existing repo (`mkdir -p .agenticframework &&
> touch .agenticframework/enabled`, then any checkout) run the identical
> `generate-ide-config.py` call.
>
> What you write yourself: `worker.py`, `workflows/`, `workflows/activities.py`
> — use `examples/oil-price-agent/` as a structural reference only.
>
> ```bash
> mkdir $REPO_DIR/my-app && cd $REPO_DIR/my-app
> git init -b main                               # hooks fire automatically
> agentsmith tenant init my-app --stack python-fastapi   # scaffolds tenant.yaml + CI/CD
> # create .env from the the Install & Start section tenant-app template, then write your worker.py and workflows/
> ```

### Design & validation playbooks (all onboarding paths)

Two `agent-rules.yaml` skill entries — `design_review` and
`validation_review` — reach every target `generate-ide-config.py` writes
(`.cursorrules`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
`.github/copilot-instructions.md`, `.agents/skills/*/skill.md`), not only
Antigravity's skill files. They point at
`docs/design-review-checklist.md` (read before and during a build — a
Definition-of-Ready equivalent, reframing every `docs/review-levers.md`
lever as build-time guidance) and `docs/validation-checklist.md` (read
before merge — a Definition-of-Done equivalent that works the levers group
by group against the change and sets the testing/gate obligations).

Both docs live under the FRAMEWORK's `docs/`, which — unlike `scripts/` and
`templates/` — is not vendored into a tenant repo by the post-checkout hook.
`install-ai-stack.sh` copies these two specific files (not all of `docs/`)
into `~/.agent-framework/docs/`, so every generated pointer resolves two
ways: `$AGENTSMITH_DIR/docs/<file>` on a live checkout, or
`~/.agent-framework/docs/<file>` on the installed package. Both paths are
printed in the generated text — see `_playbook_location` in
`generate-ide-config.py` — because generation happens once, at provisioning
time, and which of the two applies later is not knowable then.

If your IDE or agent harness isn't in that list (this framework's own set
of named targets is Cursor, Claude Code, Codex, Gemini CLI, Antigravity and
GitHub Copilot/VS Code), `AGENTS.md` is the documented cross-tool fallback —
see its own header comment for why it's self-contained rather than a
pointer to `.cursorrules`.

### Scaffold a new tenant repo (`agentsmith tenant init`)

```bash
cd /path/to/your-tenant-repo   # must be a git repo
agentsmith tenant init acme --stack python-fastapi --architecture hexagonal --agentic
```

Stack options: `python-fastapi` (default), `go`, `ts-react`. Add
`--isolation dedicated` if this tenant needs its own worker pool (the Deploy via GitHub CI/CD section "Dedicated isolation tier").

**Architecture.** `--architecture` names the application's structural style, and `--agentic` adds
the agent layer on top of any of them:

| Style | Also known as | Fits |
|---|---|---|
| `layered` | n-tier | CRUD-heavy work with modest domain logic, one deployable |
| `modular-monolith` | modulith | One deployable, modules by business capability with narrow interfaces |
| `hexagonal` | clean architecture, ports and adapters, onion | Substantial domain logic that must outlive its frameworks and providers |
| `microservice` | | One independently deployable service with its own data and contract |
| `event-driven` | | Work spanning components or time; producers and consumers joined by events |

The style becomes the Architecture section of `docs/DESIGN.md` — the layers with their paths for
your stack, the direction dependencies may point, where tests go, what to watch for — and one line
every agent session starts with. `--agentic` adds the agent layer: where agents, tools and
workflows sit in that style, and their rules (every model call through the gateway, tools
deny-by-default, retrieved content treated as data, a human for high-impact actions, an independent
judge). Both are optional; without a style, `docs/DESIGN.md` says one is still to be chosen.

**The first commit.** The gates are armed by the scaffold, so the scaffold itself needs a design
and a review. `tenant init` writes the design (`.agent-rfc/designs/scaffold.md`, scoped to exactly
what it wrote, and closed) and records a hash of every file it wrote in
`.agenticframework/scaffold.json`. Commit it as the run prints:

```bash
git add -A && git commit -m "chore: scaffold acme" -m "Design: .agent-rfc/designs/scaffold.md" -m "Review: n/a: generated scaffold"
```

The gate accepts that review only on the repository's first commit and only while every gated file
still matches its hash; change one, or add code, and it asks for a real review. Add code in the
next commit, under a design of its own.

**Vendoring.** When the repo was created on a machine with AgentSmith installed, `git init` put the
machine's hooks in `.git/hooks`; `tenant init` runs their `post-checkout` before writing the
manifest, so the vendored `scripts/`, `runtime/` and `fixtures/` go into that first commit too, and
the workflows' `scripts/*.py` steps can run. Those hooks keep running behind the gates. If the run
says nothing was vendored, run `git init` in the repo (it adds the machine's hooks and changes
nothing else) and re-run `tenant init` with `--force`, before the first commit.

This writes:
- `.agenticframework/tenant.yaml` — tenant id, isolation tier, framework version pin, per-environment Phoenix namespaces and eval thresholds
- `.github/workflows/ci-<stack>.yml`, `cd-staging.yml`, `cd-production.yml`, plus the reusable eval / security workflows the CI file calls (`eval-scorecard.yml`, `eval-fairness.yml`, `eval-hallucination.yml`, `eval-ttft-live.yml`, `eval-security.yml`, called with `strict: true` by every stack's CI template)
- `.github/actions/{gcp-auth,build-push-ghcr,deploy-placeholder,rollback-notify,install-python-deps}` — composite actions the workflows reference as `uses: ./.github/actions/<name>` (resolved inside this repo)
- Copy security templates from `fixtures/security/templates/` into `.agent-rfc/security/` (risk register, agency manifest, tool allowlist, NIST profile) — see [docs/security-framework-map.md](security-framework-map.md). **CI is red until you edit two of them:** the strict harness fails on the shipped placeholder `risk_register.yaml` and `agency_manifest.yaml`, on every stack

Re-running is idempotent — existing files are never overwritten (`--force` replaces them, and
regenerates the scaffold's design and manifest).

### Bring an existing repo under the gates (`agentsmith tenant adopt`)

`tenant init` is for an empty repo. For one with history, code and tooling of its own:

```bash
cd /path/to/existing-repo
agentsmith tenant adopt acme --architecture hexagonal
```

**What it writes, and why it is not a copy of AgentSmith.** The file that matters is
`.agenticframework/providers.json`: the repository's declaration of *who governs it*
(`contract/gate/v3/providers.schema.json`).

```json
{ "contract": 3, "providers": { "gate": { "command": "agentsmith gate", "version": "^2",
  "setup": "bobbyaqlaar/AgentSmith/.github/actions/setup-agentsmith@v2.1.0" } } }
```

`.githooks/process-gate` reads that before it falls back to the framework's own paths, so the hooks
name a provider rather than a file layout. At contract 2 the gates workflow does too: it runs the
`setup` step named there and asks the provider whether the pushed range passes — no checkout of
AgentSmith, no framework path in the workflow, and no fallback if the provider cannot answer. At
contract 3 the git hooks do the same for each commit and push — and if a commit is refused with
"older than the gate contract this repository declares", the `agentsmith` on that machine predates
the repository's declaration: re-run `install-ai-stack.sh`. Point `gate.command` at another platform's command and
this repository is governed by that platform instead — `agentsmith conformance --provider "<command>"`
scores it against the contract first. `"gate": "none"` declares the repository deliberately
ungoverned, and is never overridden by a fallback.

It reads the repo and prints a plan before writing anything: the stack, the paths it will gate
(each top-level directory git tracks source files in, plus source files at the root — or exactly
the `--gate GLOB`s you pass), the hooks the repo already runs, and for every file whether it will
be created, merged or left alone. Answer `y` to go ahead; off a terminal, pass `--yes`.

**What it writes — 28 files**, and none of them is AgentSmith's own code:

| Group | Files |
|---|---|
| The declaration and the manifest | `.agenticframework/providers.json`, `tenant.yaml`, `process-gates.json`, `scaffold.json` |
| The gate hooks | `.githooks/process-gate`, `commit-msg`, `pre-commit`, `pre-push`, and `chain` — which runs whatever hooks the repo already had |
| IDE hook wiring | `.claude/settings.json` (merged — your permissions stay), `.cursor/hooks.json` |
| Agent rule files | `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `GEMINI.md`, `.github/copilot-instructions.md` — each gets a marked block appended if it exists, and is created if it does not; plus six `.agents/skills/<name>/skill.md` for Antigravity |
| CI | `.github/workflows/agentsmith-gates.yml`, `agentsmith-sync.yml` |
| Records | `.agent-rfc/designs/adoption.md`, `.agent-rfc/fixtures/knowledge_graph.json`, `.agent-history.log`, and an `## Architecture (target)` section in `docs/DESIGN.md` |

The plan it prints before writing lists every one with its fate — created, merged or left alone — so
this table is what to expect, not what to take on trust.

What it keeps:

- **Your hooks** (husky, pre-commit, `.git/hooks`) keep running, after the gate. AgentSmith's own
  `post-checkout` and `post-commit`, which `git init` copies in, are left out: they would vendor
  framework code and CI workflows into your repo.
- **Your CI** is left alone. Two workflows are added: `.github/workflows/agentsmith-gates.yml`, which
  checks out AgentSmith at the release it names and runs the gate over every push, and
  `agentsmith-sync.yml`, which weekly brings the repository up to the framework's latest release and
  opens a pull request. Both check AgentSmith out with the run's own token; if AgentSmith is private
  to you, set the `AGENTSMITH_READ_TOKEN` repository secret (Contents: read). Nothing is vendored
  into the repo.
- **Your agent rules**: an existing rule file — `CLAUDE.md`, `AGENTS.md`, `.cursorrules`,
  `GEMINI.md`, `.github/copilot-instructions.md` — gets AgentSmith's rules appended in a marked
  block, replaced on a re-run. Everything you wrote around the block survives.
- **Your Claude settings**: the gate hooks are added; permissions and everything else stay.
- **Your design doc**: `docs/DESIGN.md` gets an `## Architecture (target)` section — the style your
  code moves towards, not a claim that it already follows it.

It ends by printing the adoption commit, which stages exactly the files it wrote:

```bash
git add -- <the files adopt wrote> && git commit -m "chore: adopt AgentSmith gates" -m "Design: .agent-rfc/designs/adoption.md" -m "Review: n/a: generated scaffold"
```

The gate accepts that review on this commit only — the one that arms the gates — and only while
every file still matches its hash. From the next commit on, a change to gated code, including code
that was there before, needs a design and a review. Earlier history is listed as before adoption,
never failed. `artifacts`, `pillars` and `knowledge_graph` start `off`; turn each on when the repo
is ready for it.

If you use husky, `npm install` points `core.hooksPath` back at `.husky`, which disarms the gates;
re-arm with `git config core.hooksPath .githooks` (your husky hooks still run through the chain).

### Configure GitHub Environments

In the tenant repo: **Settings → Environments**, create `staging` and
`production`, each with:
- Required reviewers (production)
- Environment secrets: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `AGENT_PHOENIX_ENDPOINT`, `AGENT_OWNER_ID`

### Run the reference example app end to end

The example app lives inside the AgenticFramework repo as a reference, but
you should run it as a proper standalone tenant — in its own directory,
outside the framework root, with its own git history and `.env`. This
mirrors exactly how you'd set up any real tenant app.

**Step 1 — Create the tenant project outside the framework root**

```bash
# Run from: anywhere outside AgenticFramework/
mkdir $REPO_DIR/oil-price-demo && cd $REPO_DIR/oil-price-demo
git init -b main    # post-checkout hook fires: installs .agent-rfc/, .cursorrules,
                    # CLAUDE.md, AGENTS.md, GEMINI.md,
                    # .github/copilot-instructions.md, .agents/skills/, CI workflow templates,
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
agentsmith dashboard start    # Phoenix at :6006, Postgres, Ops Portal at :3000
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
drive the the Test section UI-walkthrough's Ops Portal steps without standing up Temporal at all.

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

> **If `trigger_workflow.py` fails with "Workflow execution is already running":**
> a previous run failed mid-flight. Terminate it via the Temporal UI at
> `http://localhost:8233` (Workflows → select the run → Terminate), then re-run.
> See the Troubleshooting section for the CLI alternative.

The `95` outlier in the default price series is deliberate — it's >3 standard
deviations from the rest, which trips the HITL gate. The workflow pauses and
waits for an approval signal for up to 24h. Resolve it from a second terminal:

```bash
# Second terminal — Run from: $REPO_DIR/oil-price-demo
set -a && source .env && set +a
python3 resolve_hitl.py           # approve (default)
python3 resolve_hitl.py --reject  # or reject
```

---

## Configure Features

`scripts/multi_agent_system.py` / `local_agent_stack.py` are the **dev/IDE**
path. Production agent execution uses `runtime/` instead — never deployed
directly from this repo (tenant repos build their own worker image, docs/DESIGN.md › Production Runtime).

### LLM Gateway — models, budget, degrade ladder

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

Ollama endpoint — `OLLAMA_BASE_URL` is optional; the gateway defaults to
`http://localhost:11434` if the variable is unset or unresolved. Set it
only when Ollama is running on a non-default host or port:

```bash
export OLLAMA_BASE_URL="http://localhost:11434"   # default — omit if using the standard port
```

The gateway automatically walks the `degrade_to` chain in `models.yaml`
(e.g. `architect` → `developer` → `validator` → `fast`/Ollama) in two
situations: (1) the tenant's monthly spend breaches the cap, or (2) the
provider itself returns a billing, quota, or rate-limit error (HTTP 400
"credit balance too low", 429, overload). In both cases the chain is walked
until a tier succeeds or all tiers are exhausted — at which point
`complete()` raises `RuntimeError("All model tiers exhausted …")` with the
last error included. If the requested tier is already the free/local tier, a
budget breach never blocks it.

Budget spend is reserved atomically **before** the provider call (an upper
bound from `max_tokens`), then reconciled to the actual cost afterward —
not read-checked-then-written-after, which would let concurrent in-flight
calls for the same tenant all slip past the cap before any of them recorded
spend. If a reservation would exceed the cap, `complete()` raises
`BudgetExceededError` immediately rather than making the provider call.

### Trace redaction (`ENVIRONMENT` profiles)

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
| `production` (also the fallback for unset/unrecognized) | Scrubbed + truncated to 50 chars; full original payload stored in an AES-256-GCM-encrypted blob (`HITL_ENCRYPTION_KEY` / `HITL_ENCRYPTION_KEY_<TENANT>`, where `<TENANT>` is the tenant id upper-cased with every non-alphanumeric character replaced by `_` — `kyc-sentinel` → `HITL_ENCRYPTION_KEY_KYC_SENTINEL`; without a per-tenant key the fleet-wide key is used and that is logged at ERROR), keyed per-span by `{trace_id}.{span_id}.{attr_key}` |

The tenant id used for HITL blob encryption is read from each span's own
`tenant.id` attribute, not bound once when the processor is constructed —
required for correctness on a shared (non-dedicated) worker pool processing
spans for more than one tenant in the same process.

**Retrieving a payload for a compliance request.** The span carries the blob's
reference on `<attr>.hitl_blob_ref`; `HITLBlobStore.get()` decrypts it:

```python
from runtime.trace_redactor import HITLBlobStore
print(HITLBlobStore("kyc-sentinel").get("<trace_id>.<span_id>.input.value"))
```

`None` means no blob was written under that reference — the write failed and
was logged at ERROR. A `RuntimeError` means the stored bytes did not
authenticate: the key has rotated, or the blob belongs to another tenant. The
two are deliberately different answers. Local filesystem backend only; when
`HITL_BLOB_S3_BUCKET` is set, fetch the object and decrypt with the same
derivation rather than letting `get()` report a blob it never looked for.

CI check (also wired into `cd-staging.yml` / `cd-production.yml`):

```bash
ENVIRONMENT=production python3 scripts/verify_system.py --check-redaction
```

### Postgres checkpointer (staging/production LangGraph)

```bash
export ENVIRONMENT=production
export DATABASE_URL="postgresql://..."
```

`scripts/multi_agent_system.py` uses the same `get_environment()` resolver
as "Trace redaction" above and will use a real `PostgresSaver` instead of `MemorySaver`
whenever the resolved environment is `staging`/`production` — **including
an unset or unrecognized `ENVIRONMENT`**, which now resolves to
`production` rather than `development`. It **raises** rather than silently
falling back if `DATABASE_URL` is missing in that case — `MemorySaver`
loses all HITL pause state on crash and is dev-only by design (docs/DESIGN.md › Production Runtime,
docs/DESIGN.md › Framework vs Application Release). Local/IDE runs must set `ENVIRONMENT=development` explicitly to get
`MemorySaver` without a `DATABASE_URL`.

### Reliability & compliance pack (runtime side)

The eval-side suites are the Test section "Reliability & compliance suites". These are the runtime components that
shipped with the same pack — each opt-in, none changes existing callers:

**Pre-call input guardrail (PDPL — `runtime/input_guardrail.py`).**
Scrubs PII from prompts *before* the provider call inside
`llm_gateway.complete()` — decision-path masking, distinct from
`trace_redactor.py`'s post-call observability scrubbing (the Configure Features section "Trace redaction"). Default
patterns: Emirates ID, email, phone, Luhn-valid card numbers.

```bash
export INPUT_GUARDRAIL=default   # off | default | custom
# Unset → off in development, default in staging/production
# (environment resolved by the same fail-closed get_environment() as the two sections above).
```

Tenant-specific vocabularies: `register_input_guardrail(fn)` +
`INPUT_GUARDRAIL=custom`.

**Prompt injection guard (`runtime/prompt_guard.py`).** Runs *before* the
input guardrail inside `complete()` / `complete_stream()`. Heuristics +
denylist. `PROMPT_GUARD=off|warn|default|strict` — **`default` (blocking) is
what ships**, and any unrecognised value falls back to it, so a typo can
never silently disable the guard.

| Mode | Flagged prompt | Use it for |
|---|---|---|
| `off` | reaches the provider, unscanned | never in production; `SEC-PROMPT-001` reports **fail** |
| `warn` | reaches the provider; findings land on `CompletionResult.prompt_guard_reasons` + the span | rolling the guard out against real traffic before enforcing; `SEC-PROMPT-001` reports **warn** (fails `--strict` CI) |
| `default` (alias `block`) | gateway raises `PromptGuardBlockedError` | production default |
| `strict` | `apply_prompt_guard()` itself raises, so direct callers of the module are protected too, not just the gateway | tenants calling `prompt_guard` outside the gateway |

**Rolling out the guard on a noisy corpus:** run `PROMPT_GUARD=warn` for a
period, collect `prompt_guard_reasons` off the results (or the
`llm.gateway.prompt_guard.*` span attributes), tune
`.agent-rfc/security/prompt_denylist.txt` against the false positives, then
promote that tenant to `default`. Before G9 this was impossible — `default`
and `strict` both hard-blocked, so the only way to observe the guard was to
turn it `off`.

**Structured output (`runtime/structured_output.py`).** `parse_llm_json(...)`
validates LLM text against a Pydantic model — prefer this over bare
`json.loads` in tenant activities (`SEC-OUTPUT-001`).

**Tool allowlist (`runtime/tool_registry.py`).** `@tool` registration +
`.agent-rfc/security/tool_allowlist.yaml`; unlisted tools raise
`ToolNotAllowedError` (`SEC-TOOL-001`).

**Output moderation hook (`runtime/moderation.py`).** Pluggable classifier,
`MODERATION_HOOK=optional|required|off`. Two ways to supply it:

1. `register_output_moderator(fn)` at worker startup — imperative, wins over
   any declaration.
2. **Declared** (required for `MODERATION_HOOK=required`) — commit a dotted
   path so both the runtime and the security harness bind to the same
   classifier:

   ```yaml
   # .agenticframework/tenant.yaml
   moderation:
     hook: "agents.moderation:classify_output"   # module.path:callable
   ```

   `MODERATION_HOOK_PATH` overrides it per-deployment. The runtime resolves
   and registers it on first use; `SEC-MOD-001` imports the same path and
   verifies the classifier returns a `ModerationResult` and does not block
   benign text — so the control proves *this tenant has a working
   classifier*, not merely that the framework API exists.

   A declaration that cannot be imported raises `ModerationHookImportError`
   rather than degrading to a skip: silently unmoderated output in a
   regulated tenant is the failure mode worth being loud about.

   Before this (framework G10), `required` failed unconditionally in CI
   because an imperative registration happens in the worker process and is
   invisible to the harness — regulated tenants were told to set exactly
   the value that made their strict CI un-passable.

**LLM self-correction before human DLQ (`runtime/self_correction.py`).**
`BaseAgentWorkflow.run_with_self_correction()` asks the gateway for one
corrected JSON payload on activity failure and retries the same activity
(`max_self_correction_attempts`, default 1) before falling through to
`run_with_recoverable_step`'s human edit-and-resume path (the HITL & DLQ Operations section) — existing
`run_with_recoverable_step` callers are unchanged; tenants opt in per step.

**Memory / RAG substrate (see [docs/rag-memory.md](rag-memory.md)).**
Short-term `runtime/conversation_memory.py` (token-budget truncate-oldest);
long-term `runtime/vector_store.py` + `runtime/embeddings.py`. The gateway
does **not** auto-RAG — the tenant wires `store.query()` results into its
own prompts.

```bash
export EMBEDDER=hash                   # hash (default, no deps) | sentence-transformers
export VECTOR_BACKEND=memory           # memory (default) | postgres (needs pgvector + DATABASE_URL)
```

**TTFT on the streaming path.** `LLMGateway.complete_stream()` records
`ttft_ms` on `CompletionResult` and span attribute `llm.gateway.ttft_ms`;
non-streaming `complete()` is unchanged (total-call latency only). Live
budget gate: the Test section's `verify_ttft.py` / `TTFT_LIVE=required`.

*Provider support:* streaming works for the direct-API providers —
`openai`, `groq`, `ollama`, `anthropic`, `xai`, `google_ai`, and `openrouter`. The cloud-native adapters
(`vertex_ai`, `azure_openai`, `bedrock`, `huawei_modelarts`) have no shared
SSE surface, so `complete_stream()` **falls back to `complete()`** for them
and returns `ttft_ms=None` — a `models.yaml` provider swap degrades the
latency metric, never the call. If you gate on TTFT, assert `ttft_ms is not
None` rather than assuming every route reports it.

**Guardrail evidence on the result.** `CompletionResult.guardrail_counts`
carries the pre-call PII redactions the gateway performed
(`{"emirates_id": 1, "card": 1, ...}`), so a decision-path app can record
*what* was scrubbed without re-running the scrub itself — required evidence
for PDPL/GDPR reviews. `prompt_guard_reasons` carries non-blocking
prompt-guard findings.

**Installing the runtime in a tenant app.** `runtime/` is a pip-installable
package (`agentsmith-runtime`), so a tenant depends on it like any other
library instead of bootstrapping `sys.path`:

```bash
pip install -e /path/to/AgenticFramework                     # local checkout
pip install "agentsmith-runtime @ git+https://github.com/bobbyaqlaar/AgentSmith@v1.0.0"
```

Backends are extras, matching the runtime's own lazy imports — take only
what you use: `[postgres]`, `[redis]`, `[temporal]`, `[hitl]`, `[cloud]`,
or `[all]`. Then `from runtime.llm_gateway import LLMGateway` works from any
directory, and a tenant Dockerfile builds from the tenant repo alone.

For development against a live framework checkout, set `AGENTSMITH_DIR` —
tenant code that follows the `agents/_framework.py` pattern prefers it over
the installed copy, so framework edits take effect without reinstalling.

**Testing your tenant app.** `runtime/testing.py` ships `FakeGateway` and
`RecordingGateway` — use them instead of hand-rolling a double:

```python
from runtime.testing import FakeGateway

gw = FakeGateway(responses={"analyst": '{"rating": "LOW"}'},
                 providers={"analyst": "anthropic"})
result = await gw.complete("...", model_hint="analyst")
assert gw.routes_used() == ["analyst"]
gw.assert_prompt_excludes("784-1985-1234567-1")   # PII never reached the model
```

The double is deliberately no more capable than the real gateway (it won't
stream what the real one can't). A double that over-promises hides exactly
the bugs a test suite exists to find.

**UAE sovereign profile (`templates/uae-sovereign/`).** Pattern A: Falcon 3
on Ollama (`falcon3:3b` / `falcon3:1b`, live-verified); Pattern B:
a sovereign OpenAI-compatible API. Smoke test either:

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434 python3 scripts/verify_sovereign_endpoint.py
```

Residency checklist and `models.yaml` starter in the template; regulatory
narrative in [docs/uae-regulatory.md](uae-regulatory.md).

**Delivery Model soft gate ([docs/delivery-model.md](delivery-model.md)).**

```bash
python3 scripts/verify_system.py --check-delivery-model   # warn-only gate
python3 scripts/delivery_evidence.py                      # writes delivery_evidence.json + .md
```

**Multi-framework security harness ([docs/security-framework-map.md](security-framework-map.md)).**
Unified `SEC-*` registry drives `scripts/run-security-checks.py` (OWASP LLM,
NIST AI RMF, MITRE ATLAS, ISO/IEC 42001). Framework Self-Test and the Python
FastAPI tenant template run with `strict: true`.

```bash
# Smoke (install health) / CI gate / full
python3 scripts/verify_system.py --check-security
MODERATION_HOOK=optional python3 scripts/run-security-checks.py --mode ci --strict
python3 scripts/run-security-checks.py --mode smoke --evidence-pack ./security-evidence

# Adversarial red-team suite (also wired as SEC-ADV-001)
python3 scripts/run-evals.py --suite adversarial
```

Tenant onboarding: `post-checkout` seeds `.agent-rfc/security/` with template
copies of `risk_register.yaml` (schema-gated), `agency_manifest.yaml`,
`nist_profile.yaml` and `tool_allowlist.yaml` — fill them in with real
content (existing files are never overwritten). For regulated content, declare
`moderation.hook` in `tenant.yaml` and set `MODERATION_HOOK=required`; enable
`SSO_REVOCATION_MODE=fail-closed` when missed revocation is worse than a 503.

---

---

## Test

### CLI test pass (every feature, no browser)

Run these from the framework repo root (not your tenant project) to
validate the framework itself; see the [full testing checklist](#full-testing-checklist-same-bar-as-self-testyml)
below for the exact same commands wired into CI.

```bash
# Hooks: opt-in gate + enterprise RFC gate (throwaway repos, no side effects)
python3 scripts/verify_system.py --check-hooks

# Knowledge Graph: rebuild via map_codebase.py and assert non-empty with known nodes (Pillar 2 / P10a)
python3 scripts/verify_system.py --check-kg

# Reliability pack suites (framework seed fixtures). adversarial and rag_poison
# are deterministic — no judge, no credential — so they gate unconditionally.
python3 scripts/run-evals.py --suite fairness
python3 scripts/run-evals.py --suite hallucination
python3 scripts/run-evals.py --suite adversarial
python3 scripts/run-evals.py --suite rag_poison

# Security harness (same bar as Self-Test security job — strict)
MODERATION_HOOK=optional python3 scripts/run-security-checks.py --mode ci --strict
python3 scripts/verify_system.py --check-security

# Delivery Model soft gate (warn-only; the Configure Features section "Reliability & compliance pack")
python3 scripts/verify_system.py --check-delivery-model

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

A passing run here is the same bar CI enforces — see `.github/workflows/self-test.yml`'s `python`, `python-behaviour`, `portal`, `security`, and `widget` jobs.

### Manual test walkthrough: the UIs

Three surfaces, walked through in the order an operator would actually
hit them after a problem report comes in: trace-level detail (Phoenix) →
cross-tenant ops view (Ops Portal) → what the end user sees (In-App
Widget). Assumes the Create an AgentSmith-Governed Repo section's example-app run (Option A or B) already produced at least one real
trace/spend record for `oil-price-demo`, and `agentsmith dashboard start` is
running (Phoenix + Postgres + Ops Portal).

**1. Phoenix — `http://localhost:6006`**

- Open the **Traces** tab for the `default` project. You should see the
  span from the Create an AgentSmith-Governed Repo section's `gw.complete()` call (or the full workflow's three
  spans if you ran Option B), each carrying `tenant.id=oil-price-demo`,
  `llm.model_name`, `llm.gateway.cost_usd`.
- Click into a span → confirm `input.value`/`output.value` are visible in
  `development`/`staging` profiles (or redacted, per the Configure Features section "Trace redaction", if you set
  `ENVIRONMENT=production` for the call).
- **Annotations tab** (only relevant if you ran Option B and a HITL gate
  fired): this is the *other* HITL mechanism — the golden-dataset
  promotion loop (the Human-in-the-Loop (HITL) Self-Improvement section), distinct from the production
  workflow-pause HITL gate you resolved via `hitl_approved` signal above.
  Annotating a span here is what `agentsmith evals`/`sync-ui-feedback.py`
  later promotes into `golden_evals.json`.

**2. Ops Portal — `http://localhost:3000`** (basic auth: `$OPS_PORTAL_USER`/`$OPS_PORTAL_PASSWORD` from `.env`)

- **Apps** (`/ops`) — confirm `oil-price-demo` is listed (auto-registered
  on first trace/spend) with non-zero spend.
- **App detail** (`/ops/apps/oil-price-demo`) — click the app. Confirm:
  - **Spend this month** / **Budget cap** metric cards (cap shows `—` until
    `tenant.yaml`'s `gateway.budget_cap_usd` is synced — see the Deploy via GitHub CI/CD section).
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
    rate badge once there's enough trace volume to compute one.
- **Dead-letter queue** (`/ops/dlq`) — see the dedicated HITL/DLQ walkthrough
  immediately below; this is the newest, most hands-on part of the portal.
- **Audit log** (`/ops/audit`) — confirms every admin action above (if you're
  logged in as admin) is recorded with an HMAC signature.
- **Dev workspace** (`/dev`) — once the app's CI sends its gate record (Connect an app to the
  Dev workspace, below), each commit with its verdict, design and review. Until then it says
  "No data received".

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
  entry and an actual live-workflow resume, run the Create an AgentSmith-Governed Repo section's example-app Option B with the
  `95` outlier, let it park on the HITL gate, then check `/dlq/oil-price-demo`
  while it's waiting — that entry, if you wire up `runtime/replay_webhook_server.py`
  per the HITL & DLQ Operations section, *is* resumable.

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

### Local eval runs

```bash
# Sync HITL annotations from Phoenix, then score against the golden dataset
agentsmith evals

# Same, explicitly, with a fail threshold (what CI actually runs)
python3 scripts/run-evals.py --fail-below 0.80
```

#### When a gate blocks, and when it steps aside

A judge-backed gate can only block on a *quality* signal. Four situations are
infrastructure problems wearing a failing score, and each exits 0 with a
message rather than turning the build red. A fifth looks identical to those
four from the outside — every case errors — and is deliberately the one
exception: it turns the build red, because it is not infrastructure weather.

| Situation | Behaviour |
|---|---|
| The `judge` role needs a credential that isn't set | Skips, naming the exact env var. Requires `--skip-without-judge-credentials`; without it, the run proceeds and the calls fail. |
| The suite has fewer cases than the minimum | Skips — too few cases to mean anything. |
| **Every** case errored — no case got a verdict | `NO VERDICT (judge unreachable)`, printing the provider's error. |
| **Some** cases errored and the rest would pass | `NO VERDICT (graded N/M — a pass needs every case)`. |
| **The configured judge model has been withdrawn by the provider** | **FAILS (exit 1, `::error::`)** — names the model, says no later run will clear it, points at `models.yaml`'s `judge` role and at recalibration. |

That fifth row exists because a withdrawn model does not throw — it 404s — and
reported like an exhausted quota the two are opposite facts: a quota clears
itself overnight, a withdrawn model never clears and the repo is pointing at a
config error. `runtime.provider_dispatch.is_model_gone` classifies it —
phrase-based (`model_not_found`, `does not exist`, `has been deprecated`, …)
rather than a bare status code, for the same reason `is_provider_exhausted`
is: "404" appears in request IDs and token counts, and a 404 only counts here
when the body names the model.

**Errored cases are excluded from the averages.** A call that never returned has
no verdict to average; scoring it 0.00 reports an infrastructure failure as a
quality result. A rate-limited run once read `Overall 0.167` while its
flagged-claim rate — the gate that actually matters — sat at 0.000: five zeros
from calls that never reached a judge, dragging down one case that scored 1.00.
Any partial run prints `Graded: N of M`, so an average never stands unqualified.

**A pass requires every case to grade; a fail does not.** That asymmetry is
deliberate. A green gate is a claim about the whole suite, so anything ungraded
voids it — an earlier quorum of `min_cases` let a 12-case run report PASS on
five graded, which is the overclaiming this rule exists to stop. But a *fail*
stands on whatever graded: applied symmetrically, one flaky call alongside a
real regression would silence the gate exactly when it matters most. Silence on
a green run costs a re-run; silence on a red one ships the regression.

**Per-case markers say whether a case got a verdict, not whether it passed.**
`fail_below` gates the suite average, so an individual case has no pass/fail of
its own — a case under the bar is annotated (`below the 0.95 suite bar`) rather
than crossed out. `adversarial` and `rag_poison` keep ✅/❌ because there each
case is scored against its own expectation.

The env var is resolved from the merged registry, so it follows the `judge`
role wherever a tenant points it — including a role-level `api_key_env`. Never
gate an eval step on `if: secrets.ANTHROPIC_API_KEY != ''`: that hardcodes a
provider, and it ignores a role that declares its own key variable.

#### Budgeting judge calls against a provider cap

Count the calls before wiring the gates: one per case, per judged suite, per
run. A tenant with golden 12 + fairness 4 + hallucination 6 spends **22** judge
calls on every run that fires all three.

That number has to fit the judge account's cap, and the two kinds of cap fail
identically from the outside:

| Cap | Symptom | Remedy |
|---|---|---|
| Per-minute | A burst exhausts `cost_router`'s 4-attempt 429 retry partway through | `EVAL_RPM` — pace the calls |
| Per-day | 429 arrives even at a low observed rate; the provider's message names a total | Fewer judged calls per run, or a paid tier. **Pacing cannot help.** |

Read the provider's error rather than guessing: Gemini's free tier reports
`generate_content_free_tier_requests, limit: 20`, and that is per day. A run
pacing at ~3 requests/minute still hit it.

When the total does not fit, split the suites across triggers rather than
deleting cases or lowering a threshold — no gate is removed, each simply runs
less often:

```yaml
on:
  push: { branches: [main] }
  schedule:
    - cron: "30 8 * * 1,3,5"   # fairness
    - cron: "30 8 * * 2,4"     # hallucination

# then, per step:
#   golden:        if: github.event_name != 'schedule'
#   fairness:      if: github.event.schedule == '30 8 * * 1,3,5'
#   hallucination: if: github.event.schedule == '30 8 * * 2,4'
```

`github.event.schedule` is the cron that fired, so one workflow carries several
schedules without a second file duplicating checkout and install. Alternate the
scheduled suites rather than running them together, so the heaviest day — a push
plus the largest cron — still fits. Schedule them just after the cap resets so
they draw on a fresh allowance.

Two consequences worth stating to whoever owns the repo: a manual
`workflow_dispatch` must run **one** suite (give it a `choice` input), or it
rebuilds the oversized run you just split up; and at N calls per push-triggered
suite, the cap sets how many graded pushes a day the account affords.

**Treat the split as temporary, and prefer a judge whose quota fits.** Splitting
buys correctness at the price of latency: a suite on an alternating cron reports
up to two days after the commit that broke it, and a gate that reports two days
late is a weaker gate — long enough for the offending change to be built on. It
is the right move against a cap you cannot change today, and the wrong permanent
shape.

Moving the judge is usually cheaper than living with the split. The cost is one
recalibration run, because a threshold is only meaningful against the grader it
was measured on — and a grader with room to run the suite several times gives
you something the constrained one could not: a variance measurement, which is
what tells you whether a threshold has real headroom or is one noisy verdict
from a false failure.

**When the OLD provider retires the model you're moving away from** — mark it
in `models.yaml`'s `catalog:`, don't delete it:

```yaml
llama-3.3-70b-versatile:
  provider: groq
  decommissioned: true   # HTTP 404 model_not_found on every call as of 2026-08-17
  cost_per_input_token: 0.00000059
  cost_per_output_token: 0.00000079
```

The catalog is an offer to any tenant that wants an entry — deleting it just
means the next person shopping for a cheap model doesn't see it; leaving it
unmarked, with live-looking cost figures, means they see it and pick it.
`runtime/test/test_no_role_binds_a_dead_model.py` fails if any profile's `use`
still names a `decommissioned: true` entry — `degrade_to` is exempt, since it
names a role, not a model.

#### Why the judge never falls back to another model

There are two provider-calling paths, and they behave differently on purpose:

| | Workload path | Eval path |
|---|---|---|
| Module | `runtime/llm_gateway.py` | `scripts/cost_router.py` |
| Callers | workers, activities, tenant agents | `eval_judge.py` only |
| On provider exhaustion | walks the `degrade_to` chain | **fails — no fallback** |
| Budget, prompt guard, moderation, redaction | yes | no |

Both classify exhaustion identically (`provider_dispatch.is_provider_exhausted`);
they differ only in what they do about it.

A degraded *actor* produces worse output that a good judge still catches. A
degraded *judge* writes confident verdicts into the same `score` field, against
the same threshold, gating the same merges, and nothing downstream can tell.
Scores are only comparable against the grader they were calibrated for. So the
eval path reports exhaustion rather than substituting a model, and the gate
skips with a cause.

Three guards back this. Every result row carries `judged_by`, and a scorecard
whose verdicts came from more than one model **fails** rather than averaging
them. Every row also carries `criteria_digest` — a hash of the rubric text
actually sent to the judge (docs/DESIGN.md › Evaluation Framework) — and a scorecard graded under more
than one rubric fails the same way: a threshold is calibrated against one
grader reading one set of instructions, and the rubric mutates on its own as
`promote-learning.py` appends production failures to it.
`scripts/test/test_exhaustion_classification.py` asserts `cost_router`
never references `degrade_to`, so adding a fallback there fails a test that
explains why before it silently changes what every stored score means.

A `degrade_to` on a `judge` role is therefore inert. Do not add one expecting a
fallback — KYC Sentinel's `models.yaml` carries a worked example of why.

Provider errors are surfaced with the response body (truncated), not just the
status line. This matters more than it sounds: a bare `HTTP 400` is
indistinguishable between a malformed request, a dead model id, and an account
out of credits — all three were guessed at before the body was printed, and the
answer turned out to be the third.

### Reliability & compliance suites (fairness, hallucination, TTFT)

Same
`run-evals.py` entry point as the golden suite — different fixtures,
different thresholds, separate CI workflows:

```bash
# Fairness — paired protected-attribute cases + pair parity.
# Thresholds: FAIRNESS_FAIL_BELOW (default 0.80) gates rationale QUALITY and is
# calibrated per judge; CLI --fail-below overrides it. FAIRNESS_PARITY_FAIL_BELOW
# (default 1.0) gates the WORST protected-attribute pair and is deliberately not
# the same knob — a judge swap that loosens the quality bar must not loosen the
# bias control with it. FAIRNESS_SCORE_SPREAD_FAIL_ABOVE (default 0.25) is a
# third, narrower bar: pair_parity only compares the `fairness` flag, so two
# pair members graded on BYTE-IDENTICAL output can still diverge in overall
# score — observed live, 1.00 vs 0.33 on the same text, with parity reporting
# 1.000 throughout. Gated only where both members share an output hash; where
# the outputs differ, a score gap is a quality signal and belongs to the bar
# above, not this one.
python3 scripts/run-evals.py --suite fairness

# Hallucination — dedicated judge dimension (0.0–1.0, flagged at ≥ 0.5).
# TWO failure modes, measured separately:
#   Hallucination:  false-positive rate — clean cases the judge flagged. Hard
#                   fail above HALLUCINATION_FAIL_ABOVE (default 0.05).
#   Detection miss: planted cases the judge FAILED to flag. Any miss fails.
#
# Each reports THREE states, not two, because "all clean" and "never measured"
# must not print alike:
#   0.000                 measured, nothing wrong
#   NOT MEASURED          no clean case got a verdict — ceiling not checked
#   NOT GRADED            a positive control exists but errored
#   n/a — no positive control in this suite
python3 scripts/run-evals.py --suite hallucination

# TTFT — live Ollama smoke: streams a tiny prompt (default model falcon3:1b)
# against OLLAMA_BASE_URL and fails when ttft_ms > TTFT_FAIL_ABOVE_MS (default 2000).
# Exit codes: 0 within budget · 1 over budget · 2 Ollama unreachable/no first token.
python3 scripts/verify_ttft.py
```

**Two case fields worth knowing, both optional:**

`retrieved_context` — the documents the agent was given, as a string, a list of
strings, or a list of `{id, text}`. Supply it whenever a case's rationale cites
a source. A grounding judge without the source cannot tell an accurate
paraphrase of a retrieved document from an invented one, and a strict judge
flags both: KYC Sentinel's agent wrote `[policy-005] (rubric: incomplete source
of funds → MEDIUM)`, which is verbatim what policy-005 says, and was scored
hallucination=0.50 because the judge had never been shown policy-005.

`expect_hallucination: true` — marks a POSITIVE CONTROL, a case whose output
deliberately contains a defect. Such a case is excluded from the flagged-claim
rate (being flagged is the correct outcome) and counted by the detection-miss
rate instead. Without one, a suite measures false positives and nothing else —
it can report a perfect flagged rate while being unable to detect a
hallucination at all, and "detected everything" is then indistinguishable from
"was never asked to detect anything". `run-evals.py` prints `Detection miss:
n/a — no positive control in this suite` rather than a reassuring 0.000.

A positive control cannot be pinned from the pipeline — its output must contain
a defect the pipeline correctly never produces — so exempt it from any
regenerate-the-fixtures tooling, or the next run will overwrite the planted
defect with clean output and leave a control that passes and tests nothing.

**Judge temperature** is pinned at 0 (`scripts/eval_judge.py: JUDGE_TEMPERATURE`).
The router default of 0.2 is right for an actor and wrong for its grader:
sampling noise in the judge is indistinguishable from a quality change in the
thing being judged, and it lands directly on the threshold.

**Fixtures:** tenant-local `.agent-rfc/fixtures/fairness_evals.json` /
`hallucination_evals.json` (+ matching `*_judge_criteria.json`). Seed
copies live in the framework's `fixtures/*_base.json` — copy them into the
tenant repo's `.agent-rfc/fixtures/` and extend with domain-specific cases.
When no tenant file exists, `run-evals.py` falls back to the framework base
seeds (framework checkout only — a vendored tenant copy without fixtures
skips gracefully).

**CI wiring:** every `ci-<stack>.yml` calls these as reusable workflows —
`eval-fairness.yml` (warn-only unless repo variable `FAIRNESS_EVALS=required`),
`eval-hallucination.yml` (hard-fail gate), `eval-ttft-live.yml` (no-ops
unless repo variable `TTFT_LIVE=required`, since generic CI runners have no
Ollama). All three are copied into tenant repos by `post-checkout` /
`agentsmith tenant init` alongside `eval-scorecard.yml` — a missing callee makes
GitHub reject the whole CI workflow as invalid.

**Tenant `.env` knobs (reliability pack):**

```bash
FAIRNESS_FAIL_BELOW=0.80              # rationale quality only (calibrated per judge)
FAIRNESS_PARITY_FAIL_BELOW=1.0        # worst protected-attribute pair; do not lower to fix a noisy grader
FAIRNESS_SCORE_SPREAD_FAIL_ABOVE=0.25 # same-text pair only — see the fairness suite comment above
HALLUCINATION_FAIL_ABOVE=0.05         # max tolerated flagged-case rate
TTFT_FAIL_ABOVE_MS=2000           # live TTFT budget (verify_ttft.py)
```

### Full testing checklist (same bar as `self-test.yml`)

Minimal real validation for each subsystem (no mocks):

```bash
# Framework scripts + shell
find scripts runtime examples -name "*.py" -print0 | xargs -0 -n1 python3 -m py_compile
bash -n install-ai-stack.sh && zsh -n install-ai-stack.sh

# Lint and types. Both are CI gates and neither was one until 2026-08-26 —
# ruff had no config and ran nowhere, so it enforced its defaults only when a
# human happened to invoke it. Run them FIRST: they are the cheapest gates and
# the only ones that fail on a keystroke rather than on a behaviour.
ruff check .
mypy                                       # scope is pinned in pyproject.toml

# Knowledge Graph rebuild + non-empty assertion (Pillar 2 / P10a — wired into self-test.yml)
python3 scripts/verify_system.py --check-kg

# Ops Portal (includes a cross-tenant isolation regression suite — see docs/DESIGN.md › Federated Observability)
cd portal && npx tsc --noEmit && npm test && npm run build

# In-App Widget (includes an XSS-attribute-injection regression test)
cd templates/in-app-widget && npm install && npm test

# Redaction (needs ENVIRONMENT set; staging/production exercise real scrubbing)
ENVIRONMENT=staging python3 scripts/verify_system.py --check-redaction
ENVIRONMENT=production python3 scripts/verify_system.py --check-redaction

# Reliability pack (the Configure Features section, the Test section) — eval suites, input guardrail unit tests, TTFT
python3 scripts/run-evals.py --suite fairness
python3 scripts/run-evals.py --suite hallucination
python3 scripts/run-evals.py --suite adversarial
pytest runtime/test/test_input_guardrail.py runtime/test/test_ttft_stream.py \
       runtime/test/test_self_correction.py runtime/test/test_memory_and_vector.py \
       runtime/test/test_prompt_guard.py runtime/test/test_structured_output.py \
       runtime/test/test_tool_registry.py runtime/test/test_moderation.py -q
python3 scripts/verify_ttft.py            # needs a local Ollama with falcon3:1b pulled

# Security harness (P12 — Self-Test security job, strict)
MODERATION_HOOK=optional python3 scripts/run-security-checks.py --mode ci --strict
PYTHONPATH=scripts:. pytest scripts/test/test_security_*.py -q
python3 scripts/verify_system.py --check-security

# Hook bundle signing (needs a real GPG key; see the Enterprise Pack section)
gpg --verify agenticframework-hooks-<version>.tar.gz.sig agenticframework-hooks-<version>.tar.gz

# On-prem deployment template (the Deploy via GitHub CI/CD section) — compose/proxy/Helm syntax, no live cluster needed
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

For `run_with_recoverable_step` (the HITL & DLQ Operations section) specifically — the workflow-side
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
# see the pattern in docs/PRODUCT_ARCHIVE.md's HITL/DLQ redesign section for
# a worked example (CRM-style hallucinated-field-name failure -> parked
# workflow -> human_fix_payload signal -> resumed with the correction).
```

---

---

## Deploy via GitHub CI/CD

> ⏸️ **GCP promotion is SUSPENDED as of 2026-08-12, until further notice.**
> The automatic `push:` trigger is commented out in `cd-portal.yml` (framework)
> and `cd-staging.yml` (KYC Sentinel). **Everything in this section is retained
> and still correct** — it is the runbook for when promotion resumes, and
> resuming is uncommenting four lines in each workflow.
>
> What still works meanwhile: `workflow_dispatch` is deliberately left enabled,
> so a deliberate deploy is one click. What stops: nothing is promoted merely
> because a commit landed on `main`.
>
> Nothing already deployed was torn down. The Cloud Run services and jobs stay
> up serving whatever was last promoted — they simply stop being replaced, so
> treat what is live as a **snapshot** rather than as head of `main`.

### Deploy pipeline and GCP checklist

**Through GitHub CI/CD (cloud):**

```bash
# Scaffold a tenant repo with CI/CD wired in (the Create an AgentSmith-Governed Repo section) — or, for the example,
# this is already done: examples/oil-price-agent/.agenticframework/tenant.yaml
cd my-project
agentsmith tenant init my-tenant --stack python-fastapi   # or ts-react | go
git add .github .agenticframework && git commit -m "chore: scaffold tenant CI/CD"
git push -u origin main

# Configure once in GitHub: Settings → Environments → create "staging" and
# "production", each with required reviewers + environment-scoped secrets
# (DEPLOY_COMMAND, ANTHROPIC_API_KEY/OPENAI_API_KEY, OPS_PORTAL_* if syncing).
```

Then the pipeline runs itself on the branch flow already wired by `agentsmith tenant init`:

| You do | Workflow that fires | Gate |
|---|---|---|
| Push a feature branch / open a PR | `ci-<stack>.yml` | lint, format check, test, eval scorecard (warn-only) |
| Merge to `develop` | `cd-staging.yml` | optional GHCR image build → eval fail-gate at 0.75 + post-deploy smoke test |
| `agentsmith tenant promote my-tenant --from staging --to production` | Opens a `develop → main` PR | re-verifies the staging eval gate before opening it; **exact tenant-id match required** — refuses if `.agenticframework/tenant.yaml`'s id doesn't match exactly |
| PR reviewed + merged to `main` | `cd-production.yml` | optional GHCR image build → eval fail-gate at 0.80 + smoke test; **blocks + runs `rollback-notify` on smoke failure** (no automatic rollback execution — see "Wire your platform" below) |

`cd-staging.yml`/`cd-production.yml`'s deploy step is
`.github/actions/deploy-placeholder` — set the `DEPLOY_COMMAND` secret on
the tenant's GitHub Environment to wire in your platform; unset, it no-ops
and prints platform-specific guidance (Fly/Railway/ECS/GCP Run). See "Wire
your platform" below for the exact commands and the GHCR image-build step that runs before it.

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

> **Tenant-specific, not shipped.** `cd-demo-ui.yml` and `demo/` are not
> framework templates — `agentsmith tenant init` never writes them. They exist in the
> oil-price-demo tenant and are described here as a worked example of adding a
> second deployable to a tenant's CD. Skip this workflow if your tenant has no
> separate UI. The workflow templates the framework does provide are listed in
> the Create an AgentSmith-Governed Repo section "CI/CD workflows written per stack".

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
HITL approval → display the result after you click **Approve**. See "Worked example: a tenant demo UI" below for the full
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
agentsmith tenant onprem-scaffold     # writes deploy/onprem/
cp deploy/onprem/.env.example deploy/onprem/.env
# edit .env: APP_IMAGE_PROD (build your own, or point at the GHCR image
# cd-production.yml pushed), PROXY_ENGINE=traefik|envoy
deploy/onprem/scripts/up.sh
```

See "On-premise / air-gapped deployment" below for canary/shadow traffic routing, Kubernetes/Helm for
high-compliance customers, and air-gapped image bundling.

---

### Deploying to a server that is not your dev machine

Everything above assumes you are standing where the repo is. A real deployment
is not: the artifacts are built on one machine and run on another. This section
is the host-by-host version.

#### What the server actually needs

Less than you would guess — and knowing exactly what decides your Windows story:

| Requirement | When it is needed |
|---|---|
| **Docker Engine + Compose v2** | Always. `docker compose version` must report v2.x — the old `docker-compose` v1 binary will not read these files. |
| **bash + python3** | **Only if you run `scripts/up.sh` on the server.** It renders the proxy config from `.env` before bringing the stack up. |
| Nothing else | No framework install, no Python packages, no Node. The app ships as an image. |

That second row is the whole trick. `up.sh` exists to render
`proxy/traefik/dynamic.rendered.yml` (or `proxy/envoy/envoy.rendered.yaml`) from
your `.env`, and those rendered files are **gitignored** — so a fresh clone on
the server has neither them nor `.env`, and a bare `docker compose up` fails on
a missing mount source. Render them on a machine that has bash and python3, copy
them across, and the server needs Docker and nothing more.

#### Step 1 — get the artifacts onto the server (pick one)

```bash
# a) The server can reach your git host — simplest
git clone <your-tenant-repo> /opt/kyc-sentinel
cd /opt/kyc-sentinel/deploy/onprem

# b) No git on the server — copy the scaffolded directory
agentsmith tenant onprem-scaffold                      # on your dev machine
scp -r deploy/onprem you@server:/opt/app/

# c) Air-gapped — no registry reachable from the server either
scripts/bundle-airgapped.sh                    # dev machine, with internet
scp onprem-bundle.tar.gz you@server:/opt/app/
ssh you@server 'cd /opt/app && scripts/load-airgapped.sh'
```

#### Step 2 — configure, and decide where you render

```bash
cp .env.example .env
# Set at minimum: APP_IMAGE_PROD, APP_PORT, PROXY_ENGINE, PROXY_LISTEN_PORT.
# WITH_DB=true adds pgvector; leave it false if you already have Postgres.
```

`APP_IMAGE_PROD` must be a ref the **server** can pull — the CD workflow's
`ghcr.io/<org>/<repo>:<sha>`, your own registry, or an image loaded from the
air-gapped bundle. A tag that only exists in your laptop's Docker will fail on
the server with a pull error that reads like a network problem.

---

#### Linux server — the normal target

Install **Docker Engine**, not Docker Desktop: Desktop is a developer product,
and on a headless server it brings a VM and a licence you do not want.

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"     # log out and back in for this to take
docker compose version              # must print v2.x

cd /opt/app/onprem
cp .env.example .env && ${EDITOR:-vi} .env
scripts/up.sh                       # bash + python3 are already here
```

Survive a reboot — compose's `restart: unless-stopped` covers crashes but not
the machine coming back up:

```bash
sudo tee /etc/systemd/system/agentsmith-stack.service >/dev/null <<'UNIT'
[Unit]
Description=AgentSmith on-prem stack
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/app/onprem
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=youruser

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl enable --now agentsmith-stack
```

Use `ExecStart=docker compose up -d`, not `up.sh`, in the unit: at boot you want
the last known-good rendered config brought up, not a re-render against an
`.env` nobody has reviewed since.

---

#### macOS server

Works, with one caveat worth saying out loud: **macOS is a developer host
pretending to be a server.** No unattended reboot story without a logged-in
session, and Docker Desktop needs a paid licence for larger organisations. Use
it for a demo box or a small internal deployment, not for a production tenant.

```bash
brew install --cask docker        # Docker Desktop, then launch it once
#   or, headless and licence-free:
brew install colima docker docker-compose
colima start --cpu 4 --memory 8

cd /opt/app/onprem
cp .env.example .env && ${EDITOR:-nano} .env
scripts/up.sh                     # macOS ships bash 3.2 — up.sh is compatible
```

For restart-on-boot use a LaunchDaemon, and note it only fires once someone
logs in unless the Mac is configured for auto-login — which is its own security
conversation.

---

#### Windows server

Two routes. The first is better if you can have it.

**Route A — WSL2 (recommended).** You get a real Linux userland, so everything
in the Linux section applies verbatim, including `up.sh`.

```powershell
wsl --install -d Ubuntu           # then reboot
# Install Docker Desktop, enable Settings → Resources → WSL Integration
```

```bash
# inside the WSL2 shell — this is now just the Linux path
cd /opt/app/onprem && cp .env.example .env && scripts/up.sh
```

> ⚠️ **Keep the deployment directory inside the WSL2 filesystem** (`/opt/...`,
> `~/...`), not on `/mnt/c/...`. Bind-mounting across the Windows boundary is
> slow, and file permissions arrive wrong in a way that surfaces much later as a
> container that cannot read its own config.

**Route B — Docker only, no WSL2, PowerShell.** For a locked-down host where
you cannot install a Linux distro. Render on your dev machine, ship the result,
and the server never needs bash or python3.

```bash
# on your dev machine (Mac or Linux)
cd deploy/onprem
cp .env.example .env && $EDITOR .env
python3 scripts/render-traefik-config.py     # or render-envoy-config.py
```

```powershell
# copy the whole directory INCLUDING .env and proxy/**/*.rendered.* — the
# rendered files are gitignored, so a git clone on the server will not have them
scp -r deploy/onprem Administrator@server:C:/app/onprem

cd C:\app\onprem
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
docker compose ps
```

> ⚠️ **Line endings.** If the directory reaches the server through anything that
> translates CRLF — a Windows git checkout with `core.autocrlf=true`, some SCP
> clients — the shell scripts and the rendered YAML acquire `\r`, and the
> failure is baffling: `bash\r: no such file or directory`, or a proxy that
> starts and routes nothing. Set `git config --global core.autocrlf input` on
> the server, or copy as a `.tar` and unpack there.

Restart-on-boot: set Docker Desktop to start on login, and rely on compose's
`restart: unless-stopped`. For a genuine unattended Windows server, run the
stack under WSL2 (Route A) with a systemd unit — Route B has no good headless
restart story, and pretending otherwise is how a "deployed" service is found
down after a patch Tuesday.

---

#### Verify, on any host

```bash
docker compose ps                                   # every service Up/healthy
curl -fsS http://localhost:${PROXY_LISTEN_PORT:-80}/healthz && echo OK
docker compose logs --tail=50 proxy                 # routing actually loaded
```

Only `proxy` publishes a port — `${PROXY_LISTEN_PORT:-80}:80`. The app
containers are deliberately unpublished and reachable only through it, so if
`curl` against the app port directly fails, that is the design working.

#### Updating a deployed server

```bash
# .env only (image tag, canary weight): re-render, reconcile
scripts/up.sh                     # or on a Docker-only host: re-copy the
                                  # rendered file, then `docker compose up -d`
# new image, same config:
docker compose pull && docker compose up -d
```

Both are safe to re-run; compose reconciles rather than recreating what has not
changed.

### Promote staging → production (`agentsmith tenant promote`)

```bash
agentsmith tenant promote acme --from staging --to production
```

This verifies the staging eval gate (`run-evals.py --fail-below 0.75`) and,
only if it passes, opens a `develop → main` PR via `gh pr create` — it never
pushes directly to `main`.

### Wire your platform (CD deploy + rollback)

Before the deploy step, both CD workflows run
`.github/actions/build-push-ghcr`: if a `Dockerfile` exists at the repo
root, it builds and pushes `ghcr.io/<org>/<repo>:<sha>` using the
workflow's own `GITHUB_TOKEN` (no extra registry secret) and exports the
image ref as `$IMAGE_REF` for the deploy step below to consume — e.g.
`DEPLOY_COMMAND = "gcloud run deploy myapp-staging --image $IMAGE_REF"`.
No Dockerfile present → this step skips cleanly (exit 0, no CD failure),
same "optional infra never fails CD" posture as the Ops Portal history
sync. This is also the artifact `templates/onprem-deploy/` (below)
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
failure). The notification names the commit that failed — the job's checked-out
`HEAD`, which is the commit CI validated — and `ROLLBACK_COMMAND` can read it as
`$ROLLBACK_NOTIFY_COMMIT`:

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

### GCP deployment specifics (Vertex AI credentials + worker hosting)

"Wire your platform" above covers `DEPLOY_COMMAND` generically, with `gcloud run deploy` as
one example value — that's enough if your tenant app stays on the local-only
framework defaults or only talks to direct Anthropic/OpenAI APIs. If it routes
any `model_hint` to `provider: vertex_ai` (the `vertex_gemini` role, shipped
commented-out in `runtime/models.yaml` — uncomment it there or declare it in
your tenant `models.yaml`), CI/CD needs two more things `DEPLOY_COMMAND` alone
doesn't give you: a way for GitHub Actions to authenticate to GCP, and a
decision about *what kind* of compute actually runs `worker.py`.

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

**One-time WIF setup:** identical to the step-by-step checklist in the Deploy via GitHub CI/CD section
above (pool + provider + `github-deployer` SA + repo binding) — do it once
per GCP project there; don't repeat it here.

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
| **GKE (or any k8s)** | Best fit for a long-running poller — a `Deployment` with no `Service`/ingress needed at all, scales on whatever metric you choose (queue depth via KEDA, etc.) | More infra to operate — bring your own cluster; not scaffolded by `agentsmith tenant onprem-scaffold` |
| **Compute Engine (single VM/MIG)** | Simplest mental model, no container platform needed | Manual scaling, no rolling-deploy story beyond replacing the VM/instance template yourself |

Set `DEPLOY_COMMAND` on each GitHub Environment to whichever platform you
choose. The `gcp-auth` step runs first so `gcloud`/`kubectl` is already
authenticated when `DEPLOY_COMMAND` executes:

```bash
# Cloud Run (worker.py already has /healthz — see above):
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
`runtime/models.yaml` (docs/DESIGN.md › LLM Gateway (Production) "Cloud-Native Provider Adapters").

**Live-verification status**: the Vertex AI *call path* was verified
live against a real GCP project (`gemini-2.5-flash` via
`LLMGateway.complete(model_hint="vertex_gemini")` — docs/DESIGN.md › LLM Gateway (Production)). The
`gcp-auth` composite action is **fully verified end-to-end** through
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

### Cloud SQL Auth Proxy for the portal database (Cloud Run)

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

### Worked example: a tenant demo UI on Cloud Run (Streamlit)

> **Tenant-specific:** the `demo/` directory and `cd-demo-ui.yml` exist in the
> `bobbyaqlaar/oil-price-demo` tenant repo only — they are not part of the
> framework or of `examples/oil-price-agent/`, and are not scaffolded by
> `agentsmith tenant init`. Treat this subsection as a worked example of adding your
> own UI layer to a tenant repo.

The `demo/` directory in the oil-price-demo tenant repo contains a Streamlit app (`demo/app.py`) that
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
| `TEMPORAL_TLS` | `` (empty) | Enables TLS to the Temporal server. Accepts `1`, `true`, `yes` or `on` (case-insensitive); anything else leaves TLS **off**. Read by `runtime/temporal_client.connect`, which every worker and client script now uses — previously only the example scripts read it, and they compared against `"true"`, so the `"1"` documented here silently disabled TLS. |
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
   identical to what `resolve_hitl.py` does from the CLI
5. The workflow completes; the result (prediction, confidence, anomaly flag) is
   displayed in the run history table

**Spike preset:** uses series `[70.0, 70.1, 69.9, 70.0, 70.1, 70.0, 70.2, 69.8, 70.1, 70.0, 110.0]`
(10 stable values ~70 then spike to 110). This definitively exceeds the 3σ anomaly threshold
because the stable prefix keeps mean and σ tight — a short series with the outlier included
inflates σ and can mask the spike.

**Prerequisites:** the `staging` GitHub Environment carries `GCP_WORKLOAD_IDENTITY_PROVIDER`,
`GCP_SERVICE_ACCOUNT` and `GCP_PROJECT_ID` before the CD workflow can deploy. See "GCP deployment specifics" above for the WIF setup.

---

### Dedicated isolation tier (own worker pool)

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
[runtime/k8s/dedicated-tenant/README.md](../runtime/k8s/dedicated-tenant/README.md).

---

### On-premise / air-gapped deployment

For tenants whose customers run the agent app on their own hardware
instead of a managed cloud platform — opt-in, never auto-written the way
the CI/CD workflow templates are:

```bash
agentsmith tenant onprem-scaffold   # run inside the tenant repo — writes deploy/onprem/
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
vars only (never a cloud secret manager — see the secrets note below),
and logs JSON-Lines to stdout (already `scripts/agent_logger.py`'s
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

**Mirroring vs. shadow-eval — these are two different things, don't
conflate them:** this section's shadow *traffic* mirroring tests a new version of
the whole app against live request shape before promotion, at the
proxy/infrastructure layer — it has no idea what your app does with a
mirrored request. The framework's separate shadow-eval sampler
(`scripts/shadow-eval.py`, docs/DESIGN.md › Evaluation Framework) does *application-level*,
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

---

## Monitor in Production

### Operating surfaces at a glance

| Surface | What it shows | Where |
|---|---|---|
| **Phoenix** | This tenant's traces, evals, HITL annotation queue | `http://localhost:6006` (or your team server) |
| **Ops Portal** | Cross-tenant cost/spend + cap, real run status (incl. **Working**/in-progress), Phoenix error rate, per-tenant DLQ triage (edit/Replay/Discard), shadow-eval suggested promotions, signed audit log | `https://ops.example.com` (below) |
| **Demo UI (Streamlit)** | GUI for submitting oil-price workflows, viewing status, approving/rejecting HITL, seeing results — connects to the live Temporal server | Cloud Run: get URL via `gcloud run services describe YOUR_UI_SERVICE --region YOUR_REGION --project YOUR_GCP_PROJECT_ID --format="value(status.url)"` |
| **`.agent-history.log`** | Local append-only event log this tenant repo produces | `agentsmith check` surfaces unresolved entries from it |
| **In-App Widget** | End-user-facing status badge (own tenant only, token-scoped) | embedded in the tenant's own app (below) |
| **GitHub Actions** | CI/CD run history, eval scorecard artifacts per run | the tenant repo's Actions tab |

**Demo UI quick-test after deploy:**
1. Open the `YOUR_UI_SERVICE` Cloud Run URL
2. Sidebar → pick **HITL — price spike** preset → click **Start Workflow**
3. Status refreshes automatically — workflow pauses at HITL gate
4. Click **Approve** → workflow completes → result (prediction, confidence, anomaly=True) appears in run history

**CLI alternative (no UI):** `resolve_hitl.py` at the root of the oil-price-demo
repo does the same HITL signal from the terminal — useful for scripting or when
the UI isn't deployed yet. It is copied from
`$AGENTSMITH_DIR/examples/oil-price-agent/resolve_hitl.py` to the repo root and
run as `python3 resolve_hitl.py`; there is no `scripts/resolve_hitl.py`.

Day-to-day operational tasks (rotating tokens/keys, checking unresolved
issues, upgrading the framework version) are in [Maintain (Day-2 Operations)](#maintain-day-2-operations).

---

### Ops Portal

One portal with three areas: **Dev** (`/dev`, each app's commits as its CI gate judged them),
**Ops** (`/ops`, cost, issues, runs, dead-letter queue, audit log) and **Administration**
(`/admin`, apps and their CI tokens). Full detail: [portal/README.md](../portal/README.md).

#### Ops Portal setup

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

**Tracing (optional):** point the portal at the same collector the workers use
and its request handling, every Postgres query and every outbound Phoenix call
join the worker's trace instead of starting a new one:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:6006/v1/traces"   # or a base URL — both work
```

Unset, nothing is registered and the portal behaves exactly as it did before it
was instrumented. Set, the `traceparent` the worker already sends on
`POST /api/runs/ingest` makes the portal's spans **children** of the LLM call
that triggered them — so "the run took 9s" can be read down to which query or
which Phoenix timeout. Set `ENVIRONMENT` and `AGENT_PROJECT_NAME` the same way
you set them on the worker, or the two sides will label the same deployment
differently.

Portal spans carry `tenant.id`, `portal.actor.role` (the RBAC role of the human
who acted, blank for machine-to-machine calls), and parameterised SQL. They do
**not** carry request bodies, bound query values or replayed payloads:
`runtime/trace_redactor.py` scrubs the worker's spans, and nothing stands
between a portal span and the collector.

**Users and roles (optional):** set `OPS_PORTAL_USERS` instead of the single
`OPS_PORTAL_USER`/`PASSWORD` pair. Each user holds one or more **grants** — a role and the apps
it covers:

```bash
OPS_PORTAL_USERS='[
  {"username":"alice","password":"...","grants":[{"role":"administrator","apps":"*"}]},
  {"username":"bob","password":"...","grants":[
    {"role":"developer","apps":["acme"]},
    {"role":"design_approver","apps":["acme"]}]},
  {"username":"carol","password":"...","grants":[{"role":"operator","apps":["acme","globex"]}]}
]'
```

For SSO, set `OPS_PORTAL_SSO_USERS` the same way, keyed by email:

```bash
OPS_PORTAL_SSO_USERS='[{"email":"alice@corp.com","grants":[{"role":"administrator","apps":"*"}]}]'
```

Roles: `developer`, `design_approver`, `operator`, `hitl_reviewer`, `release_approver`,
`administrator` and `super_user`; what each may do is in docs/DESIGN.md › Federated
Observability "Role-Based Access Control". `administrator` and `super_user` must cover `"*"`.
An authenticated SSO identity not listed gets no access at all. Entries in the earlier
`{"role":"viewer|operator|admin","tenants":…}` form keep working with exactly the access they
had.

#### Wire tenant history sync

In each tenant's CD workflow (or a local `agentsmith check` run):

```bash
curl -X POST https://ops.example.com/api/sync/history \
  -H "Authorization: Bearer $OPS_PORTAL_SYNC_TOKEN" -H "Content-Type: application/json" \
  -d '{"tenantId":"acme","entries":[{"entryId":"...","level":"CRITICAL","event":"...","timestamp":"...","raw":{}}]}'
```

A tenant auto-registers on its first sync — no separate provisioning step.

#### Connect an app to the Dev workspace

The Dev workspace (`/dev`) shows what each app's process gate decided about every commit: its
design, pillars, deviations and approvals, review passes, and failures with their repairs. It
reads only what the app's CI sends; nothing is fetched from the repository.

1. **Register the app** under Administration › Apps (`/admin/apps`) with its repository URL and
   provider. An Administrator does this.
2. **Issue its ingest token** on the app's page. The token is shown once. Set two secrets in the
   app's repository: `AGENTSMITH_PORTAL_INGEST_TOKEN` to the token and `AGENTSMITH_PORTAL_URL` to
   this portal's `https://` address.
3. **Have its process-gates job write and send the record** — two changes to a job that already
   runs the gate:

   ```yaml
   - name: "Every gated commit has a design and a clean review"
     run: python3 <gate>/process_gate.py ci --base "$BASE" --head "$HEAD_SHA" --json "$RUNNER_TEMP/dev-record.json"
   - name: "Send the gate's record to the portal"
     if: always()
     env:
       AGENTSMITH_PORTAL_URL: ${{ secrets.AGENTSMITH_PORTAL_URL }}
       AGENTSMITH_PORTAL_INGEST_TOKEN: ${{ secrets.AGENTSMITH_PORTAL_INGEST_TOKEN }}
     run: python3 <gate>/send_dev_record.py "$RUNNER_TEMP/dev-record.json"
   ```

   `<gate>` is `scripts` in AgentSmith and in a tenant that carries the scripts, and the framework
   checkout's `scripts` in one that installs the framework. The send step runs whatever the gate
   decided. Without the secrets it says so and passes; a portal that refuses the record fails the
   step with the reason; a portal that is down only warns.

The first push after that fills the app's pages. Until then the workspace says "No data received";
data older than 24 hours is marked stale.

**Who sees what** is set per user in `OPS_PORTAL_USERS` / `OPS_PORTAL_SSO_USERS` (Ops Portal
setup, above): a `developer` or `design_approver` grant opens the Dev workspace for the apps it
lists.

#### Start a tenant from the portal

Anyone with the `developer` role or above sees **Dev › Start a tenant**. Fill in the tenant id,
its stack and options, and its first change — an objective and acceptance criteria, one per
line. The portal keeps the answers and shows a token **once**, with the commands to run on your
own machine:

```bash
mkdir <tenant> && cd <tenant> && git init
export AGENTSMITH_PORTAL_URL=https://your-portal
agentsmith tenant init --from <id>
```

The last command asks for the token: paste it there rather than exporting it, which keeps it
out of your shell history. It scaffolds the tenant with your RFC as its first, and prints the
exact command for its first commit — made on your machine, as any scaffold's is. The token works
once, for that tenant only, for 24 hours.

A tenant id that is already a registered app, or that an open intake names, is refused. If you
lost the token of an intake you started, the refusal offers **Replace it**: the old token stops
working and a new one is shown.

#### Audit log (enterprise pack, docs/DESIGN.md › Enterprise Install and Compliance Pack)

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
`verified: false` on any row whose signature no longer matches: one altered
outside the app (even by someone who disabled the trigger), or one signed
before an `AUDIT_LOG_HMAC_KEY` rotation. The portal reports the mismatch and
not a cause; the dashboard labels it **unverified** for that reason. `GET /api/audit` requires the `admin` role. Wired
call sites: `agentsmith tenant init` → `tenant_created`, `agentsmith tenant promote` →
`hitl_promotion`, `agentsmith upgrade` and `agentsmith tenant onprem-scaffold` →
`config_change`, and any hook bypass under an enterprise policy — from a hook
or from `agentsmith mode off` → `hook_bypass`. Set `OPS_PORTAL_URL` and `AUDIT_LOG_WRITE_TOKEN` in the
shell environment those commands run in.

**Local fallback:** if `OPS_PORTAL_URL`/`AUDIT_LOG_WRITE_TOKEN` aren't set,
or the write to the portal fails (down, network error, non-2xx), the event
is appended to `~/.agent-framework/local-audit-fallback.log` as a JSON line
instead of being dropped silently. This is a local, unsigned trace for
manual reconciliation — it is not a substitute for the portal's audit log
and has no tamper protection.

#### SSO/OIDC (replaces basic auth, docs/DESIGN.md › Enterprise Install and Compliance Pack)

```bash
SSO_ENABLED=true
SSO_ISSUER=https://corp.okta.com
SSO_CLIENT_ID=...
SSO_CLIENT_SECRET=...
SSO_REDIRECT_URI=https://ops.example.com/api/auth/callback
SSO_SESSION_SECRET=<random 32+ byte string>
# SSO_REVOCATION_MODE=fail-open   # default; fail-closed → 503 if session-status unreachable
```

This is exclusive with basic auth, not additive — once `SSO_ENABLED=true`,
`OPS_PORTAL_USER`/`PASSWORD` no longer grant access. Machine-to-machine
endpoints (`/api/sync/*`, `/api/widget/*`, `/api/audit/append`) are
unaffected either way.

`SSO_ALLOW_INSECURE_HTTP=true` is for testing against a local non-TLS IdP
only — never set it in a real deployment. Session `jti` revocation is always
on; `SSO_REVOCATION_MODE=fail-closed` prefers availability loss over a missed
revoke when `session-status` is down (SEC-SSO-001 / docs/DESIGN.md › Enterprise Install and Compliance Pack).

Each SSO identity's grants are resolved via `OPS_PORTAL_SSO_USERS` (see Ops Portal setup
above) — logging in via SSO grants nothing until the identity is added to that list.

`POST /api/auth/logout` revokes the session server-side (not just the
client cookie) by recording the session's `jti` claim in the
`revoked_sessions` table; every subsequent request's session check calls
`GET /api/auth/session-status` to confirm the `jti` isn't revoked before
trusting an otherwise-valid cookie. This check fails open on a DB/network
error — it won't lock out every SSO user over a transient outage, given the
session's 8h TTL already bounds the exposure of a missed revocation.

---

### In-App Widget

Embeddable, read-only status component for tenant end users. Full detail:
[templates/in-app-widget/README.md](../templates/in-app-widget/README.md).

#### Mint a token

```bash
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" -X POST https://ops.example.com/api/tenants/acme/widget-token
# => { "token": "...", "note": "Store this now — it will not be shown again." }
```

Minting (and revoking) widget tokens requires the `admin` role.

#### Revoke a leaked token

The portal never retains a token's plaintext after minting (only its hash),
so revocation is by tenant, not by the specific token string — it revokes
**every** still-active token for that tenant:

```bash
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" -X DELETE https://ops.example.com/api/tenants/acme/widget-token
# => { "ok": true, "revoked": 2 }
```

Mint a replacement and update the tenant's embed snippet afterward.

#### Embed the widget

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
whose gateway predates this, or `OPS_PORTAL_URL` unset) — and reports
`unknown` when there is neither — never `success` for a tenant that has never
run anything.

Tenant detail pages additionally show a 24h trace count and error rate
pulled live from the tenant's own Phoenix instance via GraphQL
(`portal/lib/phoenix.ts`'s `getRecentTraceStats()`) when `phoenixBaseUrl` is
configured — degrades silently (omits the line) if that Phoenix is
unreachable or has no `default` project yet.

---

---

## Evals & Tracing in Production

Eval thresholds by environment (enforced in the CD workflows, not just
locally): development is warn-only, staging fails below 0.75, production
fails below 0.80 (docs/DESIGN.md › Evaluation Framework, Per-Tenant Lifecycle and Promotion).

```bash
# Shadow-eval a sample of production traces (async, post-hoc — never blocks
# the live request; see docs/DESIGN.md › Evaluation Framework). Needs real production-environment
# spans in Phoenix to have anything to sample. Results land as Phoenix
# annotations tagged eval.type: shadow and feed the Ops Portal's
# suggested-promotion queue.
python3 scripts/shadow-eval.py --sample-rate 0.05
```

Filter Phoenix to one tenant's production traffic with
`tenant.id = "<id>" AND environment = "production"` (docs/DESIGN.md › Universal Observability Platform). The Ops
Portal's tenant detail page adds a live 24h trace count + error rate per
tenant (the Monitor in Production section above).

---

## HITL & DLQ Operations

### HITL gates and the recoverable-step DLQ (Temporal)

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

**A replay happens once.** `DeadLetterQueue.replay()` claims the row — an
`UPDATE ... WHERE status = 'pending'` — before it calls the handler, so a
retried POST, a double-clicked button, two browser tabs or a captured-and-resent
webhook are refused rather than signalling the workflow again. The receiver
answers **409** and the portal shows "this entry is no longer pending", which is
not an error to investigate. An entry a human has **discarded** cannot be
replayed at all; before this it could, and the discard was advisory. If the
handler raises, the claim is released and the entry returns to `pending`, so an
unreachable Temporal does not strand it.

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

---

## Continuous Improvement

Two independent loops turn production reality into stronger gates
(docs/DESIGN.md › Evaluation Framework) — both end at a human decision, never an auto-promote:

**1. HITL promotion loop (active).** A human reviews a Phoenix trace,
annotates the span (`hitl_approved = true`, label), then:

```bash
agentsmith evals                       # syncs annotations, re-runs the scorecard
agentsmith promote <case-id> "<input query>" "<correct output>"
```

`promote-learning.py` appends the case to `golden_evals.json`, archives the
resolution as a versioned judge-criteria learning (semantic dedup, never
silent FIFO eviction), and marks the log entry `hitl_resolved: true`. The
rule now gates every future PR.

**2. Shadow-eval loop (passive).** The the Evals & Tracing in Production section sampler surfaces failing
production patterns as *suggested promotions* in the Ops Portal
(`portal/lib/promotions.ts`) — a human triages them into loop 1; nothing is
promoted automatically.

**Fixture changes ride PRs.** Golden dataset and judge-criteria updates go
through a pull request in the tenant repo — never a direct push to `main`;
CI must validate the new cases (no `[skip ci]`). docs/DESIGN.md › Evaluation Framework "CD Golden
Dataset Commits".

---

## Maintain (Day-2 Operations)

| Task | Command |
|---|---|
| Upgrade vendored scripts in a tenant repo | `agentsmith upgrade --to <version>` |
| Refresh this machine's framework after pulling it | `./install-ai-stack.sh` from the checkout — rebuilds `~/.agent-framework/.venv` from the lock and reinstalls `agentsmith`, so every command is the pulled version. (Shell functions used to need `--force`, and without it stayed at whatever version was first installed.) |
| Prove onboarding still works on every stack (and npm/pnpm, pip/uv) | The **Scratch tenants** workflow — weekly, on provisioning changes, or `gh workflow run scratch-tenants.yml`. See [docs/scratch-tenants.md](scratch-tenants.md) |
| Change code in the framework repo | Design note in `.agent-rfc/designs/` first, review record in `.agent-rfc/reviews/` after, `Design:`/`Review:` trailers on the commit. Enforced by Claude Code hooks, `.githooks/commit-msg` (`git config core.hooksPath .githooks` once per clone) and Self-Test `process-gates`. See [docs/process-gates.md](process-gates.md) |
| Promote staging → production | `agentsmith tenant promote <id> --from staging --to production` |
| Rotate a widget token | Mint a new one (`POST .../widget-token`) — old one keeps working until explicitly revoked |
| Rotate the audit-log HMAC key | New events sign with the new key; old events will report `verified: false` against it — re-sign history or accept the discontinuity, document which |
| Purge expired idempotency keys | `agentsmith purge-idempotency` — `idempotency_keys.expires_at` is only read by the lookup, so an expired row stops being *returned* and never stops *existing*: one row per gateway call, kept forever. `IdempotencyStore.purge_expired()` existed the whole time with no caller anywhere, and its docstring named a `verify_system.py` check that does not call it |
| Prune expired session revocations | `DELETE FROM revoked_sessions WHERE revoked_at < now() - interval '1 day'` — one row per SSO logout, kept forever otherwise. A revocation only matters inside the 8h token TTL, so anything older is dead weight. The instruction previously existed only as a comment inside `portal/db/schema.sql`, which is not somewhere an operator reads |
| Rotate the org GPG signing key | Re-run `package-hook-bundle.sh` with the new key; redistribute the new public key to MDM before the next deploy |
| Check unresolved MAJOR/CRITICAL | `agentsmith check`, or `GET /api/audit` / `GET /api/tenants` on the Ops Portal |
| Remove the framework from a machine | `agentsmith uninstall` |

---

---

## Shutdown & Teardown

In dependency order — tenants first, shared infra second, machine last.

**Pause vs. remove (machine):**

```bash
agentsmith mode off          # mutes all hooks machine-wide; unlinks init.templateDir on a developer
                             # install; refused or break-glass-gated under an org policy
agentsmith uninstall         # restores the previous templateDir, removes the agentsmith link and any
                             # legacy shell-profile block, asks first
agentsmith uninstall --purge # …and deletes ~/.agent-framework and ~/.git_templates
```

**Retire a tenant:**

```bash
# 1. Revoke every live widget token (breaks all embeds for the tenant)
curl -u "$OPS_PORTAL_USER:$OPS_PORTAL_PASSWORD" -X DELETE \
  https://ops.example.com/api/tenants/<id>/widget-token

# 2. Drain the DLQ — Replay or Discard every pending entry in /dlq/<id>;
#    a parked recoverable-step workflow holds state until resolved or timeout.

# 3. Stop the worker (Cloud Run service, k8s Deployment, or local process).
#    Dedicated tier: kubectl delete namespace tenant-<id>

# 4. Clear replay-webhook routing if set (sync never unsets — docs/DESIGN.md › Production Runtime):
#    UPDATE tenants SET replay_webhook_url = NULL, replay_webhook_secret = NULL
#    WHERE tenant_id = '<id>';
```

Note: a tenant with audit history **cannot be deleted** from the portal
database — the `audit_log` FK has no cascade, by design (docs/DESIGN.md › Enterprise Install and Compliance Pack).
Retired tenants stay queryable for their audit trail.

**Stop shared infra (AgentSmith root):**

```bash
agentsmith dashboard stop            # stops Phoenix, unsets OTel env vars
docker compose down          # portal + Postgres + Phoenix containers
docker compose down -v       # ⚠️  also deletes volumes: budgets, DLQ, audit log — irreversible
```

**GCP teardown (when a cloud demo/deployment is done — these bill while up):**

```bash
gcloud run services delete <worker-service> --region <region> --project <project>
gcloud run services delete temporal-server  --region <region> --project <project>
gcloud sql instances delete temporal-pg     --project <project>
# Optional: artifacts + secrets
gcloud artifacts repositories delete <repo> --location <region> --project <project>
gcloud secrets delete <secret-name> --project <project>
```

**Scrub a repo** (remove AgentSmith runtime artefacts from a project you're
handing off): `agentsmith scrub [dir]` — interactive confirmation, removes
generated configs/fixtures, leaves your source untouched.

---

## Enterprise Pack

Optional governance layer (docs/DESIGN.md › Enterprise Install and Compliance Pack). Full detail:
[enterprise/README.md](../enterprise/README.md).

### Generate an org signing key (once)

```bash
gpg --full-generate-key
gpg --armor --export it-sec@example.com > org-public-key.asc   # distribute to MDM
```

### Package and sign the hook bundle

```bash
# On a machine with hooks already installed:
./enterprise/package-hook-bundle.sh 1.0.0 \
  --gpg-key it-sec@example.com \
  --org-policy ./our-org-policy.yaml \
  --out ./dist
```

Produces `agenticframework-hooks-1.0.0.tar.gz` + `.sig`,
`agenticframework-org.yaml`, `mdm-deploy-hooks.sh`.

### MDM deploys to every managed machine

```bash
./mdm-deploy-hooks.sh 1.0.0 --org-pubkey ./org-public-key.asc
```

This verifies the GPG signature **before** extracting anything — a
tampered or unsigned bundle is refused, not installed. Sets
`git config --global init.templateDir`, installs
`~/.agent-framework/agenticframework-org.yaml`.

### Bypass policy enforcement

Once the org policy is installed, `hooks.bypass_policy` is enforced by the git
hooks themselves (a commit or checkout run with `DISABLE_AI_STACK=true`, or on a
machine whose mode is `disabled`) and by `agentsmith mode off` — one decision,
`runtime/machine/policy.py`, which the hooks reach via
`agentsmith hooks bypass-check`. A refusal, or a check that cannot run, leaves
the hook enforcing:

| Policy | A requested bypass |
|---|---|
| (no policy file) | Granted — default dev mode |
| `disabled` | Refused; prints `break_glass_approvers` |
| `break-glass` | Refused unless `AI_BREAK_GLASS_TOKEN` is set **and validates** |
| any other value | Refused — a typo such as `disable` is not "no restriction" |

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
is never silently unrecorded (see the Monitor in Production section, "Audit log").

### Uninstall on a managed machine

```bash
agentsmith uninstall
```

Restores `git init.templateDir` to its value **before** AgentSmith
was installed (not just unset), removes the shell-rc block surgically
(your own customizations before/after it are untouched), warns if an
enterprise `bypass_policy: disabled` policy is present, prompts before
removing `~/.agent-framework` / `~/.git_templates`.

---

---

## Troubleshooting

See the Troubleshooting section above for dev-mode
issues (Phoenix, Ollama, hooks, commit message format, circuit breaker).
Production/enterprise-specific:

**`agentsmith tenant promote` fails with "eval gate failed"** — the staging eval
score is below 0.75; fix the regression on `develop` before retrying.

**Ops Portal won't start** — check `DATABASE_URL` is set and reachable, and
either `OPS_PORTAL_USER`+`PASSWORD` or the full `SSO_*` set is present; the
portal intentionally refuses to boot half-configured.

**Widget shows "invalid or revoked token"** — the token was never minted,
was revoked, or you're pointing `portal-url` at the wrong portal instance.

**`mdm-deploy-hooks.sh` refuses with "BAD signature"** — the bundle was
modified after signing, or you're verifying against the wrong public key.
Re-package from a clean checkout; never patch a signed tarball.

**`trigger_workflow.py` fails with "Workflow execution is already running"** — a
previous run failed mid-flight and its execution record was not cleaned up.
Terminate it first via the Temporal UI at `http://localhost:8233` (Workflows →
select the run → Terminate), then re-run `trigger_workflow.py`. If the Temporal
UI is unreachable, use: `temporal workflow terminate --workflow-id <id> --address 127.0.0.1:7233`
(use `127.0.0.1`, not `localhost` — macOS may resolve `localhost` to `::1`
while the dev server only binds IPv4).

**LangGraph raises "MemorySaver is prohibited"** — you set
`ENVIRONMENT=production`/`staging` without `DATABASE_URL`, **or you simply
didn't set `ENVIRONMENT` at all** — unset/unrecognized values resolve to
`production` (fail-closed, see the Configure Features section), not `development`. Either set
`DATABASE_URL`, or set `ENVIRONMENT=development` explicitly for a
throwaway/dev run.

---

---
