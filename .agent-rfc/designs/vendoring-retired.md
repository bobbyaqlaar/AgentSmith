---
status: done
scope:
  - workflow-templates/**
  - .githooks/process-gate
  - hooks/**
  - enterprise/**
  - install-ai-stack.sh
  - runtime/**
  - scripts/**
  - .github/workflows/**
  - .github/scratch-tenants/**
  - .github/actions/**
  - templates/**
  - contract/**
  - fixtures/**
  - .agenticframework/process-gates.json
  - .agent-rfc/fixtures/knowledge_graph.json
  - pyproject.toml
  - portal/.env.example
---
# C9 — vendoring retired (3.0.0)

Slice C9 of `.agent-rfc/designs/governance-contracts.md`: the last one. A tenant decouples from
AgentSmith by contract, and the copy of AgentSmith a tenant used to hold is the coupling this ends.
The owner asked for it on 2026-10-13.

## Problem

Measured on `main` at v2.4.0, 2026-10-13:

- **Five paths still put AgentSmith's code into a tenant.**
  - The global `post-checkout` hook copies `scripts/`, `runtime/`, `fixtures/security/` and the base
    fixtures into every opted-in repository. The installer arms it, and the other three global
    hooks, through the machine-wide git `init.templateDir`.
  - `tenant init` runs that hook once (`_vendor`).
  - `sync` refreshes a vendored tenant through `upgrade`, and `agentsmith upgrade` refreshes one
    directly.
  - `tenant init` also copies AgentSmith's composite actions into `.github/actions/`.
- **The global hooks reach every repository on the machine.** `init.templateDir` puts them into each
  repository created or cloned. `post-commit` auto-tags and pushes. The Enterprise Pack signs the
  same four hooks and pushes them fleet-wide through MDM.
- **The workflow templates call vendored scripts in 19 places.** These include `run-evals.py`
  (scorecard, fairness, hallucination and the CD smoke), `run-security-checks.py`,
  `verify_system.py --check-redaction` and `--check-kg`, `generate-ide-config.py --check-only`,
  `verify_ttft.py` and `shadow-eval.py`. A new tenant therefore needs the copy for its CI to run at
  all. C6 and C7 moved the live tenants' copies of these workflows onto the ports; the templates
  never moved.
- **The machine runtime and the launcher prefer a tenant's copy.** `find_script` returns the
  tenant's `scripts/<name>` before the machine's. The launcher's fallback looks in
  `<repo>/scripts/process_gate.py` first, which is where a vendored tenant keeps one.
- **Who holds copies:**

  | Tenant | Holds |
  |---|---|
  | OTS | `scripts/` (46 files) and `runtime/` (51). CI and CD still run four of them: `run-evals.py` as the CD smoke, `map_codebase.py`, `verify_system.py` and `verify_ttft.py`. |
  | oil-price-demo | `scripts/` and `runtime/`, on framework 1.0.0, untouched since 2026-07-01 and superseded as the demo by KYC. |
  | KYC Sentinel | only a copy of the `gcp-auth` action, kept equal to AgentSmith's by a CI diff. |
  | Scratch tenants | five of the six are built by the installed `post-checkout`. |

## Approach

### The owner's decisions (2026-10-13)

- **3.0.0, a MAJOR.** Vendoring, `upgrade` and the vendoring hook go outright. The 3.0.x row says
  what a 2.x tenant does first.
- **The installer stops arming global hooks.** It installs the provider and the `agentsmith`
  command, and restores the `init.templateDir` it found. A repository comes under the gates through
  `tenant init` (new) or `tenant adopt` (existing), which write its own `.githooks`.
- **The live TTFT and shadow-eval templates go.** An evals-port suite for latency and shadow
  comparison goes on the backlog.
- **oil-price-demo is archived by the owner.** The check covers governed tenants and names it as
  archived.
- **The Enterprise Pack's hook bundle retires with the hooks.** `package-hook-bundle.sh` and
  `mdm-deploy-hooks.sh` go. The org policy stays, read by the provider. A signed bundle of the
  provider install and the policy goes on the backlog as its own design.

- **What the global hooks guarded moves into the gate** (asked on 2026-10-13). The gate's commit
  decision (`commit_verdict`) is the one judgement both `.githooks/commit-msg` and gate contract 3's
  `commit` answer use, and it now checks the staged files the tenant wrote:
  - unresolved AI markers (`ponytail:`, `TODO: agent`, `@agent-ignore`);
  - empty `catch`/`except` blocks: the Python check by syntax tree (`check_bare_except.py`), plus the
    JS/TS and Go patterns the hook used;
  - with an org policy present (`~/.agent-framework/agenticframework-org.yaml`): no direct
    `cost_router` import under `runtime/`, at least one RFC at `.agent-rfc/*.md`, and an `RFC-NNN`
    in the message.

  A file `scaffold.json` vouches for, and that still hashes as recorded, is skipped, as in the hook.
  `process-gates.json` `commit_guardrails` is `on` by default, matching where the hooks ran.
  AgentSmith declares it `off`: the hooks never ran on its own commits, its tests carry the markers
  as fixtures, and its suite runs the same rules over its tree (`test_bare_except_tree.py`). The
  post-commit knowledge-graph refresh is not moved: the review's `KG query:` already makes a stale
  graph fail. AgentSmith's own evidence that the checks hold, `verify_system --check-hooks`, which
  CI and SEC-CHANGE-001 run, commits through its `.githooks` in throwaway repositories instead of
  running the retired hooks.
- **`tenant init` seeds the security pack's placeholders, which the hook seeded,** into
  `.agent-rfc/security/`, never overwriting. These are the tenant's documents, not framework code.
  It does **not** seed the golden dataset or the judge criteria, which the hook also seeded. Found
  while building: the framework's base cases carry no `actual_output`, so under the evals contract
  (C6) they fail SEC-EVAL-001 and can never be the repository's dataset. The design already called
  them bootstrap-only.
- **`tenant init` declares what a new repository truthfully is**, in the `providers.json` it now
  writes:
  - security `"emitter": "none"`: it exports no telemetry yet, so SEC-PII-002 is not applicable
    rather than failed;
  - the judged suites' `not_gradable` and `no_verdict` as warnings, until it has eval data of its
    own.

  Before C9, a fresh tenant's evals skipped silently (`run-evals` with fewer than 3 cases). The
  warning keeps that green step and says the suite proved nothing. This is the same declaration
  OTS's reviewed move made. `adopt` and `sync` keep C7's rule that an existing repository decides
  its emitter.
- **The machine's provisioning hooks are never chained.** `install_gate_hooks` always leaves out a
  prior `post-checkout` or `post-commit` that is AgentSmith's (`is_machine_hook`), as `adopt` and
  `sync` already did. A repository whose `.git/hooks` kept copies from an old install therefore stops
  vendoring once it is under the gates.
- **`tenant init` declares the repository's providers and writes the gates and sync workflows**,
  as `tenant adopt` does. Found while building: init wrote no `providers.json`, so an init'd
  repository's ports said "no provider declared" and judged nothing. Until 3.0.0 the vendored
  scripts papered over that; after it, the ports are the only route. `--framework-ref` names the
  provider release, and every template is rendered with that setup. The placeholder is
  `{{PROVIDER_SETUP}}`, the one the gates templates already used.
- **The five hook-built scratch tenants are rebuilt as the adopted one is** (owner, 2026-10-13):
  - a fresh orphan history each run;
  - the app committed first, then the scaffold committed with the command `tenant init` prints,
    through the tenant's own gate;
  - force-pushed.

  Their CI now runs the gates workflow too.
- **`agentsmith mode off` and the bypass policy have nothing left to mute.** `status` stops
  reporting hooks as muted, and `DISABLE_AI_STACK` is read by nothing. Retiring them, or giving
  them a meaning, is on the backlog rather than decided here.
- **Not carried over:** the hook's interactive prompt to `.gitignore` the rule files in a public
  repository. It goes on the backlog, for `tenant init` to offer non-interactively.

### The parts, in this order

0. **The guardrails in the gate (its own commit, first).** It is additive. The old hooks still exist,
   so a commit passes or fails on its own.
1. **Templates on the ports (C9a).** Every workflow template asks AgentSmith only through its
   pinned setup step and the launcher:
   - Evals go through `process-gate evals run --suite <s>`.
   - Security goes through `process-gate security check` and `security redaction --environment E`.
   - The rule files go through `process-gate rules check`.
   - The CD smoke runs `evals run --suite golden --fail-below <bar>`. The launcher gains
     `--fail-below`, which the evals request already carries (contract/evals/v1, additive), so
     staging keeps 0.75 and production 0.80.
   - `--check-kg` goes. It asserts that AgentSmith's own scripts appear in the graph, which tells a
     tenant nothing, and the gate's `ci` event already checks every review's graph scope. The
     informational `verify_system.py || true` steps go with it.
   - `{{AGENTSMITH_SETUP}}` in a template becomes the repository's declared setup reference when
     `tenant init` writes it, as `{{TENANT_ID}}` already is.
   - Composite actions are referenced at the provider, `bobbyaqlaar/AgentSmith/.github/actions/<name>@<ref>`,
     never copied, so `tenant init` stops copying them.
   - `eval-ttft-live.yml` and `shadow-eval.yml` leave the templates.
2. **Vendoring removed (C9b), in the same commit as C9a.** `hooks/post-checkout` fills only
   `{{TENANT_ID}}`, so the templates and the hook can only change together.
   - `hooks/` (the four global hooks) and the Enterprise Pack's hook bundle are deleted. The
     installer stops setting `init.templateDir` and puts back the value it recorded.
   - `tenant init` stops calling `_vendor`. `sync` stops refreshing vendored copies: in a tenant that
     holds them, it names them and says they are no longer refreshed.
   - `agentsmith upgrade`, `runtime/machine/upgrade.py` and the `ai-stack-upgrade` alias are
     removed.
   - `find_script` returns the machine's script only. The launcher's `<repo>/scripts/process_gate.py`
     lookup applies only to AgentSmith's own checkout.
   - `verify_system --governed` fails when the repository holds a **framework file**: a file at a
     path AgentSmith ships in `scripts/`, `runtime/`, `fixtures/security/`, a `fixtures/*_base.json`,
     or one of its `.github/actions/<name>/`. The check goes by path, so a stale copy counts. Each
     file is named, with the port that replaces it.
   - `tenant adopt` says the same of a repository that holds them, where it now only leaves them
     ungated.
   - The scratch tenants are built with `tenant init` instead of the installed hook.
   - Tests, docs and the backlog follow.
3. **Release 3.0.0 (C9c).** A 3.0.x compatibility row lists the removals and the order for a 2.x
   tenant: move every port first (2.4.0 has them all), delete the copies, then pin 3.0.0.
4. **Tenants (C9d), each in its own repository:**
   - **OTS:** the CD smoke moves to the evals port with `--fail-below`. CI's knowledge-graph and
     `verify_system` steps go, as does the opt-in TTFT workflow. Then the vendored `scripts/` and
     `runtime/` are deleted, keeping only OTS's own files.
   - **KYC:** `gcp-auth` is referenced at the provider, and the diff step goes.

**What stays:**
- `.githooks/` (`process-gate`, `commit-msg`, `pre-commit`, `pre-push`, `chain`) and the rule files.
  They are the contract's client, written and refreshed by `sync` and vouched for in
  `scaffold.json`, and are not framework code.
- Workflows `tenant init` writes once, which are then the tenant's.
- The `agentsmith-runtime` package, a library a tenant may choose to depend on (KYC does).

## Pillars

- P1 applies — `.agent-rfc/designs/vendoring-retired.md` records the five vendoring paths and every tenant's copies before any change, and the owner's five decisions.
- P2 applies — `runtime/cli.py` stops copying code and actions; templates reference the provider's actions at a pinned ref; no dependency is added.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/verify_system.py` `--governed` fails on any framework file, named; `scripts/test/test_workflow_template_wiring.py` holds that no template calls `scripts/` or `runtime/` by path.
- P7 applies — `workflow-templates/` stay one per stack (`ci-go.yml`, `ci-python-fastapi.yml`, `ci-ts-react.yml`), each now asking the ports.
- P8 n/a — no telemetry wiring changes; redaction is already the security port's.
- P9 n/a — no orchestration.
- P10 n/a — no routing change.
- P11 n/a — no untrusted input.
- P12 applies — `install-ai-stack.sh` stops arming a hook that pushes from every repository on the machine; no secret is read or written.
- P13 applies — `.githooks/process-gate` no longer runs a tenant's own copy of the gate; a repository is governed only by the provider it declares.
- P14 applies — `fixtures/` base files reach a tenant only through `tenant init`'s scaffold, never refreshed as code; `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
- P15 applies — `scripts/verify_system.py` names each framework file and the port that replaces it; `runtime/sync.py` says a tenant's copies are no longer refreshed instead of silently skipping them.
- P16 applies — `CHANGELOG.md`'s 3.0.x row is the recovery order for a 2.x tenant; 2.4.0 stays published with every port, so a tenant can move before pinning 3.0.0.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — a repository is governed by the provider it declares, never by a copy it holds.
- `single-source-of-truth` — AgentSmith's code lives in the provider install; actions are referenced, not copied.
- `implemented-not-invoked` — the KG check and the informational `verify_system` steps checked nothing of the tenant's.
- `two-owners-two-cadences` — the 3.0.x row is the tenant's order of moves; 2.4.0 holds every port.
- `docs-match-behaviour` — install, onboarding and upgrade docs say what 3.0.0 does.
