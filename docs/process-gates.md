# Process gates

Design before code and review before merge are checked by machine in this
repository, not left to whoever — or whatever agent — is doing the work.

`docs/design-review-checklist.md` and `docs/review-levers.md` existed for weeks
and were still skipped, for two reasons that more documentation could not fix:
no agent session in this repo ever had them in context, and nothing checked.
Every gate below calls one script, `scripts/process_gate.py`, so the rules are
defined once; what each repository gates is declared in its own
`.agenticframework/process-gates.json`. The same script serves AgentSmith and
the tenants that adopted it — AqlaarTeleologyStudio and KYC Sentinel. Designs:
`.agent-rfc/designs/process-gates.md`, `process-gates-tenants.md`.

## What is checked, where

| Layer | Runs | Blocks | Can be skipped by |
|---|---|---|---|
| **Session context** — `.claude/settings.json` SessionStart | every Claude Code session | nothing — states the rules and the pillars a design must answer, lists active designs, adds the repo's own `extends.session_start` lines, warns if the commit gate is not armed or gate spans are not being emitted | not using Claude Code |
| **Edit gate** — PreToolUse on Edit/Write/MultiEdit/NotebookEdit | before each file edit | an edit to a gated path that no complete, *active* design note covers | editing through a shell command (the next three layers still see it) |
| **Stop gate** — Stop | when an agent ends its turn | ending with uncommitted gated changes that have no clean review record newer than them | a second stop in a row (it warns instead of looping) |
| **Commit gate** — `.githooks/commit-msg` | `git commit` (including `--amend`), in a clone that armed it | a commit touching gated paths without resolving `Design:` and `Review:` trailers | not arming it, `--no-verify`, and history rewrites git runs without `commit-msg` — rebase picks, cherry-picks (CI still sees all of them) |
| **Sweep** — `.githooks/pre-commit`, `.githooks/pre-push`, session start, stop | every commit, push, session start and turn end | a push while any commit that never passed the gate is unrepaired; the next commit must be its repair | nothing local: the sweep is what catches `--no-verify`, an unarmed clone, a rebase and a cherry-pick |
| **CI gate** — Self-Test job `process-gates` | every push and pull request | a pushed range with any non-compliant gated commit, or tenant-facing changes without a CHANGELOG update | nothing in the repo — but it reports red after a push rather than refusing it (below) |

**What no gate can check** is whether the design was *good*. The gates prove a
design exists, is scoped to the change, and cites real levers; that a review
ran until a pass found nothing; and that the review is as fresh as the change.
Quality still needs a reviewer who is not the builder.

## What the gate runs on

The gate follows the pillars it enforces — Pydantic V2 models (pillar 7) and a
span per decision (pillar 3) — so it needs the framework environment:
**Python 3.11+ with `pydantic` and `opentelemetry-sdk`**, which
`install-ai-stack.sh` builds at `~/.agent-framework/.venv`.
`.githooks/process-gate` tries, in order: `$AGENTSMITH_PYTHON`,
`$AGENTSMITH_DIR/.venv/bin/python`, `~/.agent-framework/.venv/bin/python`, then
the repo's own `.venv`. An interpreter that cannot run the gate exits 3 and the
next one is tried; when none can, the gate **fails closed** — the edit is
denied, the commit and push are blocked — and says to run `install-ai-stack.sh`.
CI installs `scripts/requirements-gate.txt`, the list that travels with the
vendored gate.

Decisions are spans: `agent.gate.<event>` with `agent.role=process-gate`, the
decision, the IDE and the repo. A hook must not wait on a collector, so spans
are written to `~/.agent-framework/state/gate-spans/` as OTLP batches and
shipped at session start, stop and sweep with a one-second timeout. Session
start reports which of the four states holds: exported, not exported (no
endpoint), not exported (collector down), or not emitted (no runtime).

## The rules registry

`templates/agent-rules.yaml` is the one source. `generate-ide-config.py
--registry` compiles it to `templates/governance.json`, which the gate reads
(hooks have no pyyaml) and which says, per pillar, where it is enforced:

- `design` — the design must answer it;
- `review` — the sign-off must attest it;
- `mechanical` — a script checks it.

