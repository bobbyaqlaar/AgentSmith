---
status: active
scope:
  - scripts/process_gate.py
  - scripts/test/test_process_gate.py
  - .githooks/**
  - .claude/settings.json
  - hooks/post-commit
  - scripts/test/test_hooks_behavior.py
  - scripts/test/test_workflow_template_wiring.py
  - .github/workflows/self-test.yml
  - .github/workflows/scratch-tenants.yml
---
# Process gates — design before code, review before merge, enforced

## Problem

`docs/design-review-checklist.md` and `docs/review-levers.md` were written down
and skipped. Two causes, both verified 2026-09-14, and neither fixed by
rewriting the rules:

1. **Not in context.** This repo has no `CLAUDE.md`/`AGENTS.md` of its own (they
   are gitignored and the repo was never opted in), so no agent session here
   ever saw the checklists.
2. **Nothing checks.** Every commit ran with `core.hooksPath=/dev/null`, because
   `hooks/post-commit` pushes on its own; and no gate — local or CI — asks
   whether a change had a design or a review.

A rule an agent reads is advisory. Only a mechanical check is strict.

## Approach

Three layers, one implementation (`scripts/process_gate.py`, stdlib only):

| Layer | Where | When | Blocks |
|---|---|---|---|
| Context | `.claude/settings.json` SessionStart → `process_gate.py session-start` | every Claude Code session | nothing; states the rules and the gates |
| Agent gates | `.claude/settings.json` PreToolUse (Edit/Write/NotebookEdit) → `pre-edit`; Stop → `stop` | as the agent works | an edit to a gated path with no active design covering it; ending a turn with gated changes and no clean review newer than them |
| Commit | `.githooks/commit-msg` → `commit-msg` | every commit in a clone with `core.hooksPath=.githooks` | a commit touching gated paths without `Design:`/`Review:` trailers that resolve |
| CI | Self-Test job `process-gates` → `ci --base --head` | every push and PR | the same per-commit checks over the pushed range, plus CHANGELOG for tenant-facing paths |

**Records.** A design note is `.agent-rfc/designs/<slug>.md` with front matter
`status: active|done` and `scope:` globs, and body sections `## Problem`,
`## Approach`, `## Levers`; the Levers section must cite at least one slug that
exists in `docs/review-levers.md` (parsed, not listed here). A review record is
`.agent-rfc/reviews/<slug>.md` with `## Pass N — findings: K` headings; it is
clean when its last pass reports `findings: 0`.

**Trailers.** `Design: .agent-rfc/designs/<slug>.md` and
`Review: .agent-rfc/reviews/<slug>.md`. The design's scope must cover every
gated path the commit touches. The review must be clean, and must be changed
**in that same commit** — a review older than the change it vouches for proves
nothing, and "same commit" is the one freshness rule the local hook and CI can
check identically (a local commit cannot see a later one). `n/a: <reason>` is accepted for
either trailer only when the commit changes at most 20 gated lines; the CI
summary lists every such commit, so the escape is visible, not silent.

**Gated paths** (one catalog, in `process_gate.py`): code and anything a tenant
receives — `scripts/`, `runtime/`, `hooks/`, `portal/`, `workflow-templates/`,
`.github/`, `templates/`, `enterprise/`, `examples/`, `fixtures/`, `init-db/`,
`caddy/`, `install-ai-stack.sh`, `pyproject.toml`, `pytest.ini`,
`requirements*.txt`, `docker-compose*.yml`, `.githooks/`,
`.claude/settings.json` — excluding
Markdown, `.agent-rfc/`, and generated files (the Knowledge Graph).
**Tenant-facing paths** for the CHANGELOG rule are the list
`scratch-tenants.yml` already triggers on; a test parses that workflow and pins
the two together.

**Stop loop.** A Stop hook that blocks can loop. When the hook input says
`stop_hook_active`, it does not block again; it emits a `systemMessage` so the
user sees that the turn ended with unreviewed changes. The commit and CI gates
are the hard stops.

**Auto-push.** `hooks/post-commit` keeps auto-tagging, but skips the push when
`git config agentsmith.autopush false` (or `AGENTSMITH_AUTOPUSH=0`), so nobody
needs `core.hooksPath=/dev/null` to commit without pushing — which also skipped
every other hook. This repo uses `.githooks/`, which has no post-commit at all.

## Alternatives rejected

- **More instructions in CLAUDE.md.** The failure was that instructions were
  absent and unchecked; adding more text fixes neither.
- **Gate on Bash too.** A shell command's file writes cannot be read reliably
  from its text. The Stop, commit and CI layers catch Bash-made changes; the
  edit gate says it does not.
- **Branch protection / PR-only `main`.** Verified unavailable: GitHub returns
  "Upgrade to GitHub Pro or make this repository public" for a private repo on
  Free. The CI gate goes red after a push instead of refusing it — recorded as
  an open item with its trigger.
- **Checking design quality.** No gate can. The gates prove a design and a
  clean review exist, are scoped to the change, and cite real levers; quality
  still needs a reviewer who is not the builder.

## Levers

- `declared-vs-enforced` — the checklists are declared controls with no reader; every layer here is a reader.
- `implemented-not-invoked` — each gate names its caller (settings.json, `.githooks/`, self-test.yml), and a test checks each caller invokes a real subcommand.
- `one-catalog` — gated and tenant-facing paths live in `process_gate.py` only; `pin-unremovable-duplicates` for the copy in `scratch-tenants.yml`.
- `guards-must-be-able-to-fail` — every check gets a test that forces its violation.
- `validate-on-the-receiving-side` — trailer paths are resolved inside `.agent-rfc/designs|reviews/`; `../` is rejected.
- `minimal-host-dependency` — stdlib only and Python 3.9-compatible: the system `python3` on this Mac is 3.9 without pyyaml, and Claude hooks run whatever `python3` is on PATH.
- `environment-parity` — local commit and CI run the same function over the same records.
- `when-the-fallback-fails` — the Stop hook's second firing cannot loop.
- `failure-mode-visibility` — every block names the file, the missing record, and the command to fix it; `n/a` escapes are listed in the CI summary.
- `ambiguous-signals` — a missing trailer, `n/a`, and a trailer pointing at a missing file are three different messages.
- `docs-match-behaviour` — `docs/process-gates.md`, SPECS tree, OPERATIONS row, CHANGELOG.
