# AgentSmith — Remaining To-Do Items

**Last reviewed:** 2026-09-14 (onboarding audit; current-state section re-verified)

> **Scope:** this document owns only *not-yet-done* work: the active item and
> confirmed future gaps with their trigger conditions. Completed build history
> lives in `docs/PRODUCT_ARCHIVE.md`; the formal specification is `docs/DESIGN.md`;
> operator procedures are `docs/UserManual.md`; release notes are `CHANGELOG.md`.
>
> If an entry here says something is missing, check it still is — this file
> spent a week claiming the testbed deploy had not started, six days after it
> had.

## Current state (2026-10-07)

**v2.2.1 is the latest release** (2026-10-07) — a patch to the evals contract's dataset schemas, the
release to adopt it at. v2.2.0 (2026-10-07) carried the evals contract (C6), a MINOR
(`CHANGELOG.md` › 2.2.x in the compatibility matrix). C6's tenant steps below — KYC Sentinel's
eval steps through the declared provider, OTS's eval workflows — were waiting on it. v2.1.0
(2026-10-05) carried the governance contracts C1–C5; v2.0.0 (2026-09-19) was the governance
release, a MAJOR.
**AgentSmith, KYC Sentinel and AqlaarTeleologyStudio are private** since
2026-09-13, until AgentSmith is product-ready — see the install item below.

Green on GitHub as of 2026-09-14: AgentSmith Self-Test, and all five scratch
tenants' own CI (`docs/scratch-tenants.md`). KYC Sentinel's CI is green
against the private framework (last run 2026-09-13) — strict harness 24 pass
plus the declared `SEC-AUDIT-002` gap — and its three judged gates have
graded live on the Gemini judge (golden 1.000, fairness 1.000, hallucination
0.857; 2026-09-01 to 09-07). No test count is quoted — one was, and went stale
three times in a single working session.

The **KYC Sentinel testbed tenant** (`../KYC_Sentinel`) is built, pushed,
CI-green and was deployed as a GCP staging smoke job on 2026-08-12 — full
history in `docs/PRODUCT_ARCHIVE.md` "T1–T4". Promotion has been suspended since
then; its `cd-staging.yml` was rewritten for the private framework on
2026-09-13 and has not run since.

**The one open build item is running it against real backends** — see below.

---

## Active: Governance enforcement (G1–G7) 🟡 IN PROGRESS (2026-09-15)

Owner requirement: every AgentSmith-governed repo follows the design, review, gating and CI rules **without exception**, in any IDE (Claude Code, Cursor, Antigravity, VS Code Copilot, Gemini CLI, Codex), with no GitHub-plan dependency. The knowledge graph is built from day one and drives reviews. The owner is asked at design start for any deviation. There is one artifact per document type.

Evidence: OTS template slices S1/S2 (no spans, dataclasses, KG skipped, CI subset, no sign-off). Root causes and mechanisms are in `.agent-rfc/designs/governance-enforcement.md`. Tenant side: OTS PB-104 (T1–T7).

