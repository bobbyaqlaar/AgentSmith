# Scratch tenants

Five small private repositories whose only purpose is to be onboarded by
AgentSmith, over and over, so that tenant CI runs for real on GitHub. Their app
source lives **here**, in `.github/scratch-tenants/apps/<app>/`; the scratch
repositories are pure build outputs. Every stack has at least one app; a stack
can have several, one per scenario the templates must handle.

| Repo | Stack | App source | What it keeps under test |
|---|---|---|---|
| [agentsmith-scratch-ts-react](https://github.com/bobbyaqlaar/agentsmith-scratch-ts-react) | `ts-react` | `apps/ts-react/` — stock `create-vite` react-ts + Vitest, npm | Jest-free test command, `tsc` fallback, **a pre-existing `scripts/`** (`release.mjs`) the hook must merge into |
| [agentsmith-scratch-ts-react-pnpm](https://github.com/bobbyaqlaar/agentsmith-scratch-ts-react-pnpm) | `ts-react` | `apps/ts-react-pnpm/` — the same Vite app on **pnpm** (`pnpm-lock.yaml`, `packageManager`), no `package-lock.json` | the template picks the package manager from the lockfile: `pnpm/action-setup`, pnpm cache, `pnpm install --frozen-lockfile`, `pnpm exec tsc` |
| [agentsmith-scratch-go](https://github.com/bobbyaqlaar/agentsmith-scratch-go) | `go` | `apps/go/` — one module, one tested package, **no `.gitignore`** | eval/CD workflows on a repo with no Python manifest; nothing masking stray files |
| [agentsmith-scratch-python](https://github.com/bobbyaqlaar/agentsmith-scratch-python) | `python-fastapi` | `apps/python-fastapi/` — FastAPI `/healthz` + one test, `requirements.txt` | vendored `runtime/test` suites under the template's bare `pytest`, ruff isolation, **strict security harness** |
| [agentsmith-scratch-python-uv](https://github.com/bobbyaqlaar/agentsmith-scratch-python-uv) | `python-fastapi` | `apps/python-uv/` — the same app as a **uv** project (`pyproject.toml` + `uv.lock`, dev dependency group, `[tool.ruff]`), no `requirements.txt` | the template installs the exported lock; the vendored `ruff.toml` files `extend` the project's `pyproject.toml` |

## Why they exist

Nothing inside this repository can see an onboarding bug. The framework's own
tests run against the framework's own tree, and a real tenant's CI only
exercises that tenant's stack and customisations. The 2026-09-13 audit found,
in the first real CI run of each scratch tenant, a pip cache that failed every
Go/TS eval job before it started, a ts-react template that assumed Jest and a
`tsc` script, 36 framework-internal tests failing in a stock Python tenant, a
hook that skipped a pre-existing `scripts/` without a word, and `.pyc` files
committed into a fresh Go repo. The pnpm and uv apps were added for the next
two: the TS template assumed npm and the Python template installed nothing but
a `requirements.txt`, so a pnpm tenant failed before its first check and a uv
tenant's tests failed at import. None showed up in `pytest`, and none in
AqlaarTeleologyStudio, whose customised test step hid them.

**Expected state: every tenant's CI fully green.** Every tenant gets the same
filled-in security pack (a labelled fixture, `security-pack/`) precisely so
that the strict harness, which every stack's CI runs, passes — a red run
anywhere means a framework regression, never "the placeholders again".

## Two layers of checking

| Layer | Where | Runs | Proves |
|---|---|---|---|
| **Offline build** | `scripts/test/test_scratch_tenants.py`, in Self-Test | every AgentSmith push, ~2 min | each app builds with the real hook into a complete tenant: detected as its stack, no hook warnings, the app and shared pack verbatim, the stack's workflows and actions, pruned `runtime/test`, the right test command in `CLAUDE.md`, no `.pyc` — and the **strict security harness passes** in it. Scenario apps are pinned to their base app: they may differ only in their manifest and lockfile |
| **Template scripts** | `scripts/test/test_ci_package_managers.py`, in Self-Test | every AgentSmith push, seconds | the CI templates' own `run:` scripts and the `install-python-deps` action, executed with shimmed npm/pnpm/pip/uv, call the package manager the lockfile names — the same one the hook names in the agent rules |
| **Real CI** | `.github/workflows/scratch-tenants.yml` | weekly + provisioning pushes, minutes | the built tenant's own CI goes green on GitHub, and its CD fires off it |

The first layer catches most breaks before anything is pushed anywhere; the
second catches what only GitHub can show (a template GitHub rejects, a runner
without some tool, a cache key that fails).

## How the workflow works

`.github/workflows/scratch-tenants.yml`, one matrix job per app:

1. Checks out AgentSmith at the triggering commit, and the scratch repo.
2. Runs **`install-ai-stack.sh`** from that checkout — the real installer, so
   `~/.agent-framework` and `~/.git_templates/hooks` are what a developer gets.
3. Runs **`.github/scratch-tenants/build.sh <app> tenant`**, which:
   - **fails if the scratch repo was edited directly** (its last commit is not
     by `AgentSmith scratch-tenants`) rather than silently discarding the edit;
   - empties the tree (keeping `.git` history), copies `apps/<app>/` in, adds
     the shared `security-pack/`, `SCRATCH_TENANT.md` and the opt-in marker;
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
   - Repository access: **Only select repositories** → all five `agentsmith-scratch-*` repos (a new app's repo must be added here too). Not "Public repositories": that authenticates, then every checkout fails with `Not Found`
   - Permissions: **Contents → Read and write**, **Workflows → Read and write**, **Actions → Read-only** (Metadata is added automatically).
     Workflows is needed because each build writes the tenant's `.github/workflows/`; without it GitHub rejects any push that changes a workflow file, and accepts the rest — so a token missing it works until the first template change
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
| **Build**: `edited directly` | someone committed to the scratch repo. Move the change into `apps/<app>/`; to discard it instead, run once with `SCRATCH_TENANTS_ALLOW_MANUAL_HEAD=1` |
| **Build** with a `⚠️` line | the installed hook could not vendor something — every new tenant is broken the same way. The offline test in Self-Test should have failed too |
| **Build**: `changed .gitignore` | `gh` is not authenticated in the job (token expired), so the hook treated the repo as public |
| **Push**: `without \`workflow\` scope` | the token lacks **Workflows: Read and write**. Only pushes that change a workflow file need it, so it surfaces on the first template change |
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

- **App code** is edited in `.github/scratch-tenants/apps/<app>/`, reviewed
  and committed with the framework. Pushing it triggers the workflow, which
  rebuilds that tenant. Editing a scratch repo directly fails the next build.
- **A template change that needs an app change** lands as one AgentSmith
  commit; the offline test checks both together before anything is pushed.
- **The security pack** is ONE copy for every tenant,
  `.github/scratch-tenants/security-pack/`, which `build.sh` copies in; apps
  must not carry their own. It holds only the two authored files; the hook
  seeds the other two, and its "never overwrite" rule stays under test because
  the authored ones are copied in first. It is a labelled fixture, not a real
  risk assessment.
- **A scenario app** (`ts-react-pnpm`, `python-uv`) is a deliberate copy of
  its base app with one thing changed, so each scratch repo stays a realistic
  standalone project. A fix to the base's source must land in the copy too —
  `test_scratch_tenants.py` fails on any other difference.
- **A new app** — a new stack in `runtime/cli.py`'s `STACKS`, or another
  scenario for an existing one (a yarn TS app, a Poetry Python app) — needs
  `apps/<app>/`, a matrix entry naming its `stack` and repo, an entry in
  `test_scratch_tenants.py`'s `SCENARIOS` saying what makes it that scenario,
  and a new private scratch repo **selected on the token**.
  `test_scratch_tenants.py` fails until the directory, matrix entry and
  scenario agree, and until every stack has an app. Create the repo and update
  the token *before* pushing the matrix entry, or that job fails at checkout.

## Cost

Private repos, ~600 KB each, no secrets of their own; the app sources add
~260 KB to AgentSmith (mostly the TS apps' lockfiles, which a frozen install
needs). Per workflow run: five AgentSmith jobs (~3–5 min each) plus each
tenant's CI (~1–4 min), weekly plus provisioning-change pushes. The offline test
adds about two minutes to Self-Test, nearly all of it the five strict harness
runs. Eval jobs skip rather than grade — the scratch repos
hold no API keys — so a green eval there proves the workflow runs, not model
quality.
