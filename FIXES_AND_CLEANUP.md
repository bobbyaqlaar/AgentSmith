# AgentSmith — Remaining To-Do Items

**Last reviewed:** 2026-07-29 (post-1.1.0 release + cross-repo review)

> **Scope:** this document owns only *not-yet-done* work: the active item and
> confirmed future gaps with their trigger conditions. Completed build history
> lives in `Product_Archive.md`; the formal specification is `SPECS.md`;
> operator procedures are `OPERATIONS.md`; release notes are `CHANGELOG.md`.
>
> If an entry here says something is missing, check it still is — this file
> spent a week claiming the testbed deploy had not started, six days after it
> had.

## Current state (2026-07-29)

**v1.1.1 is released.** v1.1.0 was the first actually-published version (1.0.0
was documented but never tagged, so no tenant could pin); v1.1.1 fixed the
install path itself — the bootstrap script and its `.sha256` had never been
release assets, so the documented `curl … | bash` 404'd at every version, and
silently, because that pipeline exits 0 on a 404.

Both suites are green: `python3 -m pytest -q` here and in `../KYC_Sentinel`.
No count is quoted — one was, and went stale three times in a single working
session. KYC Sentinel's strict security harness and adversarial eval gate are
green in CI; the three judge-backed gates skip until the judge has credit.

The **KYC Sentinel testbed tenant** (`../KYC_Sentinel`) is built, pushed,
CI-green and deployed as a GCP staging smoke job — full history in
`Product_Archive.md` "T1–T4". Everything code-side is done.

**The one open build item is running it against real backends** — see below.

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
   --min-instances=1`, OPERATIONS.md §4), pointed at the real
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

1. The framework architecture — Ten Pillars, multi-agent, eval scorecard.
2. Building KYC Sentinel: why KYC is the domain where compliance features are
   load-bearing rather than decorative (`docs/testbed-tenant-spec.md` opening).
3. What building a tenant found in the framework — G1–G10, then the 1.1.0
   review findings. The honest version of this is the most useful part: a HITL
   gate that could approve without a human, a security harness grading the
   wrong repo, a "graceful skip" that failed CI.
4. CI/CD: GitHub Actions → GCP Cloud Run via WIF (keyless).
5. Screenshots: Phoenix traces, Ops Portal, HITL DLQ flow, eval scorecard.

**Source material:** `Product_Archive.md` (build history, use as structure),
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
  client/server. Rationale in SPECS.md §4a.
- LLM self-correction is a separate opt-in method
  (`run_with_self_correction`), never inserted in front of the human DLQ path.
- The default model registry is local-only. Cloud tiers are a deliberate
  per-tenant opt-in, not something a budget breach can reach.

---

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

### Compliance gap status boards (pointers, not copies)

Live status for the two compliance tracks is maintained in one place each — do
**not** duplicate their tables here:

- **UAE Regulatory:** [`docs/uae-regulatory.md`](./docs/uae-regulatory.md) +
  [`docs/iso-42001-control-map.md`](./docs/iso-42001-control-map.md). Still
  open there: live verification against a *named* UAE sovereign API (beyond the
  verified Ollama Falcon 3 pattern), and org-level certification work (never
  framework-owned).
  **Trigger:** a bid requires live sovereign-endpoint verification, or an
  auditor demands a licensed clause-ID matrix beyond the thematic pack.
- **Enterprise Delivery Model:**
  [`docs/delivery-model.md`](./docs/delivery-model.md). v1 soft pack shipped.
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
(memory / pgvector). See [`docs/rag-memory.md`](./docs/rag-memory.md).

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
`Product_Archive.md` and `CHANGELOG.md`.

- **Review the branch, not the diff — and run the CI job list before pushing.**
  On 2026-08-24 three review passes over `scripts/` reported clean, and the push
  found `main` had been red for three commits: the portal could not build
  (`node:crypto` reached the Edge bundle via `middleware → authz → constantTime`),
  `SEC-RBAC-001` failed on a missing loader, and SPECS.md was missing
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