| Slice | What | Status |
|---|---|---|
| G1 | Hooks in the framework environment (Pydantic + spooled OTel spans); `governance.json` registry generated from `agent-rules.yaml`; design needs `## Pillars / ## Deviations / ## Dependencies`; TTY-only `agentsmith approve` + `approvals.jsonl`; review sign-off parsed; "Design start: ask the owner" block in every rule file | **Done 2026-09-16** (`dde56b3`, `62810c3`) — review `.agent-rfc/reviews/governance-enforcement.md`; declaring `registry` in a repo's config is what adopts the design-time rules, so history and tenants that have not adopted are unaffected |
| G3 | Bypass sweep over every locally reachable commit, with `.git/agentsmith/verified`; `.githooks/pre-commit` (reports, re-arms) and `.githooks/pre-push` (refuses); `commit-msg` requires a `Repairs:` trailer while anything is outstanding; `agentsmith gates repair`; the IDE-drift CI step blocks | **Done 2026-09-16** — review `.agent-rfc/reviews/governance-enforcement-g3.md`. The Knowledge Graph CI step stays warn-only until G4 provisions the graph |
| G5a | Artifact registry, the `artifacts` check with a per-repo mode, `records: single`, and the cross-reference rule — as code, no documents moved | **Done 2026-09-17** — review `.agent-rfc/reviews/governance-enforcement-g5a.md`. AgentSmith runs `report`: `python3 scripts/process_gate.py artifacts` lists the 21 items G5b has to fix |
| G5b | The migrations: **OTS first**, **AgentSmith second** (reordered by the owner on 2026-09-18). AgentSmith: one file per type, numbered cross-references gone, `artifacts: enforce`, and the design, manual and README distilled to the current system and its reasons | **AgentSmith done 2026-09-18** — review `.agent-rfc/reviews/artifact-consolidation.md`. OTS's migration remains |
| Later | The portal's Ops pages answer 404 for an app outside the user's grants; the Dev pages show "You do not have access" and "No app called …" as two screens, as the approved specification asks. Align Ops, or record why the two workspaces differ | Trigger: the next change to an Ops page |
| Later | A Dev ingest record does not say which gate judged it. A backfill (`ci --json` over old history) judges every commit by today's rules, so commits that passed at the time can show as failed. Record the gate's version in the record, and show it | Trigger: the first backfill, or before phase 2 |
| Later | The Ops dead-letter queue's **Discard** fires with no confirmation, though it cannot be undone (`irreversible-needs-confirmation`). Administration's token panel shows the pattern: say what stops, then confirm | Trigger: the next change to the DLQ page |
| Later | Tenant CI templates (`workflow-templates/ci-*.yml`) run no process-gates job: a tenant gets the local hooks from `tenant init`, but nothing in CI checks its pushed commits or sends its record to the portal's Dev workspace. Add the job — gate, then `scripts/send_dev_record.py` — with its own design: it changes every tenant's CI, and the scratch tenants' generated commits carry no design trailers | Trigger: the first tenant that registers in the Dev workspace, or owner request |
| Later | A pointer by heading name (`docs/DESIGN.md › Section`) dies when that heading is renamed, and nothing reads it: the cross-reference rule reads pointers with a digit, on the lines a change adds. Catching it needs a check on the target side — a renamed or removed heading, and every pointer that named it | Trigger: the next dead heading-name pointer found |
| G6a | Evidence tokens in every `applies` answer; `P7-pydantic` and `P3-tracing` over the files a commit touches; `agentsmith pillars`; per-repo `pillars` policy with a ratcheting allowlist | **Done 2026-09-17** — review `.agent-rfc/reviews/governance-enforcement-g6a.md`. AgentSmith runs `enforce` with 18 seeded allowlist entries |
| G6b | Six more mechanical checks (`P2-dependencies`, `P7-async`, `P7-ts-any`, `P7-use-client`, `P10-gateway`, `P12-secrets`) and the narrowing of `P7-pydantic` to models built from data the code did not write | **Done 2026-09-17** — review `.agent-rfc/reviews/governance-enforcement-g6b.md`. Ten fixes rather than exemptions; the allowlist shrank from 18 entries to 2 |
| G6c | `agentsmith gates list` / `run` execute the `# agentsmith:gate` steps locally, with skips named (missing tool, service container, CI-only expression) and install lines dropped; the checklist's gates table is generated from the same tags | **Done 2026-09-17** — review `.agent-rfc/reviews/governance-enforcement-g6c.md`. 19 gates tagged here, and 20 across the tenant templates — 6 each in `ci-python-fastapi.yml` and `ci-ts-react.yml`, 7 in `ci-go.yml`, 1 in `agentsmith-gates.yml` |
| G2a | `--ide` adapters for six IDEs (one `GateEvent` in, each dialect's answer out), golden payload fixtures, the `ides` registry section, and generated hook configs where the schema is verified | **Done 2026-09-17** — review `.agent-rfc/reviews/governance-enforcement-g2a.md`. Cursor re-verified from vendor docs; Claude and Cursor configs generated, four await a confirmed schema |
| G2b | The shell pre-check: `--no-verify`, `core.hooksPath` overrides, `agentsmith approve` and writes to the gate's own files, refused in Claude Code and Cursor | **Done 2026-09-18** — review `.agent-rfc/reviews/governance-enforcement-g2b.md`. Deny-only: the cross-IDE warn channel does not exist, and the stop gate already catches a gated shell write |
| G4 | `--impact` maps a diff to the files a review must read, the lever groups and a `KG query:` hash the sign-off carries and the commit gate recomputes; session start prints the scope; the tenant CI template runs the same freshness check, blocking | **Done 2026-09-18** — review `.agent-rfc/reviews/governance-enforcement-g4.md`. Provisioning a graph at onboarding stays in G7 |
| G7 | `tenant init` provisions the config, the armed hooks, the IDE hook configs, the rule files, a committed KG and the artifact stubs; `verify_system.py --governed` lists provisioning gaps and evidence gaps separately; the stop gate and the sweep write `.agent-history.log` | **Done 2026-09-18** — review `.agent-rfc/reviews/governance-enforcement-g7.md`. G1–G7 are complete; G5b's migrations are what remain |
| Later | Antigravity, VS Code Copilot, Gemini CLI and Codex: confirm each hook CONFIG schema from a real session, then generate their configs. The adapters and fixtures are in place; what is missing is the shape of the file each tool reads | Trigger: when a session on that IDE can paste one |
| Later | husky's `prepare` script points `core.hooksPath` back at `.husky` on every `npm install`, disarming the gates in an adopted repository; `tenant adopt` warns, and the sweep re-arms only an unset path. Re-arm from a husky-compatible hook, or teach the sweep to re-arm a path it did not set | Trigger: the first adopted repository that uses husky |
| Later | The tenant CI templates (`ci-<stack>.yml`) still run no process-gate job; `workflow-templates/agentsmith-gates.yml` is one `tenant init` could also write | Trigger: the next tenant CI template change |
| Later | KYC Sentinel migrates to `records: single` (D4 ends) | Trigger: after G5a ships |
| Later | `tenant.yaml` is not covered by the IDE-config gitignore block. `docs/DESIGN.md` › IDE Config Security claimed for an unknown length of time that a `.agenticframework/tenant.yaml` holding a non-default tenant id or non-public endpoint URLs was "also included in the gitignore prompt for public repos". `hooks/post-checkout` appends seven IDE-config paths and has never included it. The doc now says so; whether the file should be ignored on a public repo is undecided — it is also the file `agentsmith tenant init` expects to be committed, so ignoring it is not obviously right | Trigger: a public tenant repo that carries real endpoint URLs in tenant.yaml |
| Later | A guardrail added to `hooks/pre-commit` later gets no vouch, and nothing says so. Guardrails 1–3 skip a staged file `.agenticframework/scaffold.json` vouches for (shipped 2026-09-29, archived); a fourth rule added tomorrow would run over the vendored `scripts/` and `runtime/` again and report a framework defect to a tenant who cannot fix it — the failure this repository has already had once. Nothing checks that a new guardrail consults `is_vouched`, and `scripts/test/test_fail_closed_declared.py` is the nearest model for what such a check would look like. Guardrail 4 is deliberately exempt: it asks whether the repository has an RFC at all, which is not a per-file question | Trigger: the next guardrail added to hooks/pre-commit |
| Now | The generated rule files (`.cursorrules`, `CLAUDE.md`, `GEMINI.md`, the Antigravity skills) are gitignored in this repo, so each clone's copies go stale whenever `agent-rules.yaml` changes and nothing can check them in CI. This one had carried the pre-`4f8e26a` P8 wording since slice B — the rule text agents in this repo were reading was two days out of date. Regenerated by hand on 2026-09-17; the fix is for the installer and `agentsmith upgrade` to regenerate them on every sync | Trigger: G2 |
| Later | The four `hooks/pre-commit` guardrails (AI markers, empty catch blocks, direct `cost_router` imports, an open RFC under enterprise policy) do not run in AgentSmith itself, which armed `.githooks` and has none in `.git/hooks`. Tenants now keep them: `tenant init` and `tenant adopt` chain the hooks directory the repository used (`.githooks/chain`). Fold the ones that still matter into the mechanical checks | Trigger: the next guardrail change |
| Later | Scope-derived pillar subset — ask only the pillars a change's paths implicate, each still carrying evidence. Held until G4: deriving the subset needs the impact query, and a wrong subset silently excuses a pillar | Trigger: G4 shipped and its impact query trusted |
| Later | Two agents in one checkout: owner decided 2026-09-16 to keep the lock a future extension. Evidence if it recurs: that morning a `mutation_check` run in a second session rewrote tracked files under an active session, and the stop gate's findings changed between turns | Trigger: owner request, or the next collision |
| Later | `sync` ignores `upgrade`'s exit code (`runtime/sync.py`, `upgrade(root, …, out=lambda _line: None)`): when the vendored refresh fails — no `tenant.yaml`, no installed scripts — `sync` prints nothing about it and still reports "vendored tenant: scripts/, runtime/, templates/ and fixtures/ are refreshed too" (`failure-is-not-a-result`). Surface the failure and leave the vendored note off a sync that did not vendor | Trigger: the next change to `runtime/sync.py` after the framework-root guard |

---

## Active: Governance contracts — every port, Dev and Ops 🟡 DESIGNED (2026-10-02)

Owner principle (2026-10-02), non-negotiable: AgentSmith and its tenants are decoupled **by contract**.
A tenant holds declarations, its own data and hash-recorded shims that call a declared command — no
framework code, no framework path. Umbrella design: `.agent-rfc/designs/governance-contracts.md`
(finishes `governance-providers.md`; reverses its decision to keep vendoring as a transport).

**OTS is the proving ground.** Its core function (template model, ingest, API) is frozen until its
governance is aligned; work in OTS on how AgentSmith governs it is in scope, slice by slice below.

| Slice | AgentSmith | Tenant step that proves it | Status |
|---|---|---|---|
| C1 | Gate v2 — the CI event, dev record as its output, a provider setup step for CI; `agentsmith-gates.yml` calls the declared command | OTS declares `providers.json`, CI calls the provider, vendored gate files go; KYC pins a release | **Built 2026-10-02** (`gate-contract-ci`); released in v2.1.0 — tenants can move |
| C2 | Gate contract 3 — commit and push; the knowledge graph as gate evidence | hooks in OTS and KYC become stubs; `map_codebase.py` leaves OTS | **Built 2026-10-03** (`gate-local-events`); tenants move after the release that carries it |
| C3 | Records — `contract/record/v1` | `send_dev_record.py` is never a tenant's file — already true since C1 (no tenant sends a record); proven by sender and receiver conformance | **Built 2026-10-04** (`record-contract`) |
| C4 | Rules — `contract/rules/v1`, `render` / `check`; `"provider"` replaces `@framework/` paths in a tenant's `process-gates.json` | OTS's rules move into its declaration and its CI calls the declared check; KYC's `@framework/` values become `"provider"` | **Built 2026-10-04** (`rules-contract`); tenants move after the release that carries it |
| C5 | Telemetry — `contract/telemetry/v1`: OTLP and a catalogue of attributes and instruments; `governance.telemetry.contract` on the Resource | OTS's template spans on plain OpenTelemetry — **done** as a governance-only change (uncommitted in OTS, with the frozen template work), 9/9 against the contract; KYC's smoke export passes once its pin moves | **Built 2026-10-04** (`telemetry-contract`) |
| C6 | Evals — `contract/evals/v1`: tenant-owned datasets with outputs, the scorecard, five verdicts, closed in CI unless declared | KYC's and OTS's eval steps call the declared command; KYC declares `no_verdict: warn` where its judge quota runs out | **Built 2026-10-06** (`evals-contract`); released in v2.2.0 — tenants can move |
| C7 | Security — `contract/security/v1` | vendored `fixtures/security/` goes | |
| C8 | Ops records — `contract/ops/v1`: run history out, HITL and UI feedback in | OTS's CD workflows send and receive by contract | |
| C9 | Vendoring retired; `upgrade` removed | no tenant holds a framework file, checked | |

**Closed 2026-10-06 — CI proves the contracts on an adopted scratch tenant** (`scratch-adopted`):
`agentsmith-scratch-adopted` is rebuilt by `tenant adopt` pinned to each commit; its gates run installs
the provider through the setup action at that commit and its adoption commit passes its own gate.

**Open — `sync` on a vendored tenant stages a refresh it cannot commit (found 2026-10-06, OTS).**
`sync` calls `upgrade`, which `git add`s the refreshed `scripts/`, `runtime/`, `templates/` and tries to
commit them; the tenant's gate refuses (no design), `sync` discards `upgrade`'s output, and the staged
framework code is swept into the "vouched" sync commit by the command sync prints. OTS's move left the
refresh out by hand. Fix with C9 (vendoring retired), or sooner: `sync` stops calling `upgrade`, or says
plainly what it staged. **Also from the tenant moves:** `sync` leaves hooks a tenant already holds
uncommitted out of its commit list and manifest (KYC's `chain`, `pre-commit`); its "vendored tenant"
note prints for a package tenant (KYC), where `upgrade` vendors nothing; and `agentsmith gate` /
`agentsmith rules` block on an open, empty stdin (the launcher always writes one, so CI is safe).
**And from KYC's evals move (2026-10-07):** `sync` moves `providers.json`'s gate `setup` to the new
release but leaves a gates workflow the tenant wrote itself at the old one, and says nothing — the
declaration and the CI step disagree until someone notices (KYC's was moved by hand).

**Open — a judge that is not the one the bars were calibrated for is not flagged (found 2026-10-07,
KYC).** A tenant's bars are calibrated against one grader (KYC's 0.95 / 0.95 / 0.75 against
`gemini-3-flash-preview`), but the judge a run uses is whatever the machine's mode selects: on a
machine in `local` mode KYC's judge resolves to `falcon3:3b`, which its own `models.yaml` calls
uncalibrated, and the provider grades against the same bars without a word. The scorecard records
the judge that answered (`judge_models_used`) but not the judge the bars belong to. Fix: the judge
role in `models.yaml` names the grader its `fail_below` was calibrated on; when the answering judge
differs, the scorecard says so in its reason and the launcher warns — a pass against a borrowed bar
is not the pass the bar describes (`failure-is-not-a-result`). **Also from the same move:** an
over-quota contract run raises two warnings, the launcher's and `run-evals.py`'s own annotation
fired inside the provider — one verdict should speak once.

---

## Active: KYC Sentinel "Running live" 🟡 NOT STARTED

**Goal:** take the tenant from offline/smoke-job to serving real traffic, so
the observability, HITL and promotion loops are exercised end-to-end rather
than asserted.

**Trigger:** fired — everything upstream of it is done.

**Blocked on:** standing up infrastructure and providing credentials. Not a
code blocker; deliberately deferred when the deploy pipeline was proven.

**What it needs** (from `KYC_Sentinel/DEVLOG.md` 2026-07-22):

1. Cloud SQL (`BUDGET_BACKEND=postgres`, `IDEMPOTENCY_BACKEND=postgres`),
   a Temporal server, Ollama for the sovereign `intake` route, and Phoenix.
2. Real provider keys: whichever variable the tenant's `judge` role declares —
   `GEMINI_API_KEY` as of 2026-08-19, when the judge moved back to
   `gemini-3-flash-preview` after Groq decommissioned the whole Llama family
   and `llama-3.3-70b-versatile` began 404ing on every call. It is **not** a
   fixed name and has now changed three times, so read it off the merged
   registry rather than this list — this line itself was four days stale.
   Plus the actor routes' key, `OPENROUTER_API_KEY` (research and analyst).
   No actor route uses Groq — that is deliberate, so exhausting an actor's
   quota cannot also take out its reviewer.

   Setting the judge key no longer turns all three judge-backed gates on at
   once: golden runs on every push, fairness and hallucination on alternating
   crons, because the three together need 22 judge calls against a free tier
   that allows 20 a day (KYC `DEVLOG.md` 2026-08-08).

   **This contradicts the judge binding's own note** in KYC `models.yaml`, which
   says the quota constraint "no longer binds" after a full 22-call cycle
   completed on 2026-08-19, and tells you not to restore the split without
   re-measuring. Re-measured 2026-08-23: the limit is real and hard —

       429 RESOURCE_EXHAUSTED
       quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier
       quotaValue: 20   model: gemini-3-flash

   so the split stands. The daily budget resets at midnight America/Los_Angeles,
   which is the only thing that clears it; probing says nothing about how much of
   the day's 20 remain, only that the per-minute window is open.
3. Swap `cd-staging.yml`'s Cloud Run **Job** for a `gcloud run deploy` of
   `worker.py` as a long-running service (`--no-cpu-throttling
   --min-instances=1`, docs/UserManual.md › Deploy via GitHub CI/CD), pointed at the real
   `TEMPORAL_ADDRESS`.
4. Then, in order: Phoenix/Ops Portal wiring → widget embed → first HITL
   round-trip through the portal → shadow-eval sampling on → first production
   golden case promoted.

Append progress to `KYC_Sentinel/DEVLOG.md` as you go.

---

## Demo publication (LinkedIn / Substack / Medium) 🟡 NOT STARTED

**Subject: KYC Sentinel**, not oil-price-demo. This file previously carried two
contradictory versions of this item; oil-price-demo was superseded as the demo
tenant when the purpose-built testbed was built.

**Trigger:** partially fired. The framework story and the tenant build are
publishable now; the operational screenshots (live Phoenix traces, a real HITL
round-trip) need "Running live" above.

**Article content:**

1. The framework architecture — the sixteen pillars, multi-agent, eval scorecard.
2. Building KYC Sentinel: why KYC is the domain where compliance features are
   load-bearing rather than decorative (`docs/testbed-tenant-spec.md` opening).
3. What building a tenant found in the framework — G1–G10, then the 1.1.0
   review findings. The honest version of this is the most useful part: a HITL
   gate that could approve without a human, a security harness grading the
   wrong repo, a "graceful skip" that failed CI.
4. CI/CD: GitHub Actions → GCP Cloud Run via WIF (keyless).
5. Screenshots: Phoenix traces, Ops Portal, HITL DLQ flow, eval scorecard.

**Source material:** `docs/PRODUCT_ARCHIVE.md` (build history, use as structure),
`README.md` (intro), `CHANGELOG.md` 1.1.0 (what the review found).

**Open cost:** Cloud SQL `temporal-pg` (~$7–10/month) and `temporal-server`
Cloud Run (min-instances=1) in `agentsmith-500916` are still live from the
oil-price-demo work. Either reuse them for KYC Sentinel's "Running live" or
tear them down — they are currently billing for nothing. Owner: Bobby.

---

Each future item records a **trigger condition** (the concrete signal that
means "build this now," not a calendar date), so a future session can decide
whether the trigger has fired instead of re-litigating whether the gap matters.

**Settled design decisions (do not re-open without a concrete reason):**
- MCP integration stays tenant-owned (BYO) — the framework ships no MCP
  client/server. Rationale in docs/DESIGN.md › Architecture by Layer.
- LLM self-correction is a separate opt-in method
  (`run_with_self_correction`), never inserted in front of the human DLQ path.
- The default model registry is local-only. Cloud tiers are a deliberate
  per-tenant opt-in, not something a budget breach can reach.

---

## Open from the onboarding audit (2026-09-13/14)

Found running every stack through a real scratch tenant's CI
(`docs/scratch-tenants.md`); fixed items are in `CHANGELOG.md` [Unreleased]
and `docs/PRODUCT_ARCHIVE.md`. Each was checked still open on 2026-09-14.

- **A day-one tenant's CI is red on every stack.** The strict harness fails on
  the shipped placeholder `risk_register.yaml` / `agency_manifest.yaml` (even
  non-strict fails on the manifest), and since 2026-09-14 Go and TS run it
  too. Deliberate — a placeholder is not a declaration — and now said in the
  hook's onboarding message and docs/UserManual.md's `tenant init` steps. The red
  run names the placeholder file, but not that this is the expected day-one
  state. **Trigger:** the first
  external tenant onboards, or someone proposes relaxing strict to get green.
- **Tenants provisioned before 2026-09-14 keep the old `rollback-notify`.**
  It named the default branch's head, not the deployed commit, under
  `workflow_run`. The hook never overwrites a composite action a tenant already
  has, and `ai-stack-upgrade` does not touch actions. AqlaarTeleologyStudio was
  synced by hand (`a4589a8`); no other vendored tenant exists today (KYC
  Sentinel does not use this action). **Trigger:** the next tenant onboarded
  from an older install, or the next fix to any composite action — at that
  point `ai-stack-upgrade` should refresh actions.
- **New tenants do not get the process gates automatically.** AqlaarTeleologyStudio
  and KYC Sentinel adopted them by hand on 2026-09-14 (`docs/process-gates.md`
  § Rolling out to a tenant). `agentsmith tenant init` and `hooks/post-checkout`
  write no `.agenticframework/process-gates.json`, `.githooks/`, settings hooks
  or CI job, and a vendored tenant's copy of `.githooks/` does not move on
  `ai-stack-upgrade`. **Trigger:** the next tenant onboarded, or the next change
  to `.githooks/` (which today must be re-copied into both tenants by hand).
- **Every release-download install path is broken while AgentSmith is private.**
  The documented `curl …/releases/latest/download/install-ai-stack.sh | bash`
  returns 404 to everyone — curl sends no GitHub login — and exits 0 having
  installed nothing; the installer's own fallbacks (`scripts.tar.gz`,
  `workflow-templates.tar.gz`, `github-actions.tar.gz`, `templates.tar.gz`,
  `hooks.tar.gz`) fail the same way for anyone running it outside a checkout.
  README, UserManual and OPERATIONS now say to install from a checkout
  (verified 2026-09-14: anonymous release page HTTP 404). **Trigger:** the repo
  goes public — then remove those notes — or the first collaborator who is not
  on this machine needs to install, at which point `gh release download` (which
  carries the login) should replace the anonymous URLs.
  *2026-09-25: the owner is flipping the repository to public. This item closes
  on that flip and not before — verify anonymously (`curl -sI` the release asset
  with no credential) rather than assuming, then remove the notes from README,
  UserManual and OPERATIONS. The tenant workflows no longer wait on it: they take
  the run's own token and fall back to the secret only for a private provider
  (`.agent-rfc/designs/public-provider-checkout.md`).*
- **KYC Sentinel's CI tests framework HEAD while it deploys v1.3.0.** Its
  `ci.yml` checks out `bobbyaqlaar/AgentSmith` with no `ref`, but its
  requirements pin `agentsmith-runtime @ …@v1.3.0`. **Trigger:** the next
  framework change that breaks compatibility with a pinned version.
- **KYC Sentinel's `cd-staging.yml` image build/push/deploy is unverified.**
  Rewritten for the private framework (BuildKit secret, `--image`), never run:
  GCP promotion is suspended. **Trigger:** promotion resumes.
- **`ai-stack-upgrade` may overwrite a tenant file that shares a vendored
  file's name.** The hook merges `scripts/` without clobbering and reports
  clashes; the upgrade path refreshes vendored files by name. Unverified
  against a real clash. **Trigger:** a tenant reports a lost script, or the
  next change to `ai-stack-upgrade`.
- **`ai-*` wrappers ship for one more release.** `templates/shell/ai-compat.sh`
  (copied to `~/.agent-framework/shell/`, never sourced by the installer) maps
  the old shell-function names onto `agentsmith`. **Trigger:** cutting the next
  minor release — delete it, its installer copy step and its test.
- **Existing tenant clones keep the hook copies they were created with.** git
  copies `~/.git_templates/hooks` into `.git/hooks` at `git init`/`clone`, so a
  clone made before 2026-09-14 still exits on `DISABLE_AI_STACK=true` without
  asking the org policy, and runs its Python with bare `python3`. No policy file
  is deployed on any machine today, so nothing is bypassable that was not
  already. **Trigger:** the first org policy deployed to a machine — refresh
  each clone's hooks (`git init` in the clone re-copies the templates).
- **A non-checkout install gets the CLI of the release tag, not `main`.**
  `install-ai-stack.sh` outside a checkout installs
  `agentsmith-runtime @ git+…@v$FRAMEWORK_VERSION`; v1.3.0 predates
  `runtime/machine/`, so that `agentsmith` has no `mode`, `check`, `dashboard`
  or `upgrade`. Moot while every release download 404s (entry above).
  **Trigger:** tagging the next release, which carries the commands.
- **The TS template supports npm and pnpm only; the Python install, pip and
  uv only.** Yarn/bun fail by name; Poetry/Pipenv get a warning and no
  dependencies. **Trigger:** a tenant on one of them — add a scratch app for it
  first (`docs/scratch-tenants.md` § Changing the tenants).
- **Local gates do not match Self-Test.** On a Python 3.14 venv, `mypy` fails
  on numpy's stubs; `verify_system.py --check-idempotency`/`--check-dlq` need
  `DATABASE_URL`. Since 2026-09-14 the checkout has a `.python-version`
  (3.11) and a `requirements.lock`, so `uv venv && uv pip sync
  requirements.lock` in the checkout builds what Self-Test runs; the local
  `.venv` on this machine predates that and is still 3.14. **Trigger:** a
  local gate is trusted as the pre-push check again.
- **Self-Test's security harness job does not install `requirements.lock`.**
  Since 2026-09-14 Self-Test's Python jobs and `install-ai-stack.sh` install
  the hashed lock, but the `security` job calls the tenant-facing
  `eval-security.yml`, whose `install-python-deps` action installs
  `requirements.txt` — ranges resolved against the index on the day. Left as
  is because that action is a tenant contract (a tenant has no
  `requirements.lock`). **Trigger:** a harness run that passes locally and
  fails in CI (or the reverse) on a dependency version, or the next change to
  `install-python-deps`.
- **The framework environment assumes a POSIX venv layout.** `install-ai-stack.sh`
  and the hooks look for `~/.agent-framework/.venv/bin/python`; a native
  Windows Python under Git Bash puts it at `Scripts/python.exe`, so the
  installer's verification would fail and the hooks would fall back to
  `python3`. WSL is unaffected. Untested — there is no Windows runner.
  **Trigger:** the first Windows (non-WSL) install.
- **Actions minutes.** With AgentSmith private, Self-Test alone was ≈1,900
  job-minutes/30 days (measured 2026-09-13) against GitHub Free's 2,000 —
  before the offline scratch build's strict harness runs added ~2 minutes to
  every Self-Test (2026-09-14), and before the five scratch tenants' weekly and
  per-change runs. **Trigger:** the first month a
  run is queued for lack of minutes.

## Known gaps carried forward from the 1.1.0 review

Small, specific, and deliberately not fixed in that release.

- **`SEC-TOOL-001` verifies the mechanism, not your allowlist.** Its runner
  smoke-tests `ToolRegistry` deny-by-default against the shipped *template*,
  so a tenant's green SEC-TOOL-001 says the enforcement works — not that the
  tenant's own `tool_allowlist.yaml` is sane. **Trigger:** an auditor reads the
  evidence pack as a statement about the tenant's tools.
- ~~**12 of 23 `SEC-*` controls have no runner**~~ — **closed.** All are bound.
  The last four (`audit_hmac`, `dlq_check`, `sovereign_smoke`, `rag_poison`)
  were closed by separating the claim that needs infrastructure from the claim
  that does not, rather than by relabelling anything: HMAC tamper-evidence is
  provable offline and append-only enforcement is a database trigger, so the
  latter became **`SEC-AUDIT-002`** and is the one remaining declared gap. An
  undeclared gap — `met`/`partial` with no runner — fails `--strict`.
  Live status: `docs/security-framework-map.md`.
- **`agency_manifest` is authored but ungraded** — both the framework's and
  KYC's manifests are real content that nothing validates (see above).
- **A tenant that removes its controls removes the gate with them.** Both
  detection gates are conditional on the control existing: the fairness parity
  floor applies only `if min_parity is not None`, and the hallucination
  detection-miss floor only `if hallucination_miss is not None`. Delete the
  `pair_id`s from a fairness fixture, or the planted case from a hallucination
  one, and the suite still passes on `avg_score` alone having measured no bias
  and no detection. Both report the absence honestly — "NOT MEASURED", "no
  positive control in this suite" — so this is a reporting-is-right,
  gate-is-silent split, not a false green.

  The framework's own fixtures are guarded by tests (`test_fairness_evals.py`
  asserts pairs exist, `test_hallucination_evals.py` asserts a positive control
  does), so this is reachable only through a tenant override. Left alone
  deliberately: making it hard-fail would red-build every tenant whose fixture
  predates the control, which is a release decision, not a fix.
  **Trigger:** a tenant's fairness or hallucination gate is green and someone
  asks what it measured. Found in the 2026-08-24 review pass.
