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

**What the CI gate decided, per commit, can be written out:** `process_gate.py ci
--json FILE` writes, alongside the usual report, one record per commit in the range
— its verdict, errors and notes, the design and review it named (or why they did
not resolve), each pillar's kind, each deviation's text hash and approval, each
review pass, and the commits a `Repairs:` trailer names — and every design
document as it stands at the head, because a design is usually closed by a
commit that does not cite it. The file is written whatever the verdict. It is what the portal's Dev workspace is sent, so the portal
shows the gate's verdict rather than reaching its own.

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
next one is tried; when none can, the gate **fails closed where a decision is
being made** — the edit is denied, and the commit, push and CI are blocked — and
says to run `install-ai-stack.sh`. **`session-start` and `stop` warn on stderr
and exit 0 instead**, because they are advisory: neither is the moment anything
is written, and blocking every turn of a session on a broken install would make
the IDE unusable rather than safe. So a machine whose gate cannot run still
starts sessions and ends turns, with a warning each time, and stops the moment
it tries to edit or commit.
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

In a tenant whose hooks were chained (Provisioning, below), a new clone also
names the directory those hooks live in — it is local configuration, so a
clone does not inherit it:

```bash
git config agentsmith.chainHooksPath .husky   # or whatever the repository's hooks directory is
```

## Configuration — `.agenticframework/process-gates.json`

A repository adopts the gates by committing this file. Without it the local
hooks do nothing and `ci` fails — CI running the gate means the repo adopted it,
so a missing config means it was removed.