A repo points at a registry with `registry` in its config (default
`@framework/templates/governance.json`) and adds its own pillars, stack rules or
session-start lines under `extends`, which re-syncing never overwrites. A
missing or invalid registry blocks, exactly as a broken config does: a gate that
cannot read its rules must not check fewer of them.

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

## Configuration — `.agenticframework/process-gates.json`

A repository adopts the gates by committing this file. Without it the local
hooks do nothing and `ci` fails — CI running the gate means the repo adopted it,
so a missing config means it was removed.

```json
{
  "gated":            ["scripts/**", "runtime/**", "…", ".agenticframework/process-gates.json"],
  "not_gated":        ["**.md", ".agent-rfc/**"],
  "levers_doc":       "docs/review-levers.md",
  "design_checklist": "@framework/docs/design-review-checklist.md",
  "changelog":        { "file": "CHANGELOG.md", "paths": ["hooks/**", "…"], "except": ["scripts/test/**"] }
}
```

- **`gated` / `not_gated`** — globs; `**` crosses directories. The config must
  gate itself, or deleting a line would switch a gate off unreviewed; a config
  that does not is rejected, and a broken config blocks every commit and every
  edit except to itself.
- **`levers_doc` / `design_checklist`** — a repo path, read at the commit being
  checked (OTS validates against its own, extended `docs/review-levers.md`), or
  `@framework/<path>`, read beside the running `process_gate.py` — the AgentSmith
  checkout or `~/.agent-framework` (KYC Sentinel carries no copy). **Only for
  installed-mode tenants:** in a vendored tenant the running script is the
  tenant's own copy, so `@framework/` resolves to the tenant repo. Point
  `levers_doc` there at the tenant's own file; `design_checklist` is only shown
  in messages, never read, so `@framework/` is harmless for it.
- **`changelog`** — optional. When present, a pushed range that changes `paths`
  (minus `except`, minus Markdown) must also change `file`. AgentSmith's paths are
  what `scratch-tenants.yml` rebuilds tenants on; a test keeps them equal.

| Repo | Gated (summary) | Levers | CHANGELOG rule |
|---|---|---|---|
| AgentSmith | code, config, and everything a tenant receives | its own | yes — tenant-facing paths |
| AqlaarTeleologyStudio | `apps/`, `services/`, `runtime/`, `scripts/`, `infra/`, `fixtures/`, `.github/`, config files | its own (inherited and extended) | none |
| KYC Sentinel | `agents/`, `workflows/`, `test/`, `scripts/`, `corpus/`, `fixtures/`, `.github/`, root `*.py`, config files | `@framework/` | none |

## Finding the script — `.githooks/process-gate`

Every caller — the three Claude Code hooks and `.githooks/commit-msg` — runs
`.githooks/process-gate <subcommand>`, which looks for `process_gate.py` in this
order and runs the first it finds, relative to the repository git reports for
the current directory (not the Claude Code session's project, which can be a
different repo):

1. `<repo>/scripts/` — AgentSmith, and vendored tenants (OTS);
2. `$AGENTSMITH_DIR/scripts/` — a framework checkout (KYC's CI, and KYC locally
   when `AGENTSMITH_DIR` is exported);
3. `~/.agent-framework/scripts/` — a machine install (re-run
   `install-ai-stack.sh` after upgrading AgentSmith).

If none exists: the edit gate denies, the commit is blocked, CI fails; the
session-start and stop hooks warn. `.githooks/commit-msg`, `.githooks/process-gate`
and the `hooks` block of `.claude/settings.json` are identical in every repo that
adopted the gates.

## Rolling out to a tenant

1. **Design and review records in the tenant** — its rollout commit is gated by
   the config it adds, like any other.
2. **Config** — `.agenticframework/process-gates.json` for its layout; gate the
   config, `.githooks/**` and `.claude/settings.json`.
3. **Hooks** — copy `.githooks/commit-msg` and `.githooks/process-gate` from
   AgentSmith; merge the `hooks` block of AgentSmith's `.claude/settings.json`.