- ~~**`.env.swp`**~~ — **gone.** The orphaned vim swap file is no longer on
  disk and was never tracked. This entry outlived the file it described.
- ~~**`scripts/verify_ttft.py:21`**~~ — **closed.** `from pathlib import Path`
  is no longer imported there and `ruff check` is clean on that file. The
  remaining `noqa` on the `_shared` import is deliberate and still correct.

  Both of the above were verified as false on 2026-08-24, which is the header's
  own instruction working: *"If an entry here says something is missing, check
  it still is."* A backlog that describes a fixed problem costs the same
  attention as one that describes a real one, and spends it on nothing.

---

## Future Phases — confirmed gaps, not yet scheduled

### A score records its judge but not its rubric version

Raised 2026-09-03 by an outside critique of LLM-judge practice, and it lands.

`scripts/run-evals.py` stores `"criteria": criteria.get("name", "default")` — a
static NAME. Meanwhile `scripts/promote-learning.py` appends to
`historical_learnings`, and `scripts/eval_judge.py` injects those into every
judge prompt. **The rubric mutates and the score does not record which version
graded it.** Two runs both stamped `criteria: "default"` may have been graded
under materially different criteria, and nothing downstream can tell.

What makes this worth fixing rather than noting is that **this codebase already
makes the argument, for the judge**. `eval_judge.run_judge` records `judged_by`
AND `judged_by_route` on every row, with the reasoning written out: a score is
not portable across graders, so "who graded this belongs with the score, not in
a single run-level field a substitution would silently falsify." That is exactly
the rubric's situation. The principle was established and applied to one of the
two inputs.

