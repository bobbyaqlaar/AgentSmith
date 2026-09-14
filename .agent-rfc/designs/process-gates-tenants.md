---
status: done
scope:
  - scripts/process_gate.py
  - scripts/test/test_process_gate.py
  - .agenticframework/process-gates.json
  - .githooks/**
  - .claude/settings.json
  - install-ai-stack.sh
  - scripts/test/test_design_and_validation_docs.py
  - scripts/test/test_hooks_behavior.py
---
# Process gates for tenants — OTS and KYC Sentinel

## Problem

The process gates (`.agent-rfc/designs/process-gates.md`, shipped 2026-09-14)
enforce design-before-code and review-before-merge in AgentSmith only. Rolling
them out to AqlaarTeleologyStudio (OTS) and KYC Sentinel is blocked by four
facts about `scripts/process_gate.py` as shipped, each verified:

1. **The catalog is AgentSmith's layout, in code.** `GATED` names `portal/`,
   `workflow-templates/`, `enterprise/`… OTS's code is `apps/web`, `services/`;
   KYC's is `agents/`, `workflows/` and root `*.py`. A tenant would gate the
   wrong paths — mostly none.
2. **Levers and checklist are read from the repo** (`docs/review-levers.md` at
   the commit). OTS has its own copy (54 levers, an inherited-and-extended
   list); KYC has none, and `~/.agent-framework/docs/` carries only the two
   checklists, not `review-levers.md`.
3. **The script is found at `scripts/process_gate.py` in the repo.** True for
   OTS (vendored). KYC is installed-mode: its `scripts/` is its own, and its CI
   runs framework tools from a checkout at `$AGENTSMITH_DIR`.
4. **Neither clone has git hooks installed** (`.git/hooks` has no non-sample
   hook), and neither has a CHANGELOG — OTS has none; KYC keeps `DEVLOG.md`.

## Approach

**Per-repo configuration, one file: `.agenticframework/process-gates.json`.**
The gate is inactive in a repo without it. Keys:

- `gated`, `not_gated` — globs (`**` crosses directories).
- `levers_doc`, `design_checklist` — a repo path, read at the commit being
  checked; or `@framework/<path>`, resolved beside the running
  `process_gate.py` (its checkout, or `~/.agent-framework`).
- `changelog` — optional `{ "file", "paths", "except" }`; omitted, there is no
  CHANGELOG rule.

AgentSmith's catalog moves out of the code into its own config, so there is one
catalog per repo and none in the script. The pin against `scratch-tenants.yml`
now parses the JSON. The config file is itself gated in every repo — otherwise
deleting a line would turn a gate off with no design or review.

**Missing config.** `pre-edit`, `stop` and `commit-msg` do nothing (the repo has
not adopted the gates). `ci` FAILS: a repo whose CI runs the gate has adopted
it, so a missing config there means it was removed.

**Finding the script — one command form in every repo.** The Claude Code hook
commands and `.githooks/commit-msg` try, in order, `$CLAUDE_PROJECT_DIR` or the
repo's `scripts/process_gate.py`, then `$AGENTSMITH_DIR/scripts/`, then
`~/.agent-framework/scripts/`. The edit gate denies if none exists (fail
closed); `.githooks/commit-msg` blocks the commit. The same file is copied
verbatim to each tenant. `install-ai-stack.sh` now also copies
`docs/review-levers.md` into `~/.agent-framework/docs/`.

**Per tenant.**

| | OTS (vendored) | KYC Sentinel (installed) |
|---|---|---|
| Script | `scripts/process_gate.py`, vendored (+ its `scripts/ruff.toml` exclude) | framework checkout / `~/.agent-framework` |
| Levers | its own `docs/review-levers.md` | `@framework/docs/review-levers.md` |
| Checklist | `@framework/docs/design-review-checklist.md` | same |
| Gated | `apps/`, `services/`, `runtime/`, `scripts/`, `infra/`, `fixtures/`, `.github/`, `.agenticframework/`, `.githooks/`, `main.py`, `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `.claude/settings.json` | `agents/`, `workflows/`, `test/`, `scripts/`, `corpus/`, `fixtures/`, `.github/`, `.agenticframework/`, `.githooks/`, root `*.py`, `models.yaml`, `requirements.txt`, `pytest.ini`, `Makefile`, `Dockerfile`, `.dockerignore`, `.claude/settings.json` |
| Not gated | `*.md`, `.agent-rfc/`, `docs/`, `ReferenceDocs/`, `data/`, `node_modules/` | `*.md`, `.agent-rfc/` |
| CHANGELOG rule | none (no CHANGELOG) | none (DEVLOG is a log, not release notes) |
| CI job | `process-gates` in `ci-python-fastapi.yml` | `process-gates` in `ci.yml`, after the framework checkout |

Each tenant's rollout commit carries its own design note and review record,
so the gate it installs passes on the commit that installs it.

**AgentSmith's `docs/process-gates.md`** gains the config reference and a
"Rolling out to a tenant" checklist; provisioning a *new* tenant automatically
stays open in `FIXES_AND_CLEANUP.md`.

## Alternatives rejected

- **Vendor `process_gate.py` and the lever docs into KYC.** Installed mode
  exists so KYC does not carry framework copies that drift from its pin; the
  gate is a framework tool like the security harness, which KYC also runs from
  a checkout.
- **Put the gate in the tenant `hooks/commit-msg`.** Neither clone has hooks
  installed, so it would reach neither; `.githooks/` is committed and armed per
  clone exactly as in AgentSmith.
- **Keep AgentSmith's catalog as a code default.** Two catalogs for one repo —
  the default and any config — is the drift `one-catalog` exists to prevent.

## Levers

- `one-catalog` — the catalog leaves the code for one config per repo; `pin-unremovable-duplicates` keeps AgentSmith's `changelog.paths` equal to `scratch-tenants.yml`'s.
- `declared-vs-enforced` — the config file is itself gated, so the declaration of what is gated cannot change unreviewed.
- `guards-must-be-able-to-fail` — `ci` fails on a missing config rather than passing a repo that silently dropped the gate; the script-finder denies when it finds nothing.
- `provenance-and-precedence` — script lookup order (repo, `$AGENTSMITH_DIR`, `~/.agent-framework`) and `@framework/` resolution are written down here and in the docs.
- `minimal-host-dependency` — KYC's local gates need a framework checkout or a current `~/.agent-framework`; stated, and the fail-closed message names the fix.
- `two-owners-two-cadences` — tenants take the gate from the framework they run: OTS's vendored copy moves on `ai-stack-upgrade`, KYC's follows the framework checkout its CI uses.
- `implemented-not-invoked` — each tenant's CI job, hooks and settings are exercised by a real commit and a real CI run, not only by framework tests.
- `environment-parity` — the pre-push gate list runs on macOS; each tenant's first CI run is the Linux check (the lesson of `3431634`).
- `docs-match-behaviour` — `docs/process-gates.md`, CHANGELOG, backlog, and each tenant's own docs.
