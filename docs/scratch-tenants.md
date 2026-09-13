# Scratch tenants

Three small private repositories whose only purpose is to be onboarded by
AgentSmith, over and over, so that tenant CI runs for real on GitHub. Their app
source lives **here**, in `.github/scratch-tenants/apps/<stack>/`; the scratch
repositories are pure build outputs.

| Repo | Stack | App source | What it keeps under test |
|---|---|---|---|
| [agentsmith-scratch-ts-react](https://github.com/bobbyaqlaar/agentsmith-scratch-ts-react) | `ts-react` | `apps/ts-react/` — stock `create-vite` react-ts + Vitest | Jest-free test command, `tsc` fallback, **a pre-existing `scripts/`** (`release.mjs`) the hook must merge into |
| [agentsmith-scratch-go](https://github.com/bobbyaqlaar/agentsmith-scratch-go) | `go` | `apps/go/` — one module, one tested package, **no `.gitignore`** | eval/CD workflows on a repo with no Python manifest; nothing masking stray files |
| [agentsmith-scratch-python](https://github.com/bobbyaqlaar/agentsmith-scratch-python) | `python-fastapi` | `apps/python-fastapi/` — FastAPI `/healthz` + one test, authored security pack | vendored `runtime/test` suites under the template's bare `pytest`, ruff isolation, **strict security harness** |

## Why they exist

Nothing inside this repository can see an onboarding bug. The framework's own
tests run against the framework's own tree, and a real tenant's CI only
exercises that tenant's stack and customisations. The 2026-09-13 audit found,
in the first real CI run of each scratch tenant, a pip cache that failed every
Go/TS eval job before it started, a ts-react template that assumed Jest and a
`tsc` script, 36 framework-internal tests failing in a stock Python tenant, a
hook that skipped a pre-existing `scripts/` without a word, and `.pyc` files
committed into a fresh Go repo. None showed up in `pytest`, and none in
AqlaarTeleologyStudio, whose customised test step hid them.

**Expected state: every tenant's CI fully green.** The Python app's security
pack is filled in (as a labelled fixture) precisely so that its strict harness
passes — a red run anywhere means a framework regression, never "the
placeholders again".

## Two layers of checking

| Layer | Where | Runs | Proves |
|---|---|---|---|
| **Offline build** | `scripts/test/test_scratch_tenants.py`, in Self-Test | every AgentSmith push, seconds | each app builds with the real hook into a complete tenant: no hook warnings, the app verbatim, the stack's workflows and actions, pruned `runtime/test`, no `.pyc` |
| **Real CI** | `.github/workflows/scratch-tenants.yml` | weekly + provisioning pushes, minutes | the built tenant's own CI goes green on GitHub, and its CD fires off it |

The first layer catches most breaks before anything is pushed anywhere; the
second catches what only GitHub can show (a template GitHub rejects, a runner
without some tool, a cache key that fails).

## How the workflow works

`.github/workflows/scratch-tenants.yml`, one matrix job per stack:

1. Checks out AgentSmith at the triggering commit, and the scratch repo.
2. Runs **`install-ai-stack.sh`** from that checkout — the real installer, so
   `~/.agent-framework` and `~/.git_templates/hooks` are what a developer gets.
3. Runs **`.github/scratch-tenants/build.sh <stack> tenant`**, which:
   - **fails if the scratch repo was edited directly** (its last commit is not
     by `AgentSmith scratch-tenants`) rather than silently discarding the edit;
   - empties the tree (keeping `.git` history), copies `apps/<stack>/` in, adds
     `SCRATCH_TENANT.md` and the opt-in marker;
   - fires the **installed** post-checkout hook;
   - fails on any hook warning (column-0 `⚠️`/`❌`), and if the hook changed or
     created `.gitignore` — which means it could not confirm the repo is private.
4. Commits (always — `--allow-empty` — so a quiet week still re-runs CI) with
   hooks disabled, and pushes. The message names the AgentSmith commit, so each
   scratch commit's diff is exactly what that framework change did to a tenant.
5. Waits for the tenant's `CI: …` run on that commit and **fails unless it
   concludes `success`**, listing the failed jobs and steps. The job summary
   links the run.

**Triggers:** Mondays 06:00 UTC; manual (`gh workflow run scratch-tenants.yml`);
and any push to `main` touching `hooks/`, `install-ai-stack.sh`,
`workflow-templates/`, `.github/actions/`, non-test `scripts/` or `runtime/`,
`fixtures/`, `templates/agent-rules.yaml`, or `.github/scratch-tenants/` (which
includes the apps).

Each tenant's CD then runs off its CI via `workflow_run` — green CI shows
`CD: Production Deploy` succeeding as a no-op (no `DEPLOY_COMMAND`); red CI
shows it skipped. That is the CD gate being exercised too.

## Setup (once)

The job pushes to other repositories, which `GITHUB_TOKEN` cannot do.

1. Create a **fine-grained personal access token**
   (GitHub → Settings → Developer settings → Fine-grained tokens):
   - Resource owner: `bobbyaqlaar`
   - Repository access: **Only select repositories** → the three `agentsmith-scratch-*` repos. Not "Public repositories": that authenticates, then every checkout fails with `Not Found`
   - Permissions: **Contents → Read and write**, **Actions → Read-only** (Metadata is added automatically)
   - Expiry: your choice. When it lapses, runs fail at **Checkout agentsmith-scratch-…** with an authentication error — renew it and update the secret
2. Store it on AgentSmith:
   ```bash
   gh secret set SCRATCH_TENANTS_TOKEN -R bobbyaqlaar/AgentSmith
   ```
3. Run it once: `gh workflow run scratch-tenants.yml -R bobbyaqlaar/AgentSmith`

Without the secret every run fails at its first step with
`SCRATCH_TENANTS_TOKEN is not set` — deliberately loud rather than skipped.

## When it goes red

Open the job summary's link to the tenant run, then:

| Where it failed | Usually means |
|---|---|
| **Install AgentSmith** | installer regression, or a pinned Python dependency no longer resolves |
| **Build**: `edited directly` | someone committed to the scratch repo. Move the change into `apps/<stack>/`; to discard it instead, run once with `SCRATCH_TENANTS_ALLOW_MANUAL_HEAD=1` |
| **Build** with a `⚠️` line | the installed hook could not vendor something — every new tenant is broken the same way. The offline test in Self-Test should have failed too |
| **Build**: `changed .gitignore` | `gh` is not authenticated in the job (token expired), so the hook treated the repo as public |
| **Checkout agentsmith-scratch-…**: `Not Found` | the token does not have that repository selected (or has expired) — edit the token's Repository access |
| **Wait for CI**: `cannot read Actions … (HTTP 403)` | the token lacks **Actions: Read-only** — the push worked, the tenant's CI is running, the job just cannot see it |
| **Wait for CI**: no run appeared | the tenant's CI YAML is invalid (GitHub rejected it) or a `ci-*.yml` `name:` changed |
| **Wait for CI**: a tenant job failed | a template, vendored-code or app regression — reproduce locally, below |

Reproduce locally against your own install — no clone needed:

```bash
./install-ai-stack.sh --force
.github/scratch-tenants/build.sh python-fastapi /tmp/scratch-python
cd /tmp/scratch-python && python3 -m pytest -q
```

To see exactly what a push would change, build over a clone instead:

```bash
git clone --template= https://github.com/bobbyaqlaar/agentsmith-scratch-python.git /tmp/scratch-python
.github/scratch-tenants/build.sh python-fastapi /tmp/scratch-python
cd /tmp/scratch-python && git status
```

`--template=` keeps the armed global hooks out of the clone (post-commit
pushes). Don't push from there: the next workflow build would fail on a commit
not made by the workflow.

## Changing the tenants

- **App code** is edited in `.github/scratch-tenants/apps/<stack>/`, reviewed
  and committed with the framework. Pushing it triggers the workflow, which
  rebuilds that tenant. Editing a scratch repo directly fails the next build.
- **A template change that needs an app change** lands as one AgentSmith
  commit; the offline test checks both together before anything is pushed.
- **The Python app's security pack** (`apps/python-fastapi/.agent-rfc/security/`)
  holds only the two authored files; the hook seeds the other two, and its
  "never overwrite" rule stays under test because the authored ones are copied
  in first. It is a labelled fixture, not a real risk assessment.
- **A new stack** in `runtime/cli.py`'s `STACKS` needs `apps/<stack>/`, a new
  scratch repo selected on the token, and a matrix entry;
  `test_scratch_tenants.py` fails until all three exist and the matrix names the
  stack's real CI workflow.
- **A new scenario for an existing stack** (say, a pnpm-based TS app) is a new
  app directory, scratch repo and matrix entry.

## Cost

Private repos, ~600 KB each, no secrets of their own; the app sources add
~210 KB to AgentSmith (mostly the TS app's `package-lock.json`, which `npm ci`
needs). Per workflow run: three AgentSmith jobs (~3–5 min each) plus each
tenant's CI (~1–4 min), weekly plus provisioning-change pushes. The offline test
adds seconds to Self-Test. Eval jobs skip rather than grade — the scratch repos
hold no API keys — so a green eval there proves the workflow runs, not model
quality.