**Fix:** hash the resolved criteria (instructions + historical_learnings, after
merge) and store the digest per row beside `judged_by`; surface it in the
scorecard; refuse to compare scores across differing digests. Small, additive,
and it closes the half of the argument that is already written down.

**Related gaps from the same critique, deliberately NOT scheduled** — recorded so
the boundary is explicit rather than accidental: no confidence interval per score
(variance informs where a bar sits, but is not reported per run); no coverage or
decay measurement of the golden set against production traffic; case selection is
failure-driven rather than uncertainty-driven (no active learning); no linkage
from eval scores to business outcomes. The first is cheap and worth doing; the
last needs holdouts and traffic volume this project does not have.

### Team-shared RFC store (`AGENT_SHARED_RFC_DIR`) — specified, never built

Found 2026-09-01 during a documentation audit. `AGENT_SHARED_RFC_DIR` was
documented in **docs/UserManual.md** with two copy-pasteable `export` lines and the
claim that "agents and `run-evals.py` also read from this directory", and in
**docs/DESIGN.md** in three places including a security boundary for it. Nothing in
the codebase has ever read the variable, and there is no shared-RFC concept in
any module.

Both documents now say so. What is worth keeping from the old text is the
constraint, which was the considered part: sharing is **within one
organisation's workspace only** — shared RFC edges must not span tenant
repositories, and this must never become a path for cross-tenant production
data linkage. The Knowledge Graph stays strictly per-repo regardless.