```json
{
  "gated":            ["scripts/**", "runtime/**", "…", ".agenticframework/process-gates.json"],
  "not_gated":        ["**.md", ".agent-rfc/**"],
  "pillars":          { "mode": "enforce", "allow": [{"check": "P7-pydantic", "path": "runtime/x.py", "why": "…"}] },
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
  checkout or `~/.agent-framework` (KYC Sentinel carries no copy) — and, when it
  is not there, from `$AGENTSMITH_DIR`, then `~/.agent-framework`. A vendored
  tenant runs its own copy of the script, which has no `templates/` or `docs/`
  beside it; the framework it came from does.
- **`pillars`** — optional, default `off`. Whether this repo is held to the
  pillars a script can check, and to evidence in its designs' pillar answers
  (below). `"enforce"` on its own is the same as `{"mode": "enforce"}`.
- **`changelog`** — optional. When present, a pushed range that changes `paths`
  (minus `except`, minus Markdown) must also change `file`. AgentSmith's paths are
  what `scratch-tenants.yml` rebuilds tenants on; a test keeps them equal.

| Repo | Gated (summary) | Levers | CHANGELOG rule |
|---|---|---|---|
| AgentSmith | code, config, and everything a tenant receives | its own | yes — tenant-facing paths |
| AqlaarTeleologyStudio | `apps/`, `services/`, `runtime/`, `scripts/`, `infra/`, `fixtures/`, `.github/`, config files | its own (inherited and extended) | none |
| KYC Sentinel | `agents/`, `workflows/`, `test/`, `scripts/`, `corpus/`, `fixtures/`, `.github/`, root `*.py`, config files | `@framework/` | none |

## Keeping a tenant current — `agentsmith sync`

A tenant holds copies: the gate hooks, the IDE hook configs, the generated rule files, and — a
vendored tenant — the framework's own code. `agentsmith sync` refreshes what this framework owns
in the repository it is run in, and nothing else, then prints the commit. Run twice, the second run
writes nothing.

It refreshes the gate hooks, the provider declaration, the IDE hook configs, the rule files'
managed block and the gates workflow — and, for a vendored tenant, the vendored trees. **The
manifest decides whose file each one is:** written by the framework and untouched, it is refreshed;
edited here since, it is left alone and named; never ours, it is left alone. The exceptions are the
regions the framework owns inside a tenant's own file — the `agentsmith:rules` block and the `hooks`
key in `.claude/settings.json` — which are refreshed whatever else changed around them.

**Its commit passes the tenant's own gates.** `Review: n/a: framework sync <version>` is accepted
while every gated file in the commit matches `.agenticframework/scaffold.json` — the same hash rule
the generated scaffold uses, and a visible note, not silence. A file the tenant edited is not in
that manifest, or no longer matches it, and gets the normal rule with its name. The limit is the
scaffold's: the manifest is not signed, so rewriting a file *and* its hash defeats it, deliberately
and in plain sight.

**A tenant does not have to remember.** `agentsmith-sync.yml`, written at adoption, runs weekly:
it syncs to AgentSmith's latest release and opens a pull request, on one branch, so an ignored
proposal is updated rather than duplicated. It proposes only — merging is a person's decision, and
the tenant's own gates run over the pull request.

An adopted repository is never vendored into, by `sync` or by `agentsmith upgrade`: both read the
manifest's `generated_by`.

## A provider, not a path — `contract/gate/v1`

The gate answers three questions: may this edit happen, may this turn end, and what should a
session know. `contract/gate/v1/protocol.md` publishes them as a protocol — one command, one event
on stdin, one decision on stdout, exit 3 for "cannot run here" — so a repository can be governed
by AgentSmith or by another platform that answers the same way. `agentsmith gate <event>` is this
framework's adapter, and `agentsmith conformance --provider "<command>"` replays the contract's
cases against any provider, in a fixture repository the contract carries.

The contract is versioned apart from the provider: a provider's major release does not reach a
tenant's files.

**A repository names its provider** in `.agenticframework/providers.json`, which `tenant init` and
`tenant adopt` write:

```json
{ "contract": 1, "providers": { "gate": { "command": "agentsmith gate", "version": "^2" } } }
```

For the three contract events the launcher asks `$GOVERNANCE_PROVIDER`, then that command, then
this framework's own paths. **An answer is a decision on stdout**: a provider that prints none has
not answered — it is missing, cannot run here, or is too old to know the event — and the next step
is tried, so naming a provider is additive rather than a migration. `"gate": "none"` declares the
repository ungoverned and never falls back, because that is a different answer from "no provider
could run". `commit-msg`, `sweep` and `ci` are not in contract v1 and keep this framework's own
resolution.

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
- P1 applies — how, naming something in backticks: `scripts/thing.py`,
  `test_it_retries`, `agent.gate.pre_edit`. Or `n/a — why`, `gap — PB-123`, or
  `**deviation D1**`. One line per pillar the registry marks `design`; a missing
  one is rejected.

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

## Six IDEs, one gate

The rules are one implementation. What differs is the shape of the payload an
IDE sends and the shape of the answer it reads, and those live in
`scripts/gate_ides.py` — a seventh IDE is a table entry, a fixture and a test,
never a second gate. Every hook command carries `--ide <name>` (or
`$AGENTSMITH_IDE`); without one it answers in Claude Code's dialect.

| IDE | Config | Deny | Turn blocked | Session context | Config generated |
|---|---|---|---|---|---|
| Claude Code | `.claude/settings.json` | `permissionDecision: deny` | `decision: block` | `additionalContext` | yes — verified by use |
| Cursor | `.cursor/hooks.json` | `permission: deny` | `followup_message` | `additional_context` | yes — vendor docs, 2026-09-17 |
| Antigravity | `.agents/hooks.json` | `decision: deny` | `decision: block` | `additionalContext` | no — schema not verified |
| VS Code Copilot | `.github/hooks/agentsmith.json` | Claude's shape | `decision: block` | `additionalContext` | no — schema not verified |
| Gemini CLI | `.gemini/settings.json` | `decision: deny` | `AfterAgent` deny | `additionalContext` | no — schema not verified |
| Codex | `.codex/hooks.json` | `decision: block` | `decision: block` | `context` | no — schema not verified |

**Cursor has no before-edit hook.** `afterFileEdit` fires after the write and
`beforeReadFile` is a read, so the edit gate is `preToolUse` with
`matcher: "Write"`, which fires before every tool. `sessionStart` there is
fire-and-forget: it can add context but cannot block. `failClosed: true` is set
on the edit gate — Cursor is the one IDE where a hook that crashes still
refuses.

**A config is generated only where its schema is verified.** A file in a shape
nobody has confirmed looks like enforcement and may be ignored in silence,
which is worse than no file. The adapters read and answer all six either way;
`generate-ide-config.py --hooks` writes the two that are confirmed and names
the four that are not.

**A write payload the adapter cannot read is denied**, naming the keys it saw.
Field names are the part most likely to be wrong, and a parser that shrugged
would leave a silent hole in exactly the IDEs nobody here tests daily. Each
IDE's golden payload is in `scripts/test/fixtures/ide-payloads/`: replace one
with a real session's payload and the tests say whether anything else changes.

## Provisioning, and knowing whether it held

A control a tenant has to install by hand is a control most tenants do not
have. `agentsmith tenant init` writes the gate config, the `.githooks`
**armed** (`core.hooksPath` is set), the Claude Code and Cursor hook configs,
the generated rule files, a committed knowledge graph and the artifact stubs.
It refuses to write into the framework's own checkout, and it never replaces a
file the tenant already owns without `--force`.

**The gates are armed only when the hooks are there.** Both commands copy `.githooks/*` out of
the framework — a checkout, `$AGENTSMITH_DIR`, or `~/.agent-framework`, which
`install-ai-stack.sh` fills. An install too old to carry them makes both refuse, naming the
missing hooks and the fix: a `core.hooksPath` pointing at an empty directory would leave the
repository with no hooks at all, the machine's included.

**The hooks a repository already ran keep running.** `core.hooksPath` names one
directory, so arming `.githooks` used to switch off whatever ran before. `tenant
init` and `tenant adopt` record that directory in `agentsmith.chainHooksPath`
(local configuration, never set by default): `commit-msg`, `pre-commit` and
`pre-push` run the gate and then, if it passed, the same-named hook from there
through `.githooks/chain`, with the same arguments and stdin; any other hook it
has gets a one-line stub in `.githooks/`. A prior hook that fails still blocks.
When that directory has a `post-commit`, `agentsmith.autopush` is set to `false`
unless it was already set — the machine's post-commit pushes on its own, and a
repository that was not pushing on commit must not start.

**Vendoring happens before the first commit.** When the repository's prior hooks
include the machine's `post-checkout`, `tenant init` runs it once before writing
the manifest, so the `scripts/`, `runtime/` and `fixtures/` it vendors are part of
the scaffold, vouched for by hash like the rest. Vendored after the first commit,
they would sit under gated paths and need a design and a review.

**The commit that arms the gates.** The scaffold touches gated paths, so it needs a design and
a review like any change. `tenant init` writes the design —
`.agent-rfc/designs/scaffold.md`, scoped to exactly the files it wrote and
`done`, so it covers that commit and authorises nothing after it — and records a
SHA-256 of every file it wrote in `.agenticframework/scaffold.json`. The review
is `Review: n/a: generated scaffold`, which the gate accepts only on the commit
that arms the gates — its parent carries no `process-gates.json`: the
repository's first commit, or an adoption — and only when every gated file in it
matches its hash.
An edited scaffold file, a file the tenant already had, or code added alongside
fails with the file named, and needs a real review. An accepted scaffold is a
note — the commit's verdict is `passed_with_notes`, and CI lists it. The limit:
the manifest is not signed, so someone who rewrites a file *and* its hash defeats
it, once, on the commit that arms the gates, in plain sight in the manifest —
the same kind of escape as `n/a` for a small change. Deleting `process-gates.json`
to reopen that door is itself a change to a gated file.

**An existing repository — `agentsmith tenant adopt`.** It detects before it
writes and prints the plan: the stack, the paths to gate (the top-level
directories and root files git tracks for that stack, or `--gate`), the prior
hooks, and per file whether it is created, merged or left alone. Vendored
AgentSmith code (`scripts/`, `runtime/` as `hooks/post-checkout` wrote them) is
not gated, and the plan says so: it is the framework's, and gating it would make
the next re-vendoring need a design and a review of framework code. Nothing is
written without a yes (`--yes` off a terminal). It merges rather than skips: the
gates into an existing `.claude/settings.json`, the generated rules into an
existing `CLAUDE.md` or `AGENTS.md` between `agentsmith:rules` markers, and an
`## Architecture (target)` section into an existing `docs/DESIGN.md`. It leaves the
repository's CI alone and adds `.github/workflows/agentsmith-gates.yml`, which
runs the gate from a checkout of AgentSmith at the release it names — with the run's own
token, falling back to the `AGENTSMITH_READ_TOKEN` secret only when the provider is
private. An adopted repository is never vendored into, and the
machine's own `post-checkout` and `post-commit` are not chained into it. The
adoption commit carries `.agent-rfc/designs/adoption.md` and the manifest, and
stages exactly what adopt wrote; history before it is `before_adoption`.

`--architecture` (`layered`, `modular-monolith`, `hexagonal`, `microservice`,
`event-driven`) and `--agentic` shape `docs/DESIGN.md`'s Architecture section and
add one session-start line naming the style and its first rule.

The extra modes — `artifacts`, `pillars`, `knowledge_graph` — are provisioned
`off`. A repo switched to `enforce` on day one is refused its first commit for
documents it has not written and a graph it has not built, and the first thing
anyone does then is take the gates out. The design and review gates are live
from the first commit; each of the others is turned on deliberately.

```bash
python3 scripts/verify_system.py --governed
```

lists **every** gap at once — a check that stops at the first one turns
provisioning into a guessing game — and keeps two kinds apart:

- **provisioning gaps**: a file missing, `core.hooksPath` unset, a config that
  gates nothing or declares no registry;
- **not yet proven**: `agentsmith gates run` has never run here, ran for a
  different commit, or ended with failures.

A freshly scaffolded repo is the second kind. "Not installed" and "installed
but never run" are different answers, and sending someone to fix the wrong one
is how a check loses its reader.

**Pillar 5's log is written by the hooks.** The stop gate appends when it
blocks a turn and the sweep appends when it finds a commit that never met a
gate — unresolved `MAJOR` lines in `.agent-history.log`, which is what
`agentsmith check` and session start already read. The same fact is not
appended twice in a row: a stop hook fires at every turn end, and a log that
repeats one line fifty times is one nobody reads.

## The scope a review covered

The knowledge graph existed and nothing made a review use it. Where a repo
declares `knowledge_graph` in its config, a review says which scope it covered:

```bash
python3 scripts/local_knowledge_graph.py --impact --base HEAD
```

It lists the files to read — the change plus **one hop** of dependents, because
two hops out from a shared helper is most of the repo — the lever groups those
files pull in, and a `KG query:` hash. That hash goes in the sign-off, and the
commit gate recomputes it from the commit's own file list.

**The hash is the scope, not the diff.** It covers the impacted file SET, so it
does not go stale on the next keystroke; what it says is "the reviewer looked
at the right files". Whether the review is as fresh as the change is a separate
rule that already exists — the record changes in the same commit.

| `knowledge_graph` | Effect |
|---|---|
| `off` (default) | nothing is asked for |
| `report` | a missing or wrong line is listed; nothing is blocked |
| `enforce` | it is a commit-gate failure |

A missing `knowledge_graph.json` is its own answer — "no graph" and "the scope
matches" are different facts — and session start prints the current change's
scope rather than telling an agent to go and run a script.

## The shell surface

The edit gate watches an IDE's edit tools. The same agent can open a terminal,
so the shell is checked too — in Claude Code through a `Bash` matcher, in Cursor
through `beforeShellExecution`. It refuses four things:

| Refused | Why |
|---|---|
| `git commit --no-verify` / `-n`, `git push --no-verify` | skips the commit gate or the pre-push sweep |
| `git -c core.hooksPath=… <anything>`, `--config-env=core.hooksPath=…`, `GIT_CONFIG_KEY_<n>=core.hooksPath` / `GIT_CONFIG_PARAMETERS` in front of a command | runs that one command with the hooks off |
| `git config core.hooksPath <not this repo's>` — plain, `--add`, `--replace-all`, `set`, any scope | points the repo away from its gates. Re-arming it to `.githooks` is allowed — that is what the sweep asks for |
| `git config --unset[-all] core.hooksPath`, `unset`, `--remove-section core`, `--rename-section core …` | with no hooks path git runs `.git/hooks`, which holds none of the gates: they stop |
| writes to `.githooks/**`, `approvals.jsonl`, `process-gates.json`, an IDE hook config | changing the gate itself, which is a gated path |
| `agentsmith approve` | it asks at a terminal and an agent has none; refusing early beats a confusing failure |

Reading any of those files is fine, and so is asking git what the hooks path
is: `git config core.hooksPath` with no value, `--get`, `--get-all`,
`--get-regexp`, `--list`, `get`, `list`. `git push -n` is a dry run, not a
bypass, and is allowed.

**A command is read past what is in front of it**: `NAME=value` assignments and
`env` before the program, and git's global options (`-C <dir>`, `-c <k=v>`,
`--git-dir`, `--work-tree`) before its subcommand. Until 2026-09-18 either one
hid the command behind it — `GIT_EDITOR=true git commit --no-verify` and
`git -C ../repo commit --no-verify` both went through.

**The line is tokenised the way a shell tokenises it**, so a bypass inside
quotes — a test fixture, an `echo`, a script handed to an interpreter — is an
argument to another program, not a command being run. This rule refused the
repo's own tests for itself until that was fixed.

**Stated limit, and it decides what this is worth.** It reads the command an
IDE is about to run, not what that command does. `bash -c "$(…)"`, a script
file, a shell alias and a Makefile target all reach git without passing
through. So do `git config --edit`, a write straight into `.git/config`, an
`export GIT_CONFIG_…` on an earlier line, and `env` given options of its own. That is why the sweep exists and why the commit and CI gates are the
ones that cannot be talked around: this layer makes the obvious bypass visible
and costly, not impossible.

## Pillars a script can check

Sixteen lines of "P7 applies — it does" is a form, not a control. Where a repo
declares a `pillars` policy, two things change.

**Every `applies` answer names something in backticks** — a path, a test id, a
span name — and the gate resolves it against what the commit tracks: a tracked
path or glob, or text a tracked source file holds. Markdown is searched for
paths but not for text, so a design cannot resolve a token it invented itself.
`n/a` is a reason there is nothing to name, `gap` already names a backlog id,
and a deviation already resolves to an approval, so only `applies` carries
evidence. It proves the token resolves, not that it is the right one — a name
someone else can look up is falsifiable, and prose is not. Checked when the
change is committed, not while it is being designed: a design that names the
file it is about, before that file exists, is doing its job.

**Two pillars are checked in the code**, over the files a commit touches
(`process_gate.py pillars` checks everything the repo tracks, which is the list
to fix, or to seed an allowlist from at adoption):

| Check | Pillar | What fails |
|---|---|---|
| `P2-dependencies` | 2 Build Architecture | a package added to a lock file that the change's `## Dependencies` does not name |
| `P3-tracing` | 3 Tracing and Evaluations | a route (`@app.get`) or CLI command (`@app.command`) whose body opens no span |
| `P7-pydantic` | 7 Stack-Specific Rules | a `@dataclass` built from data the code did not write — unpacked with `**`, or used as a request body. A dataclass built by keyword is an internal value object, not a model |
| `P7-async` | 7 | a route handler declared `def` — a synchronous handler holds the event loop for every other request |
| `P7-ts-any` | 7 | `: any`, `as any`, `any[]` in TypeScript, outside comments |
| `P7-use-client` | 7 | a `.tsx` using hooks or event handlers without `'use client'`, **only** where a `next.config.*` sits above it |
| `P10-gateway` | 10 Cost-Optimization Routing | a provider SDK imported outside `runtime/llm_gateway.py`, `provider_dispatch.py` or `cost_router.py` |
| `P12-secrets` | 12 Secrets and Credentials | a credential-shaped string in any tracked file. A line that must hold one — a redaction test — carries `# not-a-secret: <why>` on it or on the line above |

Test files are not first-party for the code-shape checks: a fixture is not a
model and a test double is not a route. `P12-secrets` opts back in, because a
real key committed in a test is leaked exactly as far as one in a module.

A check runs only while its pillar is marked `mechanical` in the registry, and
only in a repo whose policy is `report` or `enforce` — the same three modes as
`artifacts`.

**The allowlist only ratchets.** `allow` entries name one check and one path and
say `why`; a repo seeds it when it first declares a policy. After that a new
entry needs `"approval": "A-xxxxxxxx"` from `agentsmith approve`, the mode may
only strengthen, and dropping the key counts as weakening it — otherwise the
allowlist could be widened by switching the policy off and on again.

**A new check cannot be allowlisted into existence.** The ratchet asks for an
approval on any entry a repo did not already have, and it cannot tell "this
check is new" from "this repo is giving itself a pass". So a repo turning on a
new check fixes what it finds, or the owner approves each exemption. AgentSmith
fixed ten things to turn these on.

**Stated limits.** `P7-pydantic` cannot see a dataclass filled field by field
from a parsed payload. `P3-tracing` finds only entrypoints a decorator
declares, and reads a handler that delegates to a tracing helper as untraced.
`P7-ts-any` reads lines, not a parse, so the text inside a string counts.
`P12-secrets` matches shapes, not issuers: a credential shaped like nothing on
the list is not found. Every design question still gets asked.

## Cross-references

A pointer into another document by a number rots when the number is a position:
the next edit of that document renumbers it. On the lines a change ADDS, the
gate reads each pointer — a Markdown file name followed by something with a
digit in it, such as `SPECS.md §23`, `docs/PRODUCT_ARCHIVE.md 4.14` or <!-- xref: example -->
`CHANGELOG.md` 1.1.0 — and looks in the document it names. <!-- xref: example -->

- **A line number** (`DESIGN.md#L120`) is always refused. <!-- xref: example -->
- **A document this repo does not have** is refused; name it by its path from
  the repo root.
- **Otherwise the target must define the token as a name:** a heading that
  contains it, or the first word of a table row or of a bold list item.
  Fenced code does not count.
- **A number in that first place** — `5.10`, `2.3b`, `E.1` — is a name only in
  a document the registry marks `append_only` (the archive, the review log,
  the changelog), whose entries never move. Anywhere else it numbers a heading
  or a row, which is a position, and is refused.

Name the heading instead: `docs/DESIGN.md › Section Name`. Lines already in the
repo are left alone — they go as each document moves — and a line that must
show a bad pointer as an example carries `<!-- xref: example -->`. The rule
follows the `artifacts` mode above.

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
catches it on the way out, and GitHub offers it on a **public** repository at no
cost — so requiring the `process-gates` check on `main` is what turns "reported"
into "refused". The local re-checks below exist because that protection is a
repository setting nobody can rely on being present, not a substitute for it.

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
summary, so the escape stays visible. **`Review: n/a: generated scaffold`** is
accepted at any size, but only for the untouched commit that arms the gates —
see Provisioning, above.

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

- **The CI gate refuses a push — unless you are an admin.** The check
  `Process gates (design + review)` — copy it exactly; GitHub matches a required
  check by that string — is required on `main` since 2026-09-29, so a push
  or a pull-request merge whose head fails it is rejected; `allow_force_pushes` and
  `allow_deletions` are both off as well. Whether an admin bypasses *those* too
  is untested — a force push to `main` is not an experiment worth running to find
  out — so assume the admin path bypasses everything until someone verifies it. What is *not*
  enforced: `enforce_admins` is false and no pull request is required, so the
  owner — the only admin — can still push directly to `main` past a failing
  check. That half is deliberate, not an oversight: enabling it ends direct
  pushes to `main` for the person who does all of them. It stays open in
  `docs/PRODUCT_BACKLOG.md` with its trigger. `strict` is also off, so a branch
  that passed the check against an older `main` can still merge without being
  brought up to date — the check proves that commit was compliant, not that it
  still is on top of what landed since.

  Before 2026-09-29 no branch protection was possible at all: it needs GitHub
  Pro for a private repository (verified 2026-09-14 — the API answered "Upgrade
  to GitHub Pro or make this repository public"), and this repository was
  private until 2026-09-27.
- **The pre-commit guardrails skip what the tenant did not write.** Guardrails 1–3
  (AI markers, empty catch/except, direct `cost_router` imports) do not run over a
  staged file that `.agenticframework/scaffold.json` records **and** that still
  hashes to what the manifest recorded — the code AgentSmith vendored, unchanged.
  A tenant cannot fix `scripts/process_gate.py`, and being asked to blocked every
  scaffolded repository's first commit until 2026-09-29. Edit a vendored file and
  it is checked again, because the hash no longer matches. The rules still run
  over that code in AgentSmith's own suite, where it can be fixed
  (`scripts/test/test_bare_except_tree.py`, `scripts/test/test_vendored_markers.py`).
  Guardrail 4 is not skippable: it asks whether the repository has an RFC at all,
  which is not a per-file question.

  Every failure of the check that grants the skip — missing
  `scripts/vouched_files.py`, missing `python3`, missing or unreadable manifest —
  vouches for nothing, so the hook checks everything. A skip is only ever granted
  by a hash that matched.

- **Only the edit gate fails closed, and only in some IDEs.** If `python3` is
  missing or the script dies, the edit gate denies — but whether an IDE honours
  that is the IDE's to decide, and `fail_closed` in `templates/governance.json`
  records which do. **Claude Code** and **Cursor** fail closed, by two different
  mechanisms: Claude through `.githooks/process-gate`'s pre-edit fallback
  printing a deny, Cursor through the `failClosed` key in its generated
  `.cursor/hooks.json`. **Antigravity, Copilot, Gemini and Codex fail open by
  design** — an edit there lands when the gate cannot run, and the commit, push
  and CI gates are what hold. `scripts/test/test_fail_closed_declared.py` checks
  each declaration against its own mechanism, so this table cannot go stale
  quietly.

  The session-start and stop hooks cannot fail closed anywhere: Claude Code
  treats their failure as a non-blocking error, and a stop hook that blocked
  without being able to read `stop_hook_active` could loop forever. The commit
  and CI gates still hold.
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
  hook provision none of it. Recorded in `docs/PRODUCT_BACKLOG.md`.
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

`tenant init` and `tenant adopt` set the first when they chain a `post-commit`
and it is unset.

The only alternative used to be `git -c core.hooksPath=/dev/null commit`, which
also skipped `pre-commit` and `commit-msg`.
