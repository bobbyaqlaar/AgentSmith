# Scratch tenants

Three small private repositories whose only purpose is to be onboarded by
AgentSmith, over and over, so that tenant CI runs for real on GitHub.

| Repo | Stack | App | What it keeps under test |
|---|---|---|---|
| [agentsmith-scratch-ts-react](https://github.com/bobbyaqlaar/agentsmith-scratch-ts-react) | `ts-react` | stock `create-vite` react-ts + Vitest | Jest-free test command, `tsc` fallback, **a pre-existing `scripts/`** (`release.mjs`) the hook must merge into |
| [agentsmith-scratch-go](https://github.com/bobbyaqlaar/agentsmith-scratch-go) | `go` | one module, one tested package | eval/CD workflows on a repo with no Python manifest |
| [agentsmith-scratch-python](https://github.com/bobbyaqlaar/agentsmith-scratch-python) | `python-fastapi` | FastAPI `/healthz` + one test | vendored `runtime/test` suites under the template's bare `pytest`, ruff isolation, **strict security harness** |

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

**Expected state: every tenant's CI fully green.** The Python tenant's
security pack is filled in (as a labelled fixture) precisely so that its strict
harness passes — a red run anywhere means a framework regression, never "the
placeholders again".

## How the workflow works

`.github/workflows/scratch-tenants.yml`, one matrix job per stack:

1. Checks out AgentSmith at the triggering commit, and the scratch repo.
2. Runs **`install-ai-stack.sh`** from that checkout — the real installer, so
   `~/.agent-framework` and `~/.git_templates/hooks` are what a developer gets.
3. Runs **`.github/scratch-tenants/reprovision.sh <stack> tenant`**, which
   deletes everything provisioning owns (`.github/`, `runtime/`, `fixtures/`,
   IDE config, `.agent-rfc/` except `security/`, vendored `scripts/`), keeps the
   app and the authored security pack, and fires the **installed**
   post-checkout hook. It fails on any hook warning (column-0 `⚠️`/`❌`) and if
   the hook rewrites `.gitignore` for a repo it wrongly thinks is public.
4. Commits (always — `--allow-empty` — so a quiet week still re-runs CI) with
   hooks disabled, and pushes. The message names the AgentSmith commit.
5. Waits for the tenant's `CI: …` run on that commit and **fails unless it
   concludes `success`**, listing the failed jobs and steps. The job summary
   links the run.

**Triggers:** Mondays 06:00 UTC; manual (`gh workflow run scratch-tenants.yml`);
and any push to `main` touching `hooks/`, `install-ai-stack.sh`,
`workflow-templates/`, `.github/actions/`, non-test `scripts/` or `runtime/`,
`fixtures/`, `templates/agent-rules.yaml`, or the pipeline itself.

Each tenant's CD then runs off its CI via `workflow_run` — green CI shows
`CD: Production Deploy` succeeding as a no-op (no `DEPLOY_COMMAND`); red CI
shows it skipped. That is the CD gate being exercised too.

## Setup (once)

The job pushes to other repositories, which `GITHUB_TOKEN` cannot do.

1. Create a **fine-grained personal access token**
   (GitHub → Settings → Developer settings → Fine-grained tokens):
   - Resource owner: `bobbyaqlaar`
   - Repository access: **only** the three `agentsmith-scratch-*` repos
   - Permissions: **Contents: Read and write**, **Actions: Read** (Metadata: Read is added automatically)
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
| **Re-provision** with a `⚠️` line | the installed hook could not vendor something — every new tenant is broken the same way |
| **Re-provision**: `.gitignore` rewrite | `gh` is not authenticated in the job (token expired or lacks Metadata read) |
| **Wait for CI**: no run appeared | the tenant's CI YAML is invalid (GitHub rejected it) or a `ci-*.yml` `name:` changed |
| **Wait for CI**: a tenant job failed | a template or vendored-code regression — reproduce locally, below |

Reproduce locally against your own install:

```bash
./install-ai-stack.sh --force
git clone --template= https://github.com/bobbyaqlaar/agentsmith-scratch-python.git /tmp/scratch-python
.github/scratch-tenants/reprovision.sh python-fastapi /tmp/scratch-python
cd /tmp/scratch-python && git status
```

`--template=` keeps the armed global hooks out of the clone (post-commit
pushes). Push from there only if you mean to re-run that tenant's CI.

## Changing the tenants

- **App code** (anything not provisioned) is edited directly in the scratch
  repo; the workflow never touches it.
- **Tenant-owned files inside provisioned directories** are declared per stack
  in `reprovision.sh` (`TENANT_OWNED_SCRIPTS`) — add them there, or the next
  run deletes them.
- **A new stack** in `runtime/cli.py`'s `STACKS` needs a new scratch repo and a
  matrix entry; `scripts/test/test_scratch_tenants.py` fails until the matrix
  covers every stack and names each stack's real CI workflow.
- **The security pack** (`.agent-rfc/security/`) is kept across runs. Edit it
  in the scratch repo; it is a labelled fixture, not a real risk assessment.

## Cost

Private repos, ~600 KB each, no secrets of their own. Per run: three AgentSmith
jobs (~5–10 min each, mostly the installer's pip step and waiting) plus each
tenant's CI (~1–4 min). Weekly plus provisioning-change pushes. Eval jobs skip
rather than grade — the scratch repos hold no API keys — so a green eval there
proves the workflow runs, not model quality.