**Trigger:** a team asks for RFC specs visible across their repositories. Until
then a symlink into each repo's `.agent-rfc/` does the job and does not pretend
to be a feature.

**Lesson, which is the general one from that audit:** a variable that is read by
nothing fails silently by construction. There is no error to see, so the only
thing standing between a user and a false belief is whether the documentation is
true. `scripts/test/test_documented_env_vars_exist.py` now checks that every
environment variable named in the docs is read somewhere.

### Compliance gap status boards (pointers, not copies)

Live status for the two compliance tracks is maintained in one place each — do
**not** duplicate their tables here:

- **UAE Regulatory:** [`docs/uae-regulatory.md`](uae-regulatory.md) +
  [`docs/iso-42001-control-map.md`](iso-42001-control-map.md). Still
  open there: live verification against a *named* UAE sovereign API (beyond the
  verified Ollama Falcon 3 pattern), and org-level certification work (never
  framework-owned).
  **Trigger:** a bid requires live sovereign-endpoint verification, or an
  auditor demands a licensed clause-ID matrix beyond the thematic pack.
- **Enterprise Delivery Model:**
  [`docs/delivery-model.md`](delivery-model.md). v1 soft pack shipped.
  Still open: hard-fail enterprise mode; auto-inject `delivery.*` defaults from
  `ai-tenant-init`; a CD step uploading the evidence pack as a release artifact.
  **Trigger:** an org wants promote blocked when a platform isn't approved.

