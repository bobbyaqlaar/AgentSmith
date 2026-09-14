# Process gates

Design before code and review before merge are checked by machine in this
repository, not left to whoever — or whatever agent — is doing the work.

`docs/design-review-checklist.md` and `docs/review-levers.md` existed for weeks
and were still skipped, for two reasons that more documentation could not fix:
no agent session in this repo ever had them in context, and nothing checked.
Every gate below calls one script, `scripts/process_gate.py`, so the rules are
defined once. Design: `.agent-rfc/designs/process-gates.md`.

## What is checked, where

| Layer | Runs | Blocks | Can be skipped by |
|---|---|---|---|
| **Session context** — `.claude/settings.json` SessionStart | every Claude Code session | nothing — states the rules, lists active designs, warns if the commit gate is not armed | not using Claude Code |
| **Edit gate** — PreToolUse on Edit/Write/MultiEdit/NotebookEdit | before each file edit | an edit to a gated path that no complete, *active* design note covers | editing through a shell command (the next three layers still see it) |
| **Stop gate** — Stop | when an agent ends its turn | ending with uncommitted gated changes that have no clean review record newer than them | a second stop in a row (it warns instead of looping) |
| **Commit gate** — `.githooks/commit-msg` | `git commit` (including `--amend`), in a clone that armed it | a commit touching gated paths without resolving `Design:` and `Review:` trailers | not arming it, `--no-verify`, and history rewrites git runs without `commit-msg` — rebase picks, cherry-picks (CI still sees all of them) |
| **CI gate** — Self-Test job `process-gates` | every push and pull request | a pushed range with any non-compliant gated commit, or tenant-facing changes without a CHANGELOG update | nothing in the repo — but it reports red after a push rather than refusing it (below) |

**What no gate can check** is whether the design was *good*. The gates prove a
design exists, is scoped to the change, and cites real levers; that a review
ran until a pass found nothing; and that the review is as fresh as the change.
Quality still needs a reviewer who is not the builder.

## Setup, once per clone

```bash
git config core.hooksPath .githooks
python3 scripts/generate-ide-config.py --repo-root .   # AGENTS.md, .cursorrules, … for other agents (gitignored)
```

The Claude Code hooks need nothing: they live in the committed
`.claude/settings.json`. The session-start message says if either step above
is missing.

Arming `.githooks` replaces the tenant hooks in `~/.git_templates` for this
clone. That is deliberate: this is the framework, not a tenant, and
`hooks/post-commit` pushes on its own.

## Gated paths

Code, configuration, and anything a tenant receives: `scripts/`, `runtime/`,
`hooks/`, `portal/`, `workflow-templates/`, `.github/`, `templates/`,
`enterprise/`, `examples/`, `fixtures/`, `init-db/`, `caddy/`, `.githooks/`,
`install-ai-stack.sh`, `pyproject.toml`, `pytest.ini`, `requirements*.txt`,
`docker-compose*.yml`, `.claude/settings.json`. **Not gated:** any `*.md`,
`.agent-rfc/`, `node_modules/`. The list lives in `process_gate.py` (`GATED`).

**Tenant-facing** paths — the ones whose change needs a `CHANGELOG.md`
[Unreleased] entry in the same push — are the ones
`.github/workflows/scratch-tenants.yml` rebuilds tenants on; a test keeps the
two lists identical.

## The two records

**Design note** — `.agent-rfc/designs/<slug>.md`, written *before* the code:

```markdown
---
status: active          # active while you build; done when it has shipped
scope:
  - scripts/process_gate.py
  - scripts/test/test_process_gate.py
  - .githooks/**
---
# One-line title

## Problem
What is wrong or missing, and the evidence.

## Approach
What you will build, and the decisions that matter.

## Levers
- `one-catalog` — why it applies and what the design does about it.
```