4. **The script** — vendored tenants get `scripts/process_gate.py` (and add it to
   `scripts/ruff.toml`'s excludes); installed-mode tenants need nothing.
5. **CI** — a `process-gates` job with `fetch-depth: 0` running
   `python3 <gate> ci --base <before or PR base> --head <sha>`; installed-mode
   tenants check out the framework first and run `$AGENTSMITH_DIR/scripts/process_gate.py`.
6. **Arm each clone** — `git config core.hooksPath .githooks`.

## The two records

**Design note** — `.agent-rfc/designs/<slug>.md`, written *before* the code.
`agentsmith design new <slug> --scope <glob>` writes this skeleton in any IDE:

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

## Pillars
- P1 applies — how. Or `n/a — why`, `gap — PB-123`, or `**deviation D1**`.
  One line per pillar the registry marks `design`; a missing one is rejected.

## Deviations
none
# or: - D1 — P3 — what and why — approval: A-0123abcd

## Dependencies
none
# or the packages added, direct and transitive (diff the lock file).

## Levers
- `one-catalog` — why it applies and what the design does about it.
```

## Permission to deviate

A design may break a rule only with the owner's approval, recorded by

```bash
agentsmith approve .agent-rfc/designs/<slug>.md D1 --statement "why"
```

which asks at the **terminal** (`/dev/tty`) and appends to
`.agenticframework/approvals.jsonl`. Every coding agent runs shell commands
without a controlling terminal, so an agent cannot record one: it has to ask
you. The gate then requires each active deviation to resolve to an approval
naming that design and that deviation, so until you approve, every edit in the
design's scope stays denied.

What this cannot prevent is a person approving something they should not — it
makes the deviation visible, attributed and dated, which unwritten exceptions
never were.

`.agenticframework/approvals.jsonl` is never edited directly: the edit gate
denies it even when an active design's scope names it. Committing one is a
one-line gated change, so `Design: n/a: owner approval` is the trailer for it,
and CI lists that escape in its summary like any other.

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
The record is clean only when its last pass reports `findings: 0`, passes are
numbered 1, 2, 3… with none skipped, **and** it ends with the sign-off block
from `docs/validation-checklist.md` Step 4 — the seven group lines, each marked
checked, n/a with a reason or gap with a backlog id, plus Tests added,
Mutation-checked, Fixtures re-pinned and Gates run. Passes say what was looked
at; the sign-off says what was decided.

## One artifact per type

A repo grows a second backlog, a third review file and four READMEs, and then
no agent knows which one governs. `templates/governance.json → artifacts` names
one file per type — readme, backlog, archive, design, review log, user manual,
and optionally a changelog and a manual test script — and a repo adjusts the
paths in `extends.artifacts`, where `path: null` says it has none.

`process_gate.py artifacts` reads what git tracks and reports three things: a
second file of a type (by name pattern), a Markdown file that is neither an
artifact nor declared reference documentation, and a missing required artifact.
It runs standalone, in the sweep and in CI.

**The mode is per repo**, in `.agenticframework/process-gates.json`:

| `artifacts` | Effect |
|---|---|
| `off` (default) | Nothing is checked — the repo has not declared a layout |
| `report` | Every problem is listed; nothing is blocked |
| `enforce` | A problem fails the commit, the sweep and CI |

A repo consolidating its documents runs `report` until it has finished, then
switches to `enforce` in the same change. Blocking first would block the
migration that fixes it.

## Cross-references

A pointer into another document's numbering rots the next time that document is
edited. On the lines a change ADDS, the gate refuses `SPECS.md §23`,
`DESIGN.md#L120` and the like; name the document, or a heading inside it. <!-- xref: example --> Lines
already in the repo are left alone — they go as each document moves — and a line
that must show a bad pointer as an example carries `<!-- xref: example -->`. The
rule follows the `artifacts` mode above.

## Where the records live

`records` in the repo's config picks one convention, and the gate reads only
that one:

- **`legacy`** (default) — a file per change: `.agent-rfc/designs/<slug>.md`,
  `.agent-rfc/reviews/<slug>.md`, named by the trailers.
- **`single`** — a section per change in the design artifact, entries in the
  review log:

  ```
  ## Active change: worker-retry

  ```governance
  status: active
  scope:
    - services/worker/**
  ```

  ### Problem … ### Approach … ### Pillars … ### Deviations … ### Dependencies … ### Levers
  ```

  with `## worker-retry — Pass N — findings: K` and `## worker-retry — Sign-off`
  in `docs/REVIEW_LOG.md`, and trailers `Design: docs/DESIGN.md#worker-retry`,
  `Review: docs/REVIEW_LOG.md#worker-retry`.

The rules are identical either way: the same pillars, deviations, dependencies,
passes and sign-off. A section is normalised into the shape the checkers already
read, so there is one set of rules, not two.

## The sweep — what catches a bypass

The commit gate is skippable: `git commit --no-verify`, a clone that never ran
`git config core.hooksPath .githooks`, a rebase or cherry-pick (git runs no
`commit-msg` for those), or git run from a shell no IDE gates. Branch protection
would catch it on the way out, and a private repository on a free plan does not
have it — so the check runs again, locally, at every touchpoint.

`process_gate.py sweep` re-checks every commit reachable from a local branch
that it has not checked before, using the same per-commit code the CI gate uses.
`.git/agentsmith/verified` records what passed, so a sweep costs one pass over
what is new. It runs from `.githooks/pre-commit` (report only), `.githooks/pre-push`
(blocking), every session start and every turn end.

The first sweep in a repo **records where it started and checks nothing**: a
repo adopting the gates has history that could not comply, and failing all of it
would say nothing useful. It prints how many commits it recorded.

**Repairing, never rewriting.** A commit that skipped the gate is not amended
away. The next commit carries the design and review records that cover those
changes and a trailer naming what it repairs:

```
fix(worker): bring the bypassed change under review

Design: .agent-rfc/designs/worker-retry.md
Review: .agent-rfc/reviews/worker-retry.md
Repairs: 9f2c1ab
```

Until then, `commit-msg` refuses any commit that does not repair the outstanding
ones, and `pre-push` refuses the push. `agentsmith gates repair` lists them and
what each lacks. The trailer is resolved by git, so it cannot name a commit that
does not exist.

Every sweep also re-arms `core.hooksPath` when it finds it unset in a repo that
carries `.githooks/process-gate`, and says that it did — an unarmed clone is one
of the ways commits skip the gate in the first place.

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
| `… is a gated path and no active design note covers it` | write the design note (`agentsmith design new <slug> --scope <glob>`), or add the path to an active design's `scope` if it belongs to that work |
| `'## Pillars' does not answer P3 …` | answer it: `applies — how`, `n/a — why`, or `gap — <backlog id>` |
| `deviation D1 has no owner approval` | ask the owner; they run `agentsmith approve` and you paste the id into the entry |
| `records no '## Sign-off' block` | sign off per group (validation-checklist Step 4) |
| `the rules registry … does not exist` | re-sync the framework (`agentsmith upgrade`), or regenerate it with `generate-ide-config.py --registry` |
| `no interpreter could run …` | run AgentSmith's `install-ai-stack.sh`, or set `AGENTSMITH_PYTHON` |
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
  push adds, and the sweep records the history it finds on first run as its
  starting point rather than failing it.
- **The sweep's hooks are `.githooks/`.** A repo that runs the machine-wide
  `~/.git_templates` hooks without adopting `.githooks` gets the sweep at
  session start and in CI, but not at commit or push time. Adopting the gates
  (`git config core.hooksPath .githooks`) is what arms those two, and every
  sweep re-arms it when it finds it unset.
- **The sweep sees this machine's clone.** It walks local branches, not remote
  refs: what someone else pushed is their machine's and CI's business. A commit
  that reaches a remote without passing anything is caught by CI, and by the
  sweep on the next machine that fetches and works on it.
- **New tenants do not get the gates automatically.** OTS and KYC Sentinel
  adopted them by hand (above); `agentsmith tenant init` and the post-checkout
  hook provision none of it. Recorded in `FIXES_AND_CLEANUP.md`.
- **An installed-mode tenant's local gates follow the framework it finds.** With
  no `AGENTSMITH_DIR`, KYC's hooks run `~/.agent-framework`'s copy — as current
  as the last `install-ai-stack.sh`. Its CI runs the framework checkout's.

## Tenant repositories: auto-push without disabling hooks

`hooks/post-commit` auto-tags a `feat`/`fix`/`perf`/`refactor` commit and pushes
it when the branch tracks a remote. To keep the tag and skip the push:

```bash
git config agentsmith.autopush false    # this repo
AGENTSMITH_AUTOPUSH=0 git commit …      # one commit
```

The only alternative used to be `git -c core.hooksPath=/dev/null commit`, which
also skipped `pre-commit` and `commit-msg`.