### Tool Orchestration — provider function-calling wire-up

**Shipped:** `runtime/tool_registry.py` (`@tool` + YAML allowlist,
`SEC-TOOL-001`, tenant-attributed spans). MCP stays **bring-your-own**.

**Remaining gap:** `llm_gateway.complete()` still does not emit provider
function-calling request fields — the registry is allowlist/schema extraction,
not a tool-choice runtime.

**Trigger:** a tenant needs the LLM to choose among tools dynamically inside
the gateway request, not only fixed activity sequences.

### Perception & Input Parsing — prompt templating

**Shipped:** `runtime/structured_output.py` (`parse_llm_json`,
`SEC-OUTPUT-001`).

**Remaining gap:** no reusable prompt-template engine; prompts are inline
f-strings (KYC Sentinel has four such prompts across its agents).

**Trigger:** 2+ real call sites sharing the same prompt structure.

**Fix sketch:** `runtime/prompt_templates.py` — a minimal Jinja2 or
`string.Template` wrapper.

### Memory / RAG — remaining extensions (v1 shipped)

Shipped: `conversation_memory.py`, `embeddings.py`, `vector_store.py`
(memory / pgvector). See [`docs/rag-memory.md`](rag-memory.md).

**Remaining:** summarization eviction; auto-RAG in the gateway; ingest/chunk
CLI; a live pgvector CI job (the extension is often absent in bare Postgres).