The edit gate only unlocks paths matched by `scope`, only while
`status: active`, and only when all three sections exist and `## Levers` cites
at least one lever from `docs/review-levers.md`. Work
`docs/design-review-checklist.md` to find them. Other sections
(`## Alternatives rejected`, …) are welcome.

**Review record** — `.agent-rfc/reviews/<slug>.md`, same slug, one heading per
pass, written *after* building:

```markdown
## Pass 1 — findings: 3
- `grep-for-siblings` — eval-security.yml kept its own copy of the install. Fixed: …
- …

## Pass 2 — findings: 0
```

Verify each finding in code before recording it, fix it, and run another pass.
The record is clean only when its last pass reports `findings: 0`, and passes
are numbered 1, 2, 3… with none skipped.

## Commit trailers

```
feat(ci): the thing

Why, in prose.

Design: .agent-rfc/designs/process-gates.md
Review: .agent-rfc/reviews/process-gates.md
```

For a commit touching gated paths, the commit gate and CI require:

- the design exists **in that commit**, is complete, and its `scope` covers
  every gated path the commit changes;
- the review exists, is clean, and **is changed in that same commit**. A review
  written before the change cannot vouch for it — record the pass that covers
  this change;
- each trailer names a file directly under `.agent-rfc/designs/` or
  `.agent-rfc/reviews/` — nothing else.

**`n/a: <reason>`** is accepted for either trailer when the commit changes at
most 20 gated lines (a typo, a version pin). CI lists every such commit in its
summary, so the escape stays visible.

## When a gate blocks you

| Message | Do this |
|---|---|
| `… is a gated path and no active design note covers it` | write the design note (above), or add the path to an active design's `scope` if it belongs to that work |
| `… covered by a design note that is not complete` | add the missing section, or cite a real lever in `## Levers` |
| `Unreviewed gated changes: … no review record` | run a review pass against `docs/review-levers.md` and record it |
| `… last updated before the newest change it covers` | you changed code after the last pass — review again and record the pass |
| `missing 'Design: …' trailer` / `missing 'Review: …' trailer` | add the trailers to the commit message |
| `Review: … is not changed in this commit` | record the pass that covers this change, and stage the review file |
| `n/a is allowed only for changes of at most 20 gated lines` | write the records; the change is too big to wave through |
| CI: `tenant-facing paths changed … CHANGELOG.md` | add an [Unreleased] entry, calling out hook-interface changes |

## Limits, stated

- **The CI gate cannot refuse a push.** Branch protection, which would make
  `process-gates` a required check on `main`, needs GitHub Pro for a private
  repository (verified 2026-09-14: the API answers "Upgrade to GitHub Pro or
  make this repository public"). Until then a non-compliant push lands and
  Self-Test goes red. Recorded in `FIXES_AND_CLEANUP.md`.
- **Only the edit gate fails closed.** If `python3` is missing or the script
  dies, the edit gate still denies (its command falls back to a deny). The
  session-start and stop hooks cannot: Claude Code treats their failure as a
  non-blocking error, and a stop hook that blocked without being able to read
  `stop_hook_active` could loop forever. The commit and CI gates still hold.
- **Shell-made edits skip the edit gate.** A command's file writes cannot be
  read reliably from its text. The stop, commit and CI gates check the files
  themselves.
- **History before 2026-09-14 is not gated.** CI checks only the commits each
  push adds.
- **Tenants do not get these gates yet.** `process_gate.py` is vendored with
  `scripts/`, but no tenant template wires it. Recorded in
  `FIXES_AND_CLEANUP.md` with its trigger.

## Tenant repositories: auto-push without disabling hooks

`hooks/post-commit` auto-tags a `feat`/`fix`/`perf`/`refactor` commit and pushes
it when the branch tracks a remote. To keep the tag and skip the push:

```bash
git config agentsmith.autopush false    # this repo
AGENTSMITH_AUTOPUSH=0 git commit …      # one commit
```

The only alternative used to be `git -c core.hooksPath=/dev/null commit`, which
also skipped `pre-commit` and `commit-msg`.
