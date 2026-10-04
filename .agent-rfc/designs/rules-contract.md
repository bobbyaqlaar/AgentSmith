---
status: active
scope:
  - contract/rules/v1/**
  - scripts/rules_port.py
  - scripts/generate-ide-config.py
  - scripts/gate_models.py
  - scripts/process_gate.py
  - runtime/cli.py
  - runtime/adopt.py
  - runtime/sync.py
  - runtime/conformance.py
  - .githooks/process-gate
  - workflow-templates/agentsmith-gates.yml
  - scripts/test/**
  - runtime/test/**
  - scripts/mutation_check.py
  - .agenticframework/process-gates.json
---
# C4 — The rules contract: what a tenant's agents are told, and who checks it

Slice C4 of `.agent-rfc/designs/governance-contracts.md`. The gate decides whether a change may
land; the **rules** are what every IDE's agent is told before it starts — `CLAUDE.md`, `AGENTS.md`,
`GEMINI.md`, `.cursorrules`, `.github/copilot-instructions.md` and the skill files. This slice puts
rendering and checking them behind a declared command, so a tenant's CI and declaration name a
provider, never a framework file.

## Problem

Measured in this repository, OTS and KYC Sentinel on 2026-10-04:

- **A tenant's CI runs the renderer by path.** OTS's `ci-python-fastapi.yml` runs
  `python3 scripts/generate-ide-config.py --check-only` and `--registry --check-only` against its
  vendored copies of `templates/agent-rules.yaml`, `templates/governance.json` and the script. The
  `tenant init` templates (`workflow-templates/ci-*.yml`) ship the same step.
- **A tenant's declaration names the provider's files.** `agentsmith tenant adopt` writes
  `"registry": "@framework/templates/governance.json"`, `"levers_doc": "@framework/docs/review-levers.md"`
  and `"design_checklist": "@framework/docs/design-review-checklist.md"` into every adopted tenant's
  `process-gates.json` (`runtime/cli.py` `_process_gates_config`) — the provider's install layout,
  in the tenant's committed config. KYC carries the last two. OTS goes further: `"registry":
  "templates/governance.json"`, its own vendored copy, so the pillars its designs are held to are
  whatever was vendored last, not what its provider enforces.
- **Rendering is not callable by anyone else.** `adopt` and `sync` render by running
  `<framework>/scripts/generate-ide-config.py` (`runtime/adopt.py` `generated_rules`). The marked
  block that lets a tenant keep its own text in a rule file — `<!-- agentsmith:rules:begin … -->` /
  `<!-- agentsmith:rules:end -->` — and when a file is the provider's whole are defined only in that
  code. A second rules provider could not be plugged in, and nothing could check it was right.
- **What the rules depend on is not fixed.** The renderer reads `AGENT_OWNER_ID`,
  `AGENT_PHOENIX_ENDPOINT` and `FRAMEWORK_VERSION` from the environment, and `adopt` passes the git
  remote's name as the project. A CI runner with one of those set renders different text from the
  developer who committed the files: drift that is nobody's change.
- **The tenant's own rules have no published shape.** `extends` in `process-gates.json`
  (`rules_extra`, `session_start`, `test_command`, `pillars`, `artifacts`) is validated by
  `gate_models.Extends`, and described nowhere a tenant or another provider can read.

## Approach

### `contract/rules/v1/` — a command port

The shape of `contract/gate/v1`: `<rules-command> <verb>`, cwd is the repository, one JSON request
on stdin (`request.schema.json`: an object, `cwd` optional, unknown keys ignored), one JSON answer on
stdout, **exit 3** for "cannot run here". An answer is JSON on stdout; anything else is no answer.

**Inputs.** A render is a function of the repository's **committed declarations and content** and
the provider's own version — nothing else:

- `.agenticframework/tenant.yaml` — `tenant.name`, `tenant.owner`, `framework.version`;
- `.agenticframework/process-gates.json` `extends` — the tenant's own rules
  (`extends.schema.json`, generated from `gate_models.Extends`, which gains `otel_endpoint` — absent,
  the provider's own default);
- files the repository commits (a lock file decides a default test command, a manifest the stack).

Not the environment, not machine configuration, not the git remote. Two machines render the same
bytes from the same commit, so CI's check can only fail on a change somebody made.

**`render`** → `rendered.schema.json`: `{"files": [{"path", "text", "placement", "kind"}]}`.

- `placement` is **`whole`** — the file is the provider's, and is replaced — or **`block`** — the
  provider owns the region between the two markers and the tenant owns everything else. The markers
  are the ones tenants already carry, now named by the contract:
  `<!-- agentsmith:rules:begin` (the rest of that line is free text) and `<!-- agentsmith:rules:end -->`,
  each on its own line; a file without them gets the block appended. A provider returns `whole` for
  a file that exists only when it recognises the file as its own; how it recognises it is its own
  business (AgentSmith reads its generated header). So a tenant's hand-written `CLAUDE.md` is never
  overwritten.
- `kind` is **`instructions`** — an IDE's standing rules file, which must carry every one of the
  tenant's `rules_extra` notes — or **`supporting`** (a skill file, which need not).
- `path` must be relative, normalised and outside `.git/`, `.githooks/`, `.agenticframework/`,
  `.github/workflows/` and `.github/actions/`: a rules provider writes what agents read, never the
  repository's hooks, declarations or CI. **The caller enforces it** and refuses the whole render on
  the first bad path — it writes nothing rather than half.

**`check`** → `check.schema.json`: `{"decision": "allow" | "deny", "text", "report", "files": [{"path", "state"}]}`,
`state` ∈ `current`, `drifted`, `absent`. A `whole` file is drifted unless byte-equal; a `block` file
unless its region is, and a file with no markers is drifted; text outside the block is never compared. An **absent** file is reported and is
not drift: a repository may choose not to commit its rule files (this one gitignores them). `deny`
carries the reason and the command that repairs it; `report` is a diff of each drifted file, for a person.

**`providers.json`** gains a `rules` port, `{"command": "agentsmith rules", "version": "^2",
"contract": 1}` or `"none"` (`contract/rules/v1/providers.schema.json`, the fragment for this port).
The gate's top-level `contract` stays the gate's.

**Deliberately not in the contract: the registry.** The umbrella listed "the registry schema". The
registry — the pillar catalogue a design is checked against — is the gate provider's policy, and
publishing it as something a tenant may hold is exactly how OTS came to check its designs against a
stale vendored copy. A tenant adds to it through `extends.pillars`, which is published. The umbrella's
C4 row is amended to say so.

### AgentSmith as the provider

- **`scripts/rules_port.py`**: `render(root) -> list[RulesFile]` and `check(root) -> RulesCheck`,
  built on `generate-ide-config.py`'s renderers. The script keeps its flags for this repository's own
  CI and the vendored post-checkout hook, and its default mode calls the same `render`, so there is one
  renderer. It stops reading the three environment variables; `adopt` stops passing the git remote's
  name (`tenant.name` is already declared).
- **`agentsmith rules render [--write] | check`**, through `_provider_scripts()` — the provider's own
  scripts, never a tenant's vendored copy, as C2 does for the gate. `--write` places each file by its
  placement; it is the provider's convenience, not a contract verb.
- **`adopt` and `sync`** ask the declared rules command for `render` and place what it returns —
  the same function `--write` uses — so a tenant that declares another rules provider is synced from
  it. With no `rules` declared, `sync` adds AgentSmith's to a declaration it wrote, as it does the
  gate's setup; a declaration the tenant edited is left alone and named.
- **The gates workflow** (`workflow-templates/agentsmith-gates.yml`) gains one step after the gate:
  `bash .githooks/process-gate rules check`. The launcher reads the `rules` port the way it reads the
  gate's (`declared_gate` becomes `declared_port <port>`): not declared, or `"none"` → says so and
  passes; declared and no answer → **fails**, and says which way it got none. An old launcher that does
  not know `rules` hands it to `process_gate.py`, which refuses it as a usage error, or finds no gate
  script — either fails the step: closed, not skipped.
- **The provider paths leave a tenant's config.** `adopt` stops writing `registry`, `levers_doc` and
  `design_checklist`. Absent, `registry` already means the provider's own. `levers_doc` and
  `design_checklist` do not: absent, they default to a repository path (`docs/review-levers.md`,
  `docs/design-review-checklist.md`), so dropping KYC's keys as things stand would point its gate at
  files it does not have. Their default becomes **the repository's own file if it has one at the
  commit being checked, else the provider's** — every repository that has the file keeps reading it,
  and one that has not gets what its `@framework/` value meant. `sync` removes each of the three
  keys from a tenant's `process-gates.json` **only** when it holds exactly the `@framework/` value
  `adopt` wrote, and lists the change in its commit; any other value is the tenant's choice and is left, with a note when it names a repository path to a registry. `process_gate.py`
  still resolves `@framework/` (a tenant not yet synced keeps working), and its messages stop telling a
  tenant to run `scripts/generate-ide-config.py`.

### Failure semantics (the umbrella's table, for this port)

**Closed in CI**: drift, a bad path, or no answer fails the step. **Open in a session**: nothing runs
per session; the files already rendered stand. **Not declared** is said, not silent, and is itself a
change to an always-governed file.

### Conformance

`agentsmith conformance --port rules --provider "<command>"` builds `fixture.json`'s repository — a
tenant's declarations with two notes, and a hand-written `CLAUDE.md` with no markers — and runs
`cases.json`:

- `render` answers, valid against the schema, with at least one `instructions` file and only safe
  paths;
- it renders the same bytes twice, the second time with `AGENT_OWNER_ID`, `AGENT_PHOENIX_ENDPOINT`
  and `FRAMEWORK_VERSION` set to junk;
- every note appears in every `instructions` file; the hand-written `CLAUDE.md` is not `whole`;
- after the runner places the files: `check` allows; a byte changed inside a block denies, naming
  the file; a line added outside the block allows; a byte changed in a `whole` file denies; a file
  deleted is reported `absent` and allows; a note changed in the declaration denies;
- an unknown verb gets no answer.

AgentSmith is scored by it. A stub provider that ignores its notes, and one that reads the
environment, are each shown to fail it.

### The tenant steps that prove it — after the release that carries it

- **OTS** (its own design, in OTS): declares `rules`; drops `"registry": "templates/governance.json"`,
  so its designs are checked against its provider's pillars; its two `generate-ide-config.py` CI steps
  go, replaced by the gates workflow's step. Its vendored `templates/` and `generate-ide-config.py`
  are then read by nothing — they leave with the rest of vendoring at C9, because `upgrade` re-vendors
  `scripts/` and `templates/` whole and stopping that piecemeal would break a vendored tenant whose CI
  still runs `scripts/process_gate.py` by path.
- **KYC Sentinel**: `sync` removes its two `@framework/` keys. It commits no rule files today; while
  that holds, its check reports each one absent and passes.

**Deliberately not done:** the `tenant init` templates' drift step (`ci-*.yml` serve vendored
tenants, which retire at C9); the IDE hook configs (`.claude/settings.json` and the rest wire the gate
and stay with it); seeding `.agent-history.log` (tenant data, not a rule); the registry as a published
schema (above).

## Pillars

- P1 applies — `.agent-rfc/designs/governance-contracts.md` defines C4 and is amended where this design departs from its row (the registry, the timing of the vendored files); `.agent-rfc/designs/sync-merged-files.md` is where the marked block was designed; this design precedes the code.
- P2 applies — `scripts/generate-ide-config.py` keeps its renderers and gains one entry point both its own default mode and the port call; `runtime/conformance.py` gains the port rather than a second runner; `.githooks/process-gate` generalises `declared_gate` rather than adding a parser. KG impact over the scope is recorded in the review. No dependency added.
- P3 applies — `scripts/gate_tracing.py` `gate_span` is the helper every gate event runs inside; `rules render` and `rules check` each run inside one span from it (`gate.rules_render`, `gate.rules_check`, with `agent.role=process-gate` and the tenant) carrying the verdict and file count, spooled like the gate's when no collector is up.
- P4 applies — `runtime/conformance.py`'s rules suite runs against AgentSmith and against two stub providers that must fail it; unit tests for placement (block replace, append, whole), path refusal, the launcher's three outcomes, and `sync` dropping only default-valued keys. Mutations: a check that ignores a block's drift, a renderer that reads `AGENT_OWNER_ID`, a path guard that allows `.githooks/`, a launcher that passes on no answer, a `sync` that drops a non-default `registry`, a levers default that prefers the provider's file over the repository's.
- P7 applies — `scripts/gate_models.py`: `RulesFile`, `RulesRender`, `RulesCheck` and the `rules` port entry are Pydantic V2 models, the schemas generated from them, as C3's record is.
- P8 n/a — no telemetry wire changes; the span above uses the existing exporter path.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 applies — `runtime/adopt.py` will write files named by a provider's output: the caller validates every path against the contract's allowed shape and refuses the whole render on the first bad one, so a rules provider cannot write hooks, declarations or CI.
- P12 n/a — no credentials are read or written; the rules port carries none.
- P13 applies — `workflow-templates/agentsmith-gates.yml` gains a blocking check a tenant's CI did not have; the existing drift check's semantics (absent is not drift) are kept, not loosened; `@framework/` still resolves, so no tenant's gate weakens before it syncs; removing a declared `rules` port is a change to an always-governed file.
- P14 applies — `scripts/generate-ide-config.py` stops reading three environment variables and the git remote: a tenant whose files were rendered with one of them set sees a one-time drift that `agentsmith sync` repairs, and the fixture pins the inputs the contract allows.
- P15 applies — `.githooks/process-gate` keeps "not declared", "declared none" and "no answer" apart: the first two pass and say so, the third fails and names whether the command was missing, exited 3 or printed something that was not JSON.
- P16 applies — `runtime/sync.py` places files only after the whole render validated, so a refused render leaves the tenant's files as they were; a tenant that drifted is repaired by `agentsmith sync`, which the deny text names.

## Deviations

none

## Dependencies

none

## Levers

- `single-source-of-truth` — one renderer behind the script's flags, the port and `sync`; one model per document, the schemas generated from it.
- `environment-parity` — a render depends on committed content only, so CI and a developer cannot disagree about what the rules say.
- `two-owners-two-cadences` — the marked block is the provider's, the rest of the file the tenant's; only the block is ever compared or replaced.
- `validate-on-the-receiving-side` — the caller checks every path a provider returns before writing any.
- `denied-vs-missing` — absent, drifted, not declared, declared none and no answer are five different results.
- `guards-must-be-able-to-fail` — two stub providers are shown failing conformance, and the launcher's no-answer path is tested to fail the step.
- `test-the-contract` — AgentSmith is scored by the same cases another provider would be.
- `declared-vs-enforced` — the provider paths in a tenant's config go, so what the tenant declares is what it holds.