**Trigger:** a tenant needs summarization or gateway-native retrieve.

### HITL self-correction — remaining extensions (v1 shipped)

**Remaining:** tenant-specific policies for which error classes opt in.
Multi-turn planner/tool-choice correction stays out of scope.

### Eval suites — remaining extensions (v1 shipped)

- **Hallucination:** expand golden cases beyond seed pairs; a human review UI
  for flagged cases.
- **Fairness:** domain-specific sets beyond seed pairs; statistical
  disparate-impact metrics beyond judge + pair parity.
- **TTFT:** portal chat UI streaming; TTFT on the non-stream path (not
  measurable without a fake first token). Not wired into KYC Sentinel's CI —
  it needs a live streaming provider.

### Input guardrail — remaining extensions (v1 shipped)

**Remaining:** tenant-specific PII vocabularies beyond the default patterns
(Emirates ID, email, phone, Luhn cards). Content moderation (toxicity) stays
out of framework scope — tenants declare a `moderation.hook`.

### Package rename — `runtime` → `agentsmith_runtime`

The distribution is `agentsmith-runtime` but imports as the generic top-level
`runtime`, which could collide in a crowded virtualenv. Noted in
`pyproject.toml`.

**Trigger:** a real collision, or the next major version — it breaks every
`from runtime.X import Y` in every tenant at once, so it is a 2.0.0 change.

---

## Appendix — Lessons (do not repeat)

Operational lessons distilled from past phases; full incident context in
`docs/PRODUCT_ARCHIVE.md` and `CHANGELOG.md`.

- **Review the branch, not the diff — and run the CI job list before pushing.**
  On 2026-08-24 three review passes over `scripts/` reported clean, and the push
  found `main` had been red for three commits: the portal could not build
  (`node:crypto` reached the Edge bundle via `middleware → authz → constantTime`),
  `SEC-RBAC-001` failed on a missing loader, and docs/DESIGN.md was missing
  `runtime/security_paths.py`. None were in the reviewed diff; all three were in
  what the branch was about to ship.

  Two habits would have caught all of them, and both are cheap:

  1. **Scope the review by what CI checks, not by what you edited.**
     `.github/workflows/self-test.yml` is the repo's definitive statement of
     "done". Every one of the three failures is a job in it, and all three
     reproduce locally in about ninety seconds. Read it as a checklist BEFORE
     pushing, not as a debugging aid after.
  2. **When a fix lands at "both" call sites, grep for the third.** The archive
     entry recording the loader fix said it was "now on both scripts" — one
     `git grep experimental-strip-types` printed twelve lines with the missed
     Python call site four lines below the fixed one. This is the same lesson as
     `return 2` for graceful skip, which is already in this list. It recurs
     because the fix always *looks* complete from inside the file you fixed.

  Note which pillar the miss maps to: pillar 15 (Ambiguous Signals) was applied
  hard and found real defects; pillar 2's five-step check — *what does this
  affect, are there downstream consumers* — covers four of the five misses and
  was not run at all. Working one pillar is not working the list.

  **A local run is only equivalent to CI if the git state matches.** The guard
  written for lesson 2 above passed locally and failed on the first push,
  because it swept `git ls-files` — and it was itself still untracked, so it
  never examined itself. Anything that derives its input from git sees a
  different repo before and after the commit. Sweeps should use
  `git ls-files --cached --others --exclude-standard`, which is the set that is
  about to be committed rather than the set already committed.

  Guards added rather than resolutions: `scripts/test/test_ts_runner_invocations.py`
  fails when any invocation of `node --experimental-strip-types` omits the
  loader, and `portal/test/edgeSafety.test.ts` fails when anything reachable
  from `middleware.ts` imports a Node-only builtin — that one is only visible to
  `next build`, since `tsc --noEmit` and `npm test` both pass on it.

