---
status: active
scope:
  - scripts/process_gate.py
  - scripts/gate_models.py
  - scripts/gate_pillars.py
  - scripts/gate_tracing.py
  - scripts/test/test_gate_*.py
  - scripts/test/test_cli_approve.py
  - scripts/test/test_generate_ide_config*.py
  - .github/scratch-tenants/**
  - requirements*.txt
  - requirements*.lock
  - scripts/generate-ide-config.py
  - scripts/map_codebase.py
  - scripts/local_knowledge_graph.py
  - scripts/verify_system.py
  - scripts/test/test_process_gate.py
  - scripts/test/test_governance_*.py
  - scripts/test/test_ide_hook_adapters.py
  - templates/agent-rules.yaml
  - templates/governance.json
  - .githooks/**
  - hooks/**
  - .claude/settings.json
  - .cursor/hooks.json
  - .gemini/settings.json
  - .codex/hooks.json
  - .agents/hooks.json
  - .github/hooks/**
  - .github/workflows/**
  - workflow-templates/**
  - scripts/test/conftest.py
  - scripts/test/test_workflow_template_wiring.py
  - .agenticframework/process-gates.json
  - runtime/cli.py
  - runtime/machine/**
  - scripts/requirements-gate.txt
  - install-ai-stack.sh
---
# Governance enforcement: rules followed without exception, in any IDE

Owner decisions: OTS `docs/PRODUCT_BACKLOG.md` § "PB-104 scope", 2026-09-15 (rounds 1–2).
Tenant counterpart: OTS `.agent-rfc/designs/governance-enforcement-tenant.md`.
**Status: approved 2026-09-15.** Deviations D3 and D4 were approved by the owner in chat. D1/D2 were withdrawn: the owner chose option B, so hooks run in the framework environment with Pydantic and OTel. Chat was the bootstrap channel because `agentsmith approve` doesn't exist yet. Once G1 lands, the owner re-records D3/D4 with `agentsmith approve` so the gate can resolve them.

## Problem

AgentSmith exists so that governed repos get it right the first time. In practice only what a gate checks is followed; what the rule files say is followed from memory.

Evidence from OTS template slices S1/S2, 2026-09-15:
- no OTel spans;
- dataclasses instead of Pydantic;
- the knowledge graph was not queried;
- only a subset of CI gates was run;
- plans were skipped;
- no sign-off block;
- transitive dependencies were not approved.

Root causes:

1. **Rule files are advice, not enforcement.** `CLAUDE.md`, `.cursorrules`, `AGENTS.md` and `GEMINI.md` are read, or not.
   - Only Claude Code has hooks wired (`.claude/settings.json`).
   - Cursor, Antigravity, VS Code Copilot, Gemini CLI and Codex get no early gate. Each of them now supports hooks.
2. **The gate checks levers, not pillars.**
   - `check_design` requires `## Problem / ## Approach / ## Levers` only.
   - No design ever has to answer "tracing? models? dependencies? KG?".
   - No design has to ask the owner for permission to deviate.
3. **Bypasses go unnoticed.**
   - `git commit --no-verify`, an unarmed clone, or `-c core.hooksPath=` skip `commit-msg`.
   - CI reports only after the push, and without paid branch protection cannot refuse it.
   - The owner ruled out a GitHub dependency: enforcement must live in the IDE and on the machine.
4. **CI steps that pass on failure.** Tenant workflows carry `continue-on-error` / `|| true` on governance steps (OTS `ci-python-fastapi.yml` lines 111, 128, 134).
5. **The KG is optional.**
   - It isn't built at onboarding, isn't committed in tenants, and its freshness isn't blocking.
   - Reviews re-read files instead of querying impact, which is slow and token-heavy.
6. **Too many overlapping documents.**
   - AgentSmith has `SPECS.md` + `OPERATIONS.md` + `FIXES_AND_CLEANUP.md` + `ReviewFindings-*` + `TestCoverageReview-*` + `TestbedFeedback-*` + `.agent-rfc/{designs,reviews}` + `docs/superpowers`.
   - OTS has two READMEs, two `CRITICAL_REVIEW_*`, a TODO plan, 22 specs + 31 plans, and review sections inside the backlog.
   - Agents don't know which one governs.
7. **One source of rules, missing downstream.** OTS has no `templates/agent-rules.yaml`, so its rule files were hand-edited and the drift check prints "skipped" (`ambiguous-signals`).

## Approach

Seven slices, each designed, built, reviewed (passes until 0) and signed off before the next. The tenant (OTS) side of each slice lands in the same session (owner: "implement both sides together").

### Owner decisions — 2026-09-16 (sequencing)

Recorded after G1 shipped; they change the order and three of the slices.

**Each slice keeps its own review record** — `reviews/governance-enforcement-<slice>.md` —
because the gate checks one record per change: passes numbered 1..N, ending at 0 and a
sign-off. G1's is `reviews/governance-enforcement.md`.

**Order.** G3 → G5a → G6 → G2 → G4 → G7, with the document migrations (G5b) and the
scope-derived pillar subset trailing their prerequisites:

1. **G3 — the sweep, next.** It is the backstop every other layer leans on, it needs no vendor
   cooperation, and an uncommitted unreviewed tree survived a whole session on 2026-09-16 because
   nothing checked between the edit gate and the end of the turn.
2. **G5a — the artifact registry, the `artifacts` check, `records: single` and the
   cross-reference rule, as code.** Split from the migrations below: enforcement must not wait
   behind renaming references in three repos.
3. **G6 — mechanical checks**, starting with the two pillars OTS actually violated (tracing,
   Pydantic models) and the resolution of evidence tokens (below).
4. **G2 — IDE adapters.** 5. **G4 — knowledge-graph impact.** 6. **G7 — onboarding.**
   **G5b — migrations: OTS first** (its sprawl is what confuses agents today), **AgentSmith
   second** (the framework must follow the rule it ships, or the `artifacts` check never runs
   against the repo that defines it).

**Pillar answers carry evidence (G1 amendment, built in G6).** `P<id> applies` must name something
resolvable — a path, a test id, a span name — not prose. A prose "applies" is unfalsifiable, which
is how sixteen lines become ritual. G6 resolves the token (does that file/test/span exist?). The
scope-derived subset stays on the roadmap for **after G4**, because deriving it needs the impact
query: a wrong subset silently excuses a pillar, and a question never asked is invisible. Evidence
tokens survive that change — the two compose.

**Cross-references are minimised, and never by section number.** No pointer into another
artifact's numbering (`SPECS.md §23`, `OPERATIONS.md §9`, `DESIGN.md#L120`) <!-- xref: example -->: numbers move on every
edit. Name the document, or a heading within the same document. Enforced on **new and changed
lines first**; existing pointers are cleaned up as each document is migrated in G5b, because
consolidation is exactly when stale pointers multiply.

**Documentation is for humans. The knowledge graph and the code are the agent's sources.** An
agent designing a change, fixing a defect or scoping a review reads the graph and the code; prose
explains the system to a person. This is why G4's freshness is blocking rather than advisory, why
session start carries a graph summary instead of a reading list, and why the artifact set stays
small: every document is a human's map, not an agent's index.

**Two agents in one checkout stays a future extension** (owner, 2026-09-16), with the evidence
recorded in the backlog: on 2026-09-16 a `mutation_check` run in a second session rewrote tracked
files under this one, and the stop gate's findings changed between turns.

### G1 — Rules registry, design-time pillars and deviations

- **Hook runtime (owner option B, 2026-09-15).**
  - Every gate entrypoint runs in the framework environment. `.githooks/process-gate` resolves the interpreter in this order: `$AGENTSMITH_PYTHON`, `$AGENTSMITH_DIR/.venv`, `~/.agent-framework/.venv`, then the repo's own `.venv`; an interpreter that cannot run the gate exits 3 and the next is tried, with the hook's stdin read once and replayed.
  - It requires Python ≥ 3.11 with `pydantic` and `opentelemetry-sdk` importable. Both are already in `requirements.txt` / `requirements.lock`, so nothing is added.
  - No usable interpreter means the gate fails closed: pre-edit denies, pre-commit / commit-msg / pre-push block, session-start and stop warn (the IDE can't block there). Each message names `install-ai-stack.sh`.
  - Measured on 2026-09-15: import cost ~0.15 s warm, versus 0.04 s for stdlib.
- **Models.** Pydantic V2 models validate, on the receiving side, IDE payloads (per-IDE input models → one `GateEvent`), `governance.json`, `process-gates.json`, approvals and review sign-offs. The current hand-rolled front-matter parser stays only for the legacy records mode.
- **Spans.**
  - Every decision emits `agent.gate.<event>` through `runtime/tracing.py` (`agent_span`, identity processor, redactor). `agent_span` namespaces its keyword attributes, so they are `agent.decision`, `agent.rule`, `agent.ide`, `agent.repo`, `agent.exit_code`, alongside `tenant.id` and `agent.role=process-gate`. The decision is recorded by the code that decides, never inferred from the JSON a hook printed, and `agent.ide` comes from `AGENTSMITH_IDE` (G2 sets it per adapter) rather than being assumed.
  - Export is **spooled**: `scripts/gate_tracing.py` holds a file span exporter that writes each batch as an OTLP protobuf `ExportTraceServiceRequest` (the bytes OTLP/HTTP would send) to `$AGENTSMITH_STATE_DIR/gate-spans/` (default `~/.agent-framework/state/gate-spans/`).
  - Shipping happens only at `session-start`, `stop` and `sweep`, never in `pre-edit`. Each batch is POSTed as-is to the resolved OTLP traces endpoint (`runtime/otlp.py`) with a 1 s timeout. A 2xx deletes the file; anything else keeps it.
  - With no endpoint configured, the spool is kept and session start says "gate spans NOT exported (no endpoint) — N batches spooled" (`ambiguous-signals`).
  - Spool size is capped; oldest-first drop is counted and reported, never silent.
- **`templates/governance.json`** is the machine-readable registry. It is JSON so that hooks and non-Python tooling read it without pyyaml. It is generated from `templates/agent-rules.yaml` by `generate-ide-config.py --registry`, with a blocking drift test, so there is still one source. It reaches tenants the way `agent-rules.yaml` does (changelog paths, scratch-tenants, `agentsmith upgrade`). It holds:
  - `pillars[]`: `id`, `name`, `design_question`, and `check`, one of:
    - `design` — answered in the design;
    - `mechanical` — a script checks it (G6);
    - `review` — attested in the sign-off.
  - `records`: the design sections, the sign-off shape, and the "ask the owner" block every rule file carries.
  - `artifacts{}`: the single-artifact registry (G5, not yet present).
  - `ides{}`: hook adapter targets (G2, not yet present).
- **No new per-repo file.** `.agenticframework/process-gates.json` gains:
  - `registry`, defaulting to `@framework/templates/governance.json`: the vendored copy in a vendored tenant, the framework's in installed mode, so KYC Sentinel needs no change;
  - `extends`, a tenant-owned overlay that re-sync never overwrites (same rule as `models.yaml`). It carries only what something reads: extra pillars, and extra session-start lines. (Stack rules and the test command were dropped from the model — a declared key nothing consumes is a rule a tenant would believe is in force.)

  A registry that is missing or invalid is a config problem, and it blocks as a broken config does today.
- **`check_design` also requires:**
  - `## Pillars`: one line per registry pillar whose `check` includes `design`, each one of:
    - `P<id> applies — how`
    - `P<id> n/a — why`
    - `P<id> gap — PB-/backlog id`

    A missing pillar fails and names the pillar.
  - `## Deviations`: either `none`, or one entry per deviation: `D<n> — rule (P<id> / lever / artifact) — what and why — approval: <approval id>`.
  - `## Dependencies`: direct packages added, plus the `uv lock` / `npm` transitive diff.
- **Approvals.** `.agenticframework/approvals.jsonl` is append-only, one JSON object per approval: `id`, `design`, `deviation`, `approver`, `approved_at`, `channel`, `statement`. It is written only by `agentsmith approve`:
  - The command reads the confirmation from **`/dev/tty`**, never stdin. Agent shell tools in Claude Code, Cursor, Antigravity, Copilot, Gemini and Codex run without a controlling terminal, so the command cannot complete there.
  - `approvals.jsonl` is never editable through a design: the edit gate denies it whatever any design's scope says, because an agent that could write the file could approve its own deviation. (Denying the `agentsmith approve` *command* in each IDE's shell hook is G2; the terminal requirement already blocks it.)
  - `check_design` resolves each deviation's approval id and fails if it is missing or doesn't match the design and deviation.
  - Stated limit: a human can still type approval at a terminal on the agent's behalf. The record makes that visible and attributable; it can't make it impossible.
- **Edits wait for approvals.** A design with an unapproved deviation isn't "complete", so the existing pre-edit, stop and commit gates already deny edits in its scope. No new blocking path is needed (`single-source-of-truth`).
- **Review sign-off parsed.** A clean review needs the last pass at 0 findings **and** a `## Sign-off` block with:
  - the 7 group lines (`checked` / `n/a — reason` / `gap — id`);
  - `Tests added`, `Mutation-checked`, `Fixtures re-pinned`, `Gates run`, `KG query` (G4) and `Declared gaps`.
- **Every generated rule file** (CLAUDE.md, AGENTS.md, `.cursorrules`, GEMINI.md, copilot-instructions, Antigravity skills) gains one "Design start" block: list the pillar answers, name any deviation, and **ask the owner before continuing**. The generator writes it from the registry.
  - `generate-ide-config.py --write` regenerates tracked rule files; the current never-overwrite behaviour stays the default for first provisioning.
  - `process-gates.json → extends` feeds tenant-specific lines, replacing hand edits.
- **`agentsmith design new <slug> --scope <glob>…`** writes the design skeleton from the registry: front matter, Problem, Approach, one Pillars line per pillar with its design question, `Deviations: none`, Dependencies and Levers. The next IDE session starts from the right shape whatever the IDE.

### G2 — IDE hook adapters (one gate, every IDE)

- **`process_gate.py --ide <claude|cursor|antigravity|copilot|gemini|codex>`** normalises each IDE's stdin payload to one internal event (`session_start`, `pre_tool {kind: edit|shell|other, paths, command}`, `stop`), then renders the decision in that IDE's output format:

  | IDE | Config written | Deny | Stop block | Session context |
  |---|---|---|---|---|
  | Claude Code | `.claude/settings.json` | `hookSpecificOutput.permissionDecision: deny` | `decision: block` | `additionalContext` |
  | Cursor | `.cursor/hooks.json` (`failClosed: true` on `preToolUse`) | `permission: deny` | `followup_message` | `sessionStart` output |
  | Antigravity | `.agents/hooks.json` | `decision: deny` | `Stop` output | via rule file |
  | VS Code Copilot | `.github/hooks/agentsmith.json` | Claude format | `continue: false` + reason | `additionalContext` |
  | Gemini CLI | `.gemini/settings.json` | `decision: deny` | `AfterAgent` `decision: deny` | `additionalContext` |
  | Codex | `.codex/hooks.json` | `decision: block` | `Stop` | via AGENTS.md |

  VS Code also reads `.claude/settings.json` but **ignores matchers** and uses camelCase tool fields. Adapter input therefore accepts both field spellings, and a non-edit tool returns allow.
- **Shell pre-check, all IDEs.** It denies:
  - `git commit|push … --no-verify`;
  - `git -c core.hooksPath=…`;
  - `git config core.hooksPath` to anything other than `.githooks`;
  - writes to `.githooks/**`, `.agenticframework/approvals.jsonl` and IDE hook configs;
  - `agentsmith approve`.

  It also warns when a shell command writes into a gated path with no complete design. That is best effort; the stop, commit and sweep gates are authoritative.
- **Generated configs.** Every hook config is generated from `governance.json → ides`, drift-checked and committed. In a hook-capable IDE, the only way round the gate is to edit a generated config, which is itself a gated, denied path.
- **Fail-closed where the IDE allows it:**
  - Cursor: `failClosed: true`;
  - Claude: the existing shell fallback prints a deny;
  - Antigravity and VS Code fail open by design, so the stated limit is that git and the sweep still hold.

### G3 — Bypass sweep (no GitHub dependency)

- **Verified pointer.** `.git/agentsmith/verified` records the last commit whose range passed `ci` checks.
- **Sweep.** `process_gate.py sweep` runs the existing `cmd_ci` logic over `verified..HEAD` for every branch reachable locally. It runs from:
  - `pre-commit` (new, fast; before `commit-msg`);
  - `pre-push` (new);
  - every IDE session start (G2);
  - the stop hook.

  A commit that slipped past `commit-msg` (`--no-verify`, unarmed clone, rebase or cherry-pick) is found at the next touchpoint, whatever tool made it.
- **Blocked until repaired.** While unverified non-compliant commits exist, pre-commit and pre-push fail and the IDE pre-edit denies, naming the commits. `agentsmith gates repair` shows them. The fix is to amend or add the records in a new commit carrying `Repairs: <sha>…` trailers, re-run the check, and append a `bypass` entry to the review log. History is never rewritten automatically (pillar 12 spirit).
- **Hooks re-armed.** Every sweep checks `core.hooksPath` and re-arms it (idempotent) when a tenant config exists, printing that it did.
- **No trailer stamp.** An HMAC key would sit on the same disk the agent can read, and the sweep re-checks content anyway, so a stamp adds no guarantee. This replaces the "Gate: trailer" idea in the owner-reviewed backlog note, and it is flagged to the owner.
- **CI** stays as the last layer. `continue-on-error` / `|| true` are removed from governance steps in workflow templates, and a test fails on their reappearance. **Amended while building (2026-09-16):** the Knowledge Graph step keeps `continue-on-error` until G4, because it is G4 that builds and commits the graph at onboarding — making it blocking now would fail every tenant's CI for a control no tenant has yet. The framework health check stays non-blocking too: it reports on Phoenix and the registry, which a tenant may legitimately not configure in CI. Both are pinned with their reason by `test_governance_steps_block_on_failure`.
- **Amended while building (2026-09-16):** pre-commit reports rather than refuses. Refusing there deadlocks the repair — the commit that would fix a bypass is itself a commit, and pre-commit runs before the message that says what it repairs exists. `commit-msg` makes that call, and `pre-push` refuses unconditionally.

### G4 — Knowledge graph from day one, and reviews that use it

- **Onboarding.** `agentsmith tenant init` and first sync build the KG and commit `.agent-rfc/fixtures/knowledge_graph.json`.
- **Freshness.** `pre-commit` rebuilds it incrementally when staged files change top-level symbols; the check is blocking in the sweep and in CI (`verify_system.py --check-kg`, no `|| true`).
- **`local_knowledge_graph.py impact --base <ref>`** maps the diff to the nodes and edges it touches plus one hop of dependents. It outputs:
  - the files a reviewer must read;
  - the lever groups that apply, derived from node kinds (route → Group 5 / 7, gate script → 2 / 6, …);
  - a query hash.

  The review sign-off's `KG query:` line must carry that hash for the reviewed diff, and `check_review` verifies it matches the current diff.
- **Session start** injects a 20-line KG summary (changed-since-last-session impact) instead of telling the agent to run a script.

### G5 — One artifact per type

- **Registry** (`governance.json → artifacts`), per repo, with defaults:

  | Type | Canonical path | Notes |
  |---|---|---|
  | readme | `README.md` | High-level view of every aspect |
  | backlog | `docs/PRODUCT_BACKLOG.md` | Open work; also the to-do list |
  | archive | `docs/PRODUCT_ARCHIVE.md` | Done items with date and evidence |
  | design | `docs/DESIGN.md` | Living and current state; architecture, deployment, runbooks; "Active change" sections |
  | review_log | `docs/REVIEW_LOG.md` | Append-only: passes, sign-offs, audits, bypass repairs |
  | user_manual | `docs/UserManual.md` | The operations manual, with an Administrator/Operator section |
  | test_script | `docs/manual-test-script.md` | Tenant option |
  | changelog | `CHANGELOG.md` | Only where the repo releases to tenants (AgentSmith) |

  `ignored` covers git-ignored personal files (e.g. OTS `docs/DemoScript.md`). `reference` globs cover shipped product docs that aren't project records (AgentSmith `docs/process-gates.md`, `review-levers.md`, checklists).
- **Mode, per repo (amended while building G5a, 2026-09-17).** `.agenticframework/process-gates.json`
  gains `artifacts: "off" | "report" | "enforce"`, default `off`. The check ships in G5a; the
  documents move in G5b, and a repo that has not migrated would otherwise block every commit on
  files it is not allowed to delete yet. AgentSmith and OTS run `report` from G5a — the check says
  exactly what the migration has to fix — and G5b flips each to `enforce` in the same change that
  finishes its migration. `off` is for a repo that has not adopted the registry at all.
- **Cross-references travel with it.** The same mode governs the cross-reference rule (no pointer
  into another artifact's section numbers), which looks only at lines a commit adds or changes.
  A line that must quote a bad pointer as an example carries `<!-- xref: example -->`; the marker
  is greppable, so the exemptions can be counted.
- **Check.** `process_gate.py artifacts` runs in pre-commit, sweep and CI. It fails on:
  - a tracked Markdown file outside the registry, reference globs and ignored;
  - a second file whose name or heading matches an artifact type's patterns (`*BACKLOG*`, `*TODO*`, `*REVIEW*`, `SPECS*`, `OPERATIONS*`, `README*` outside the root and package roots);
  - a missing canonical file.
- **Records move into the single artifacts.**
  - Designs become `## Active change: <slug>` sections in `docs/DESIGN.md`. Front matter is replaced by a fenced `governance` block holding `status`, `scope`, Pillars, Deviations, Dependencies and Levers. A section is folded into the living text and removed when done.
  - Reviews become `## <slug> — Pass N — findings: K` and `## <slug> — Sign-off` entries in `docs/REVIEW_LOG.md`.
  - Trailers become `Design: docs/DESIGN.md#<slug>` and `Review: docs/REVIEW_LOG.md#<slug>`. "Changed in this commit" means the log gained lines for that slug.
  - `process-gates.json → records: "single" | "legacy"`, default `legacy`: the mode a repo has not declared is the one every repo has today. The gate accepts only the configured mode, so a repo never has two conventions. AgentSmith and OTS switch to `single`; KYC Sentinel stays `legacy` until it migrates (a logged item in the AgentSmith backlog).
- **AgentSmith's own consolidation:**
  - `FIXES_AND_CLEANUP.md` → `docs/PRODUCT_BACKLOG.md`;
  - `Product_Archive.md` → `docs/PRODUCT_ARCHIVE.md`;
  - `SPECS.md` + `docs/superpowers` + `.agent-rfc/designs` → `docs/DESIGN.md`;
  - `ReviewFindings-*`, `TestCoverageReview-*`, `TestbedFeedback-*`, `.agent-rfc/reviews`, `docs/review-lever-notes.md` (TBC) and OTS's `review-levers-history.md` (owner: "into the review log under AgentSmith") → `docs/REVIEW_LOG.md`;
  - `OPERATIONS.md` splits: high level → README, operator procedures → UserManual Administrator section, deployment architecture and runbooks → DESIGN.

### G6 — Mechanical pillar checks

- **`process_gate.py pillars`** is driven by `governance.json → pillars[].check.mechanical`, with a per-repo `allowlist` that can only shrink: the gate fails if an entry is added without an approved deviation. It checks:
  - **P7 Python:** no `@dataclass` or `dataclasses` import in first-party packages;
  - **P7 FastAPI:** route handlers are `async def`;
  - **P7 TS:** no `: any` / `as any`; `'use client'` is present where hooks or events are used;
  - **P3 tracing:** every CLI command, route and declared entrypoint is inside a span helper (AST);
  - **P10:** no direct provider SDK calls outside `runtime/llm_gateway.py` / the declared gateway;
  - **P12:** secrets scan on staged content;
  - **P2 dependencies:** lock-file package diff ⊆ the active design's `## Dependencies`.
- **Runs** in pre-commit (staged files only), the sweep and CI.
- **Local gate runner.** `agentsmith gates` runs the workflow's governance and test jobs locally by reading the steps tagged `# agentsmith:gate` in `.github/workflows/*.yml`. The Repo gates table in `review-levers.md` is generated from those tags (`pin-unremovable-duplicates`).

**Amended while designing (2026-09-17): G6 splits, and the policy is per repo.**

- **G6a (this slice)** — the pillar policy, evidence tokens, and the two checks the owner named:
  `P3-tracing` and `P7-pydantic`. **G6b** — the rest (`: any` / `use client`, async handlers, the
  gateway rule, the staged-secrets scan, the dependency diff) and the local `agentsmith gates`
  runner. Same reason G5 split: enforcement must not wait behind the breadth of a rule set.
- **The policy lives in the repo's config, not in the registry version.** A `@framework/…`
  registry is read beside the running script, not at the commit being checked, so a requirement
  added to it would apply retroactively to every commit CI re-checks — the defect G1 shipped with
  and fixed by adoption. `process-gates.json` is read at each commit, so the policy goes there:
  `"pillars": "off" | "report" | "enforce"`, or `{"mode": …, "allow": [...]}`, default `off`.
  Which checks exist is still the registry's: a check runs only while its pillar is marked
  `mechanical`.
- **Evidence is written in backticks and resolved against the tree.** A token resolves when it
  names a tracked path or glob, or when its literal text is found in tracked content (`git grep
  -F` at that commit) — one rule covering a path, a test id and a span name. Only `applies`
  carries evidence: `n/a` is a reason there is nothing to name, `gap` already names a backlog id,
  and a deviation already resolves to an approval. **Stated limit:** this proves the token
  resolves, not that it is the right token. A resolvable name can be falsified by anyone reading
  it; prose cannot.
- **The allowlist is per check and per path, and only ratchets.** An entry carries `check`,
  `path` and `why`. Adding one to a repo that already declares a policy needs `approval:
  A-xxxxxxxx` on the entry, resolved against `approvals.jsonl` like a deviation — the owner at a
  terminal, never the agent. The mode may only strengthen (`off` → `report` → `enforce`), and
  dropping the key is a weakening, so an allowlist cannot be widened by turning the policy off
  and on again. The seed is the adoption commit itself, where there is no policy to weaken.
- **Mechanical checks read the files a commit touches**, whole-file, not the added lines: a rule
  about how a module is built is not answerable line by line. So a repo adopts without fixing
  everything it owns, and pays when it next edits a file — which is what the allowlist is for.
- **`P7-pydantic`** flags `@dataclass` and `dataclasses` imports in first-party Python (tests
  excluded — a fixture is not a model). **Stated limit:** the AST cannot tell an internal value
  object from a model built out of unvalidated input, so the check flags both and the allowlist
  carries the difference in a sentence a person wrote. AgentSmith seeds sixteen entries, which is
  the evidence for narrowing the rule in G6b rather than a reason to trust it less.
- **`P3-tracing`** flags a route handler (`@<app>.get/post/put/patch/delete`) or a CLI command
  (`@<app>.command`) whose body opens no span — `agent_span(...)`, `*.start_as_current_span(...)`
  or `gate_span(...)` — and no tracing decorator. **Stated limit:** an entrypoint that is not
  declared by a decorator is not found, and a handler that delegates to a helper that traces
  reads as untraced. Both are the design-time question's job, which does not go away.

### G7 — Onboarding completeness

- `agentsmith tenant init` / sync provisions everything: `process-gates.json`, `governance.json`, `.githooks` (armed), every IDE hook config, generated rule files, a committed KG, and single-artifact stubs.
- `verify_system.py --governed` fails until all of that is present, the rules source exists, the security posture has no placeholders and the last local `agentsmith gates` run is green.
- Pillar 5: `.agent-history.log` entries are written by the stop and sweep hooks (bypasses, blocked turns), not by agent memory.

## Pillars

- P1 applies — this design precedes code and records each slice; the shape it must have is checked by `check_design`.
- P2 applies — no new third-party dependencies: pydantic, opentelemetry-sdk/exporter and pyyaml are already pinned in `requirements.lock`.
- P3 applies — every gate decision is a span through `scripts/gate_tracing.py`, spooled locally and shipped with a short timeout.
- P4 applies — each slice adds failing tests first, this one in `scripts/test/test_gate_pillars.py`, with mutation checks on every blocking path.
- P5 applies — bypasses and blocked turns are appended to `.agent-history.log` by hooks (G7).
- P6 applies — hook messages are one line naming the rule, the file and the fix; the wording is pinned by `test_gate_pillars.py`.
- P7 applies — Pydantic V2 models for payloads, registry, config, approvals and sign-offs, in `scripts/gate_models.py`.
- P8 n/a — no runtime OTLP wiring changes.
- P9 n/a — no orchestration.
- P10 n/a — no LLM calls.
- P11 applies — hook payloads and commit messages are data; `resolve_record` resolves a trailer only inside the records directories.
- P12 applies — no credentials; the approval record in `.agenticframework/approvals.jsonl` stores the git identity only.
- P13 applies — no threshold lowered; `transition_problems` is what keeps an allowlist shrinking; every limit (a human typing an approval, fail-open IDEs) is stated.
- P14 applies — the baseline each slice re-pins in the same change is `templates/governance.json`, generated and drift-checked; the golden hook payload fixtures per IDE arrive with G2 and are pinned the same way.
- P15 applies — "skipped", "not armed", "not generated" and "passed" are four distinct outputs; `test_off_is_the_default_and_checks_nothing` pins one of them.
- P16 applies — no usable framework interpreter means pre-edit, pre-commit, commit-msg and pre-push fail closed with the fix (`.githooks/process-gate`); session start and stop warn; a failed span ship is kept in the spool and retried, never fatal.

## Deviations

- ~~D1 — P3 no spans in hooks~~ — withdrawn 2026-09-15 (owner chose option B).
- ~~D2 — P7 no Pydantic in hooks~~ — withdrawn 2026-09-15 (owner chose option B).
- D3 — the backlog note's `Gate:` trailer stamp is replaced by the verified-pointer sweep (G3) — an HMAC key would sit on the same disk the agent can read, and the sweep re-checks content — approval: A-597cd675
- D4 — `records: legacy` stays supported for KYC Sentinel until it migrates; each repo uses exactly one mode — approval: A-8ad5e81b

## Dependencies

- None added. Hooks use the framework environment's existing pydantic 2.x, opentelemetry-sdk 1.x and opentelemetry-exporter-otlp-proto-http 1.x; the generator keeps pyyaml; tests keep pytest.
- `scripts/test/test_process_gate.py`'s "hooks run the PATH python3 — 3.9 on a stock Mac" contract is deliberately replaced by the interpreter-resolution contract above, with a test for each fail-closed path.
- The IDE hook formats were verified against vendor docs on 2026-09-15 (Cursor, Antigravity, VS Code, Gemini CLI, Codex) and are pinned as fixtures.

## Levers

- `declared-vs-enforced` — every pillar gets a design question and, where possible, a mechanical check; rules stop living only in prose.
- `single-source-of-truth` — `agent-rules.yaml` → `governance.json` → every rule file and hook config, all generated and drift-checked.
- `implemented-not-invoked` — each IDE's config is generated and committed, so a hook existing means it runs.
- `guards-must-be-able-to-fail` — each blocking path gets a mutation check; the sweep is proven by a fixture commit made with `--no-verify`.
- `gate-integrity` — allowlists only shrink; approvals come from a TTY-only command; the framework follows its own P3/P7 rules with no exception; limits are stated.
- `ambiguous-signals` — "drift check skipped (no rules file)" becomes a failure in governed repos.
- `minimal-host-dependency` — the only host requirement is the framework environment `install-ai-stack.sh` already builds; a missing one is a named, fail-closed state, not a silent skip.
- `when-the-fallback-fails` — a missing interpreter fails closed in pre-commit and pre-push; fail-open IDEs are named, with git and the sweep behind them.
- `no-redundant-artifacts` — the artifact registry plus the consolidation of both repos.
- `run-the-gates-ci-lists` — `agentsmith gates` reads the workflow tags; the Repo gates table is generated.
- `small-verified-slices` — G1…G7, each reviewed to 0 before the next.
- `environment-parity` — the same gate code runs in six IDEs, git hooks and CI.
- `design-before-code` — this note, with deviations approved before any code.
