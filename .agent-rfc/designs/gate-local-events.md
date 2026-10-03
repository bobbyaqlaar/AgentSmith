---
status: done
scope:
  - contract/gate/v3/**
  - .githooks/process-gate
  - .githooks/commit-msg
  - .githooks/pre-commit
  - .githooks/pre-push
  - scripts/process_gate.py
  - scripts/gate_models.py
  - scripts/gate_kg.py
  - scripts/map_codebase.py
  - scripts/local_knowledge_graph.py
  - runtime/cli.py
  - runtime/conformance.py
  - runtime/adopt.py
  - runtime/sync.py
  - scripts/generate-ide-config.py
  - .agenticframework/process-gates.json
  - scripts/test/**
  - runtime/test/**
  - scripts/mutation_check.py
---
# C2 — Gate contract 3: the commit and push events, and the knowledge graph

Slice C2 of `.agent-rfc/designs/governance-contracts.md`. After C1 a tenant's CI asks its declared
provider; its local commit and push still run AgentSmith's `process_gate.py` by path. This slice puts
them behind the contract too, and makes the knowledge graph the gate's evidence rather than a script
the tenant runs.

## Problem

What a tenant still holds or calls that is AgentSmith's, after C1:

- **The local git gates resolve framework paths.** `.githooks/commit-msg` runs
  `.githooks/process-gate commit-msg`, `pre-commit` and `pre-push` run `process-gate sweep`; for those
  the launcher skips any declared provider and looks for `scripts/process_gate.py` in the repository
  (OTS's vendored copy), `$AGENTSMITH_DIR`, or `~/.agent-framework`. A third-party provider can govern
  a tenant's editing session and its CI, but not its commits.
- **Framework policy lives in a tenant file.** `.githooks/commit-msg` — copied into every tenant —
  hard-codes the Conventional Commits subject rule in bash. A provider with another rule cannot apply
  it, and a change to the rule is a change to every tenant's hook.
- **The knowledge graph is a framework script the tenant runs.** The gate's own messages tell a tenant
  to run `python3 scripts/map_codebase.py` and `python3 scripts/local_knowledge_graph.py --impact`;
  OTS's CI runs `map_codebase.py` by path; the graph's format is whatever `map_codebase.py` writes, and
  only `scripts/gate_kg.py` knows what the review's `KG query:` hash is computed from.

## Approach

### Contract 3 = contract 2 + `commit` and `push`

`contract/gate/v3/` is a new directory; v1 and v2 stay published and served. A new version rather
than additions to v2 because v2 is on `main` and is what v2.1.0 will publish: a published contract
does not change under the people who implemented it.

- **`commit`** — `{"kind": "commit", "message": "<the full message>", "amend": false}`: may this commit
  be made? The provider judges the staged change in `cwd` and the message — whatever its policy is:
  for AgentSmith, the subject rule, the Design and Review trailers, and the bypass sweep's outstanding
  commits with their `Repairs:` trailer. One decision; `deny` carries the reason; `report` is optional.
- **`push`** — `{"kind": "push"}`: may this repository's history leave this machine? AgentSmith
  answers with the bypass sweep. The refs git passes to `pre-push` stay with the hook (they are not
  stable across git versions and no provider has needed them).
- **Neither falls back.** As for `ci`: no decision blocks the commit or the push, and names why. The
  three editing events keep v1's fall-through.
- **`pre-commit` stops asking anything at contract 3.** Today it runs the sweep in report mode before
  the message exists; `commit` runs the same sweep with the message and is the one that decides, so the
  early report duplicates it. At contract 3 `pre-commit` only chains the repository's own hook. At
  contract 1 or 2 every hook does exactly what it does today.

### The hooks become stubs

At contract 3, `.githooks/commit-msg` reads the message file, detects `--amend` as it does now, and
asks `.githooks/process-gate commit` — **no subject rule, no policy**: the regex moves into AgentSmith's
`commit` answer, where it was always a rule of this provider. `.githooks/pre-push` asks
`process-gate push`. The launcher sends the event to the declared provider and turns the decision into
an exit code, as it does for `ci`. Below contract 3 the hooks keep today's behaviour, regex included,
so an unmigrated tenant loses nothing.

### The knowledge graph is the gate's

- **The graph's shape is published**: `contract/gate/v3/knowledge_graph.schema.json`, generated from
  the model `scripts/gate_kg.py` reads, for `.agent-rfc/fixtures/knowledge_graph.json`. The committed
  graph is the tenant's data, in a documented format.
- **Two tool verbs join the contract**, beside the events: `<gate> kg build` writes the graph for the
  repository in `cwd`; `<gate> kg impact --base <ref>` prints, as JSON, the files a review should read,
  the lever groups, and the `KG query:` hash. A provider must offer both if its `commit` or `ci`
  answers check a review's scope. AgentSmith's are `agentsmith gate kg build|impact`, over
  `map_codebase.py` and `local_knowledge_graph.py`.
- **Every message and rule names the verb, not the path.** The gate's refusals, the session-start
  checklist every generated rule file carries (`scripts/generate-ide-config.py` writes "Query the
  Knowledge Graph: `python3 scripts/local_knowledge_graph.py`" into each IDE's rules) and the docs say
  `agentsmith gate kg …` where they named a script path. `tenant init` and `tenant adopt` build the
  first graph by calling `map_codebase.py` themselves — the provider running its own code, which is not
  coupling — and keep doing so.
- **No freshness rebuild in CI.** `map_codebase.py` records file mtimes, so a rebuilt graph never
  equals a committed one byte for byte; what CI must know — that a review covered the right scope — the
  `KG query:` check in `ci` already enforces. OTS's node-count step is replaced by that, not ported.

### The provider runs its own gate

`agentsmith gate` looked for `process_gate.py` in the repository it was asked about **first**
(`./scripts/`), and in its own installation second. In a vendored tenant that means the provider
answers with the tenant's copy — OTS's, 1,318 lines behind — so a tenant on contract 2 or 3 would
still be judged by stale framework code it holds. The provider now runs its own installation's gate;
a repository's `scripts/` is used only when that repository is the framework checkout itself
(`looks_like_framework`), so AgentSmith's own development still runs the code being changed.

### Declarations and sync

`providers_declaration` writes contract 3; `sync` moves an untouched declaration and the hook stubs
together, in its one pull request. A contract-3 declaration with stub hooks against an older provider
gets "no decision" on `commit` — the launcher then blocks the commit and says the provider is too old
for contract 3, which is the honest answer.

### Conformance

v3's fixture is v2's; its cases are v2's plus: a staged governed change with no trailers (`commit` →
`deny`), the same with a design that covers it and a clean review (`allow`), a subject that breaks the
provider's message rule is **not** a case (the rule is policy, not contract), a clean history
(`push` → `allow`), a history holding a commit that skipped the gate (`push` → `deny`), and `kg impact`
returning the three fields with a `kg:` hash. AgentSmith passes v1, v2 and v3.

### The tenants that prove it

After the release that carries it: an adopted scratch tenant (the backlog item opened with this
design), KYC — its hooks become stubs and its declaration moves to 3 — and OTS, whose vendored
`process_gate.py`, `gate_*.py`, `map_codebase.py` and `local_knowledge_graph.py` can then go unless
another vendored script still imports them; its alignment design names which.

**Deliberately not done:** the record's wire contract (C3); the rules contract (C4) — this slice only
changes the rule *text* that named a path, in `scripts/generate-ide-config.py`; the machine hooks (`hooks/post-commit`,
`hooks/post-checkout`), which run on the developer's machine from the install, not from the tenant.

## Pillars

- P1 applies — `.agent-rfc/designs/governance-contracts.md` defines C2 and its tenant steps; `.agent-rfc/designs/gate-contract-ci.md` is the pattern this extends; this design precedes the code.
- P2 applies — `contract/gate/v2/protocol.md` is extended into v3 rather than rewritten, and `scripts/process_gate.py`'s `cmd_commit_msg` and `cmd_sweep` already make both decisions; they gain a decision output as `cmd_ci` did. `scripts/gate_kg.py` already defines what the hash is computed from; the schema is generated from it. No dependency added.
- P3 applies — `scripts/process_gate.py` runs `commit-msg` and `sweep` inside `_traced(...)`; the provider path goes through the same calls, so each event keeps its span.
- P4 applies — `runtime/conformance.py` gains the v3 cases and AgentSmith must pass v1, v2 and v3; `scripts/test/test_gate_contract_v2.py` is the model for a v3 file covering the launcher's answers for `commit` and `push` (allow, deny, no decision → blocked, never a path fallback), the stub hooks, and contract-1/2 hooks unchanged. Mutations on the no-fall-through rule, the moved subject rule and the `kg impact` hash.
- P7 applies — `scripts/gate_models.py`: the commit and push events and the knowledge-graph shape are Pydantic models; the v3 schemas are generated from them.
- P8 n/a — no new telemetry wire; each event keeps its existing span.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 applies — `.githooks/commit-msg` passes the commit message to the provider as data inside a JSON event, encoded by the launcher's interpreter, never spliced into a command; the declared command comes from the committed declaration, as in v1.
- P12 n/a — no credentials in these events.
- P13 applies — `.githooks/commit-msg` blocks a commit when the gate cannot run, today; the provider stops answering with a tenant's vendored copy of the gate; at contract 3 a provider with no decision blocks it too and never falls back to a framework path, and the subject rule moves into the provider without being dropped for unmigrated tenants.
- P14 applies — `contract/gate/v2/fixture.json` and its cases stay byte-for-byte; v3 carries them, pinned, and adds its own.
- P15 applies — `.githooks/process-gate` distinguishes a refused commit (the provider's reason) from a provider that gave no decision (which kind) from one too old for contract 3.
- P16 applies — `contract/gate/v2/providers.schema.json` already lets the gate entry state its contract, so a tenant returns to 2 by editing one number; below 3 the hooks behave exactly as before.

## Deviations

none

## Dependencies

none

## Levers

- `gate-integrity` — no fall-through for `commit` or `push`; the subject rule moves, it is not dropped.
- `declared-vs-enforced` — the provider's policy lives in the provider; the tenant's hook only asks.
- `single-source-of-truth` — one definition of the graph's shape and the review-scope hash, published.
- `test-the-contract` — v3 conformance cases, and the stub hooks exercised in a real commit and push.
- `two-owners-two-cadences` — v1 and v2 stay served; contract 3 is chosen per tenant.
- `failure-mode-visibility` — refused, no decision, and too old read differently at commit time.
- `docs-match-behaviour` — every message and rule that named `map_codebase.py` names the verb.