- **A verification step must not regenerate the thing it verifies.**
  `verify_system.py --check-kg` called `map_codebase.run_map()` and then
  asserted the graph was non-empty and held known nodes — every assertion about
  the file it had just written, so it could only fail if the mapper broke. The
  committed graph was 703 lines stale with the gate green throughout.

  Two things fell out of fixing it, both worth keeping:
  - **Compare shape, not bytes.** `actions/checkout` stamps working-tree mtimes
    at checkout time, and the mapper walks the FILESYSTEM, so a committed graph
    also carries build output (`portal/next-env.d.ts`) and Guardrail nodes with
    ABSOLUTE paths. Comparing all of it red-built every CI run, which is worse
    than the weak gate — a gate that always fails gets deleted. Compare only
    git-tracked, reproducible content.
  - **An incremental cache cannot repair what it never re-reads.** `run_map`
    skips files whose stored mtime matches, so a graph wrong for any reason
    other than a file edit — a hand edit, a bad merge, a truncated write —
    survives every subsequent run. A corrupted graph reached a public repo this
    way. `run_map(force=True)` / `map_codebase.py --force` exists now, and any
    caller that VERIFIES the graph forces; the post-commit hook keeps the fast
    path.

- **A test double must never be more capable than the real thing.** KYC
  Sentinel's original fake gateway aliased `complete_stream` to `complete`,
  hiding a production crash on the analyst's own route. `runtime/testing.py`'s
  shipped double now refuses to stream what the real gateway can't.
- **A guard assertion inside the `try` it guards is not a guard.** Two F-scenario
  drivers raised `AssertionError` inside a block caught by
  `except Exception`, so they reported their control proven while it was
  broken — through CI and a Cloud Run smoke job.
- **Config that is read from two places will disagree.** There were four
  copies of "which model is the architect tier", a judge id in a constant
  *and* in models.yaml, and a security pack that was a byte-copy of its own
  template. Every one had drifted. Read from one source; guard it with a test.
- **cwd-relative vs install-relative is a real distinction.** The security
  harness resolved the tenant pack from its install location, so every tenant
  graded the framework's pack. Two roots that coincide during self-test hide
  this completely.
- **"Skip gracefully" means exit 0.** `return 2` from `run_scorecard()` still
  failed the CI step, so every fresh tenant went red for not yet having a
  golden dataset. This lesson was recorded here and applied to only one of two
  call sites for months.
- **A CI callee must ship with its caller.** `ci-python-fastapi.yml`
  referenced `eval-security.yml`, which `ai-tenant-init` never copied — GitHub
  rejects the whole workflow as invalid, not just the missing job.
- **GitHub Actions rejects YAML anchors.** They parse fine locally and fail on
  the runner.
- **Groq 429 retry needs FULL JITTER** — `(2**attempt)*5 + random.uniform(0, 3)`.
  A bare `2**n * 5` gives concurrent CI jobs identical waits. Baked into
  `scripts/cost_router.py`.
- **`# fail-open:` convention + global-copy drift** — the pre-commit hook
  executes the GLOBAL `~/.agent-framework/scripts/check_bare_except.py`, not
  the repo copy; sync both when changing checker behaviour.
- **The same drift bites the agent RULES, and it is easy to miss because the
  repo tests all pass.** `git init` runs `~/.git_templates/hooks/post-checkout`,
  which reads `~/.agent-framework/templates/agent-rules.yaml` and
  `~/.agent-framework/scripts/generate-ide-config.py`. Edit the repo alone and a
  freshly provisioned project still gets the OLD pillars — observed 2026-08-17,
  where the repo had 14 pillars and 6 targets while a real `git init` produced 10
  pillars and 3. Nothing failed; it just quietly provisioned the previous
  version. After changing `templates/agent-rules.yaml`,
  `scripts/generate-ide-config.py` or `hooks/*`:

      cp templates/agent-rules.yaml       ~/.agent-framework/templates/
      cp scripts/generate-ide-config.py   ~/.agent-framework/scripts/
      cp hooks/post-checkout              ~/.git_templates/hooks/

  That targeted copy is the FAST path, and it is deliberately not the supported
  one. Re-running the installer from the checkout is:

      bash install-ai-stack.sh    # from the repo root

  When `INSTALLER_DIR` resolves to a checkout it overwrites the global copies of
  `scripts/`, `templates/agent-rules.yaml` and all four `hooks/*` — so it also
  refreshes `workflow-templates/`, `github-actions/` and the on-prem template,
  which the three `cp` lines above miss. It has no skip flags, so it re-runs the
  whole install (pip, Ollama checks); use the `cp` shortcut when you have touched
  only rules or hooks, and the installer when you have touched anything else.

  Either way, verify against a throwaway `git init` rather than trusting the
  copy — that is what turned this up.
- **Cloud SQL from Cloud Run** — use the Auth Proxy
  (`--add-cloudsql-instances`, Unix-socket `DATABASE_URL`), never
  `sslmode=no-verify`; grant the Compute SA `roles/cloudsql.client` and
  `roles/secretmanager.secretAccessor` per secret.
- **New GCP projects grant the default compute SA nothing.** Cloud Run
  `--source` deploys use it via Cloud Build; it needs
  `roles/storage.objectViewer`, `roles/artifactregistry.writer`,
  `roles/logging.logWriter` before a first deploy will work.
- **WIF attribute condition is one expression** — adding a repo means updating
  `==` to `in [...]`, or the new repo gets
  `unauthorized_client: rejected by attribute condition`.
- **oil-price-demo: cherry-pick, don't rebase** — the post-commit hook
  regenerates the Knowledge Graph on every git operation. `AGENT_KG_DEFER=1 git
  rebase ...` now skips the per-step rebuild (run `python3
  scripts/map_codebase.py` once afterwards).
