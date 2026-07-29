# Changelog

All notable AgentSmith framework changes. The framework releases on its own
semver (SPECS.md §28); tenant apps pin `framework.version` in
`.agenticframework/tenant.yaml` and upgrade on their own schedule via
`ai-stack-upgrade --to <version>`.

Release notes must call out span-attribute or hook-interface changes
explicitly — those are the two contracts tenant repos depend on.

## Compatibility Matrix

Canonical copy — SPECS.md §28 mirrors the current row.

| Framework version | Min Python | Min LangGraph | Min Phoenix | Breaking changes |
|---|---|---|---|---|
| 1.1.x | 3.11 | 0.2 | 4.0 | Default model registry is local-only; `local_large`/`local_small` roles removed |
| 1.0.x | 3.11 | 0.2 | 4.0 | Initial public release (documented only — never tagged or published) |

## [Unreleased]

### Added — the judge is configurable across three vendors

`models.yaml` can now point the `judge` role at Anthropic, xAI or Google AI
Studio by editing one entry. All three speak OpenAI-compatible APIs, so no
adapter was needed — `xai` (`XAI_API_KEY`) and `google_ai` (`GEMINI_API_KEY`)
join the provider/credential map, with default hosts on both call paths.

The motivation is independence, not availability. `judge_independence_warning`
only catches *identical* model ids, so a Claude judge grading a Claude actor
passes the check while sharing a training lineage and RLHF profile — and models
rate their own family's output higher. Cross-vendor judging removes the
mechanism instead of mitigating it.

- **`fail_below` can be declared beside the judge**, as a float or per-suite
  mapping. A threshold is calibrated for one grader; with a swappable judge a
  single global number silently compares each new judge against the last one's
  calibration. Precedence: CLI → registry → env → 0.80.
- **`scripts/verify_judge_route.py`** proves a judge resolves, has its
  credential, reaches the host its provider implies, and returns parseable
  JSON — before it is trusted to gate merges.
- **Provenance records the resolved route**, not just the requested id
  (`judged_by_route`, `judge_routes_used`). An id alone cannot reveal a
  misroute.

### Fixed — three silent misroutes

- **`cost_router._route_for_model` ignored the registry**, substring-matching
  the model id (`claude`/`gpt`/`llama`) and falling through to **localhost
  Ollama** for anything else. `grok-4` and `gemini-2.5-pro` were both served by
  a local model under their own names. It was fragile for declared models too:
  `llama-3.3-70b-versatile` routed to Groq only when `GROQ_API_KEY` happened to
  be set in the process, and to localhost otherwise. Now registry-first, with
  the heuristics kept only for undeclared ids.
- **The registry merge leaked fields between different models.**
  `load_model_registry` shallow-merged a tenant role over the framework's, so a
  tenant judge declaring a different `id` still inherited the framework entry's
  `endpoint`, `cost_per_*_token` and `degrade_to`. Live consequences: KYC
  Sentinel's `claude-opus-4-8` judge carried `endpoint: ${OLLAMA_BASE_URL}/v1`,
  so the gateway posted Claude requests at the Ollama host; a frontier model
  inherited a free tier's zero costs, reading as costless to budget
  reservation; and removing `degrade_to` from a tenant file did **not** remove
  the behaviour, because the framework's value showed through — the judge role
  that release notes above describe as having no fallback still had one. A
  tenant entry with a different `id` is now taken wholesale; same-id entries
  still merge.
- **An unparseable judge reply scored 0.0 instead of erroring.** `falcon3:3b` —
  the framework's own default judge — returns an **empty string** to a
  JSON-only scoring prompt (verified against a local Ollama with the model
  pulled; `qwen2.5` answers the identical prompt correctly). With no `error`
  set, the all-errored skip could not fire, so every case scored 0.00 with
  blank notes and a working application read as failing its entire scorecard.
  Now reported as a judge error with the reply preview.

### Changed — the eval judge never falls back to another model

The two provider-calling paths now differ **explicitly** rather than by
omission. `runtime/llm_gateway.py` (workers, activities, tenant agents) walks
the `degrade_to` chain on provider exhaustion. `scripts/cost_router.py` (the
eval judge, and nothing else) classifies exhaustion identically and then fails,
reporting the cause.

A degraded *actor* produces worse output that a good judge still catches. A
degraded *judge* writes confident verdicts into the same `score` field, against
the same threshold, gating the same merges, with nothing downstream able to
tell. Scores are only comparable against the grader they were calibrated for.

- **`is_provider_exhausted` moved to `runtime/provider_dispatch.py`** — already
  the shared seam between the two paths, so "is this exhaustion?" has one
  definition even though the two answers to "what now?" differ. The gateway
  keeps its method as a delegating shim; no behaviour change there.
- **Per-case verdict provenance.** Every result row carries `judged_by`, and
  `eval_results.json` gains `judge_models_used` alongside `judge_model` (which
  is now explicitly *requested*, not *used*). A scorecard whose verdicts came
  from more than one model **fails** — averaging across graders and comparing
  to one threshold is meaningless. Additive keys only; `delivery_evidence.py`
  and the CI artifact uploads are unaffected.
- **`cost_router` must not grow a ladder.** A test asserts it never references
  `degrade_to`, so adding one fails with the rationale attached rather than
  silently changing what every stored score means.

### Fixed

- **An advisory LLM call could fail a whole KYC application.** `agents/judge.py`
  makes a critique call whose result is deliberately discarded — the verdict
  comes from deterministic citation and parity checks — but an exception from
  it propagated and failed the activity. A call whose answer nobody reads could
  block onboarding. Now fail-open, with the outage logged.

  This was hidden by the judge role's `degrade_to`, which on an outage quietly
  substituted a weaker model to write a critique nobody reads. Removing the
  degrade exposed it. Tests cover both directions: an unreachable judge does
  not block, and a bad citation still flags when the judge is down.
- **A false safety claim in KYC Sentinel's `models.yaml` and RFC-002.** Both
  said `warn_if_judge_not_independent` would catch a degrade that collapsed
  judge and analyst onto one model. It cannot — `agents/judge.py` passes the
  ids *declared* in the merged registry, so it validates configuration and is
  structurally blind to any runtime substitution.
- **`README.md` called the gateway the "single choke point for provider
  calls"** without qualification, where `SPECS.md` correctly scoped it to
  production workers. The eval harness is the one deliberate exception.
- **`PgVectorStore` bypassed the connection pool** — the last raw
  `psycopg2.connect()` in the codebase, and the store `pg_pool.py`'s docstring
  forgot to list. It opened a connection per `add()` **and** per `query()`, so
  every RAG lookup paid a TCP + auth round-trip: exactly the cost `pg_pool`
  was built to remove. It also leaked, since the call sites used
  `with psycopg2.connect(...) as conn:` and psycopg2's connection context
  manager wraps the *transaction*, leaving the socket open. Rewritten to
  `try/finally` — a `with` on a pooled borrow never returns it and would
  exhaust the pool instead. `runtime/test/test_pg_pool_coverage.py` fails on a
  new raw connect, an unbalanced borrow, or a stale docstring list.
- **`docs/superpowers/.../2026-07-10-reliability-pack-v1*.md` had no inbound
  link** from anywhere, unlike its security-harness counterpart in SPECS. The
  threshold and pair-parity rationale lives there; now referenced from
  OPERATIONS' reliability-suite section.

## [1.1.1] — 2026-07-29

Install-path release. v1.1.0 published the artifacts the installer downloads
but not the installer itself, so the documented bootstrap command never worked
at any version; the local-model instructions had also drifted off the registry.
No API changes — no span-attribute or hook-interface changes.

### Fixed — the documented install path

- **`install-ai-stack.sh` is now a release asset**, with a published
  `.sha256` (and a GPG `.sig` when signing is configured). It never was one:
  the release shipped only the tarballs the script fetches, so
  `curl …/releases/download/<tag>/install-ai-stack.sh | bash` — the first
  command in OPERATIONS.md — 404'd at **every** version, and the checksum the
  docs piped into `shasum --check` had never existed. Nothing surfaced it
  because `curl -fsSL … | bash` on a 404 **exits 0**: curl writes to stderr,
  bash runs an empty script, and the pipeline reports bash's status, so a dead
  URL looks like a clean install that silently did nothing.
- **One install path, not two.** README/UserManual pointed at
  `raw.githubusercontent.com/…/main/` (unversioned, unpinnable, no integrity
  check) while OPERATIONS pointed at a release URL that 404'd. Everything now
  uses `releases/latest/download/`, with the pinned + checksum-verified form
  documented for team environments. The checksum step verifies *before*
  executing rather than after.
- **`ollama pull` instructions matched no model the framework routes to.**
  UserManual told users to pull `llama3`, `mistral`, `gemma2` (~15 GB); the
  registry needs `qwen2.5`, `llama3.2:3b`, `falcon3:3b`, `smollm2` — zero
  overlap, so a correct first-time setup left local mode unable to make a
  single call. `ai-stack-check` already reported the right models; only the
  docs were wrong. They now use `ollama pull $(ai-stack-required-models)`,
  which reads the merged registry, and routing is described by **role**
  (`architect`/`developer`/`validator`/`fast`) rather than by model name, so
  the same drift cannot recur.
- **SPECS.md declared version 1.0.0** while claiming in the same sentence to
  match `FRAMEWORK_VERSION` (1.1.0) — pinned now by
  `scripts/test/test_version_consistency.py`, which also fails a version bump
  that ships without release notes.

### Guards

- `test_release_artifact_contract.py` gained
  `test_the_installer_itself_is_a_release_asset` and
  `test_docs_only_reference_artifacts_the_release_builds`. The existing tests
  could not have caught this: they verify artifacts the installer *downloads*,
  and it does not download itself — so the docs are now part of the contract.
- `test_version_consistency.py` (new) ties SPECS.md, `pyproject.toml` and
  `FRAMEWORK_VERSION` together.

### Fixed — evals (carried from 1.1.0)

- **An unreachable judge no longer fails an eval gate.** When *every* case
  errors, no verdict came back and there is no quality signal to gate on — the
  same class as the missing-credential preflight — so the suite exits 0 with
  the provider's message. Partial errors still fail: a judge that answers some
  cases and not others may be signalling something real. This is a deliberate
  change to gate semantics; both sides of the boundary are pinned by tests
  (`scripts/test/test_fairness_evals.py`).
- **Provider errors surface the response body**, truncated to 600 chars, instead
  of `raise_for_status()`'s bare status line. `run-evals.py` also separates
  "scored 0.00" from "never got a verdict" — an errored judge previously printed
  a column of empty `quality_notes`, which read as *the application* failing
  every case. Three wrong root-cause guesses came out of that ambiguity before
  the body was printed and named the real one. Keys travel in headers, never
  response bodies, so this does not widen credential exposure.
- **Judge credential lookup honours the role's `api_key_env`** and is resolved
  from the merged registry rather than a hardcoded provider, so it follows the
  `judge` role wherever a tenant points it. New
  `--skip-without-judge-credentials` moves the decision out of CI YAML, which
  cannot look up a secret by a name computed at runtime.
- **Credential lookup degrades against an older pinned runtime.** `scripts/` can
  be newer than the `runtime` wheel a tenant pins; when
  `credential_env_for_model` is absent, returning `None` meant "can't tell,
  don't skip" and ran a full suite of failing judge calls.

## [1.1.0] — 2026-07-29

**First actually-published release.** 1.0.0 was written up below and dated
2026-07-11, but no `v1.0.0` tag was ever created and no release artifacts were
ever built — so `install-ai-stack.sh`'s `releases/latest/download/*.tar.gz`
path 404'd and no tenant could pin a version. Nothing external consumed 1.0.0;
this is the first tag.

**Upgrading from a 1.0.x checkout:** if a tenant `models.yaml` points a
`degrade_to` at `local_large` or `local_small`, repoint it — those roles are
gone (they had become duplicates of `architect` and `developer`). Tenants
relying on cloud routing must now declare it: the framework defaults are
local-only. `framework.version` pins in `.agenticframework/tenant.yaml` move
from `1.0.x` to `1.1.x`.

### Changed — Local-only default model registry (2026-07-29)

- **`runtime/models.yaml` now routes every role to Ollama.** `architect:
  qwen2.5`, `developer: llama3.2:3b`, `validator: falcon3:3b`, `fast:
  smollm2`, chaining `architect → developer → validator → fast → halt`. No
  prompt leaves the machine and no call is billable under framework defaults;
  every tier is zero-cost, so the budget ladder degrades to a smaller local
  model instead of across a trust boundary.
- **Removed roles:** `local_large` (qwen2.5) and `local_small` (llama3.2) —
  now duplicates of `architect` and `developer`. Nothing in the codebase
  referenced them by name; `templates/uae-sovereign/models.yaml` defines its
  own `local_small` and is unaffected. A tenant `models.yaml` or
  `routing_overrides` pointing a `degrade_to` at either name must be
  repointed.
- **`groq_fast` and `vertex_gemini` are commented out**, not deleted — both
  blocks are preserved in place with their verification notes. Uncomment to
  opt back in. `groq_fast` was previously in the default chain
  (`validator → groq_fast → local_large`), so a budget breach could reach a
  billable cloud model from the defaults; it no longer can.
- **Prerequisite:** `ollama pull qwen2.5 && ollama pull llama3.2:3b &&
  ollama pull falcon3:3b && ollama pull smollm2`. `ai-stack-check` in
  `install-ai-stack.sh` now verifies exactly these four (it had drifted to
  checking `llama3`/`mistral`/`gemma2`, none of which the registry routed to).
- **New `judge` role (`falcon3:3b`)** — the eval judge is now declared in the
  registry rather than hardcoded in `scripts/_shared.py`.
  `_shared.judge_model()` resolves `AGENT_JUDGE_MODEL` → the `judge` role in
  the **merged** registry → `DEFAULT_JUDGE_MODEL` (now only a last-resort
  fallback for scripts-only installs where `runtime/` isn't importable).
  `runtime/` is imported lazily and its absence tolerated, so the
  scripts↔runtime vendoring boundary still holds.
  **Effect for tenants:** a tenant declaring its own `judge` role now gets its
  CI evals and its runtime judge on the same model automatically. KYC Sentinel
  resolves to its declared `claude-opus-4-8` instead of the framework
  constant — previously those were two independent settings that could
  silently disagree. A blank `AGENT_JUDGE_MODEL=` is now treated as unset
  rather than passed through as an empty model id.
  **Judge/actor separation:** `judge` is `falcon3:3b`, deliberately not
  `architect`'s `qwen2.5`, so the grader is never the model that wrote what it
  grades — asserted by a test against
  `runtime.judging.judge_independence_warning`. It does share `falcon3:3b`
  with `validator`, unavoidable in a four-model local registry; that overlap
  only matters if you grade validator output specifically, in which case add a
  fifth local model. `judge` degrades to `fast`, not `validator`, since the
  latter would have been a same-model no-op dressed as a fallback.
- **`install-ai-stack.sh` no longer exports `AGENT_JUDGE_MODEL`.** It had
  pinned a stale `claude-3-5-sonnet-20241022` into the shell profile, and
  since the env var wins over the registry, that default would have overridden
  every repo's declared `judge` role machine-wide.
- **Every model id now resolves from `models.yaml`.** There were four
  independent copies of "which model is the architect tier" and all four
  disagreed — the registry, `cost_router.py`, `multi_agent_system.py`, and the
  CI templates' `AGENT_JUDGE_MODEL || 'claude-sonnet-4-6'` — so editing
  `models.yaml` changed almost nothing. New `_shared.role_model(role,
  fallback)` and `_shared.provider_models(provider)` are the single accessor;
  the registry is cached per cwd rather than re-parsed per lookup. Converted:
  - `cost_router.py` — the five route tiers (`AGENT_MODEL_ARCHITECT` →
    `architect`, `COMPLEX` → `developer`, `STANDARD` → `validator`, `FAST` and
    `LOCAL` → `fast`). Env var still wins for a per-run override.
  - `multi_agent_system.py` — the same table, which had drifted separately
    (`claude-3-5-sonnet-20241022` where cost_router said `claude-sonnet-4-6`).
  - `verify_system.py` and `install-ai-stack.sh`'s `ai-stack-check` — the
    "is it pulled?" preflight, now via a shared `ai-stack-required-models`
    shell function that calls `provider_models("ollama")`, so the two checks
    cannot disagree. Both also match exact ids: the old substring test
    reported `llama3` present because `llama3.2:latest` happened to exist.
  - `verify_ttft.py` — `DEFAULT_MODEL` was `falcon3:1b`, an id the registry
    never referenced, so the TTFT number described nothing in the system.
  - `verify_sovereign_endpoint.py` — reads
    `templates/uae-sovereign/models.yaml`, the profile it exists to verify.
  - `workflow-templates/*.yml` (7 occurrences) — dropped the
    `|| 'claude-sonnet-4-6'` fallback. It looked harmless but the env var wins
    over the registry, so every tenant CI run overrode its own declared judge.
  Guarded by `scripts/test/test_no_hardcoded_model_ids.py`: a model id may
  appear in `scripts/` or `runtime/` only on a line resolving it from the
  registry, or with `# model-literal-ok: <reason>` (the same convention as
  `# fail-open:`). Docstrings and comments are exempt — recording what a
  default used to be is history, not configuration.
- **Docs:** SPECS §5 `_shared.py` row, §7 env table, §21 decision 8, §29
  registry snippet + `vertex_gemini` note; OPERATIONS §0 env block + §4 Vertex
  AI paragraph; UserManual §8 judge-model section; `shadow-eval.py` docstring.

### Fixed — Review findings, phase 2 (2026-07-29)

- **Security harness graded the wrong repo.** `run-security-checks.py`
  resolved the `.agent-rfc/security/` pack under review from
  `_install_root()` (file-relative), so a tenant running
  `cd my-tenant && python3 $AGENTSMITH_DIR/scripts/run-security-checks.py
  --strict` graded the **framework's** pack, not its own. The pack
  `ai-tenant-init` seeds into a tenant (G5) was read by nothing, and a
  tenant's green SEC-RISK-001 was evidence about a different repo. New
  `_tenant_root()` resolves it from cwd (walk up to `.git`, same semantics as
  `_shared._repo_root()`), overridable with `AGENTSMITH_TENANT_ROOT`; the
  control registry and templates still come from the install root. The
  framework-grading-itself path is unchanged — both roots agree there.
- **An un-edited security pack now fails `--strict`.** The shipped risk
  register is a placeholder by design and validates perfectly, so a repo that
  seeded the pack and never filled it in passed strict CI and published an
  evidence pack citing `RISK-EXAMPLE-001`. `SEC-RISK-001` now fails (warns,
  non-strict) when the register still carries template sentinel ids.
  Validating the template *as* the template — the `use_template_fallback`
  path — is unaffected.
- **The framework's own `.agent-rfc/security/` pack is now real.** All four
  files were byte-identical copies of `fixtures/security/templates/`, down to
  `organization: "REPLACE_ME"`, so the framework's self-test graded its own
  placeholders. Replaced with the framework's actual risks, high-impact
  actions, allowlist posture and NIST role mapping.
- **`eval-security.yml` was never provisioned into tenants.**
  `ci-python-fastapi.yml` does `uses: ./.github/workflows/eval-security.yml`,
  but the workflow was missing from `install-ai-stack.sh`'s copy list — and a
  missing callee makes GitHub reject the entire CI workflow as invalid, so
  every Python/FastAPI tenant was provisioned with CI that could not run. Added
  to the list, with a test asserting every `uses: ./.github/workflows/*`
  referenced by a template both exists and ships.
- **Drift guards for the copies that must stay identical:**
  `.github/workflows/eval-security.yml` ≡ `workflow-templates/eval-security.yml`
  (framework self-test vs tenant CI) is asserted in `scripts/test/`; KYC
  Sentinel's vendored `gcp-auth` composite action is diffed against the
  framework checkout its CI already clones.
- **`pytest.ini` runs both suites.** `testpaths = runtime/test scripts/test`
  (plus `pythonpath = . scripts`): a bare `pytest` collected 171 of 292 tests
  and reported green while skipping the security harness, eval suites, hooks
  behaviour, cost router and promotion loop.
- **`judge_model()` never actually read the registry in real runs.** Every
  `scripts/*.py` is invoked as `python3 scripts/foo.py`, which puts `scripts/`
  on `sys.path[0]` and NOT the repo root, so the lazy `import runtime` failed
  in exactly the normal invocation path and every run silently fell back to
  `DEFAULT_JUDGE_MODEL` — invisible only because the constant was kept in step
  with the role. `_shared.load_registry()` now puts the install root on the
  path first. A tenant's declared `judge` role reaches `run-evals.py` /
  `shadow-eval.py` for the first time; regression test invokes a script as a
  subprocess rather than trusting pytest's sys.path.
- **`verify_system.py` checked a stale, loosely-matched model list.** It
  required `llama3`/`mistral`/`gemma2` by substring, so `llama3` reported
  present because `llama3.2:latest` happened to be installed while the models
  the registry actually routes to went unverified. Now reads the ollama-provider
  ids from the merged registry (same single-source principle as the judge) and
  matches exact ids. `install-ai-stack.sh`'s `ai-stack-check` carried the same
  stale trio and was corrected alongside it.
- **`map_codebase.py` indexed build output.** `dist`/`build` were ignored but
  not their JS equivalents, so the portal's Next.js output contributed 297 of
  the Knowledge Graph's 449 nodes — minified bundles riding into the agent
  context window `fetch_subgraph_context_window` builds. Added `.next`,
  `.nuxt`, `.svelte-kit`, `.turbo`, `out`, `coverage`, `.ruff_cache`, `.tox`,
  `site-packages`; the graph is now 175 source-only nodes.
- **Dead code removed:** `runtime/tracing._live_span()` (defined, never
  called) and KYC Sentinel's `_complete_maybe_stream` shim.

### Fixed — Review findings (2026-07-28)

From a docs+code review of the framework and the KYC Sentinel tenant.

- **HITL gate (interface change, `BaseAgentWorkflow.run_with_hitl_gate`):**
  the `needs_hitl` decision can now be supplied by the caller via a new
  keyword-only `gate_result=`, as an alternative to `gate_activity_name`
  (now `Optional[str]`; pass `None` when supplying `gate_result`). Exactly
  one is required — passing both or neither raises `ValueError`. Existing
  positional callers are unaffected.
  **Why this matters:** the only shape previously available re-executed the
  gate activity. A caller whose preceding step had *already* produced
  `needs_hitl` (the common case) therefore paid for that step twice AND let
  the gate read the decision off the **second** run — so a non-deterministic
  re-run returning `needs_hitl=False` ran the resume activity with no
  `hitl_approved` signal at all. That is a silent bypass of the mandatory-HITL
  control on a high-impact action. Tenants using `run_with_hitl_gate` with an
  activity they have already run should switch to `gate_result=`.
- **HITL gate dead-letter payload:** new optional `tenant_id=` / `gate_id=`.
  With `tenant_id`, the timeout path emits the generic `dlq_enqueue_activity`
  envelope (`payload` / `error` / `tenant_id` / `reason` / `workflow_id` /
  `gate_id`) that `run_with_recoverable_step` already used. Without it the
  legacy flattened `{**gate_input, "error": "hitl_timeout"}` shape is
  unchanged, so tenant-specific dead-letter activities (e.g.
  `examples/oil-price-agent`'s) keep working. Pairing
  `dead_letter_activity_name="dlq_enqueue_activity"` with no `tenant_id`
  previously raised `KeyError` inside the activity, losing the payload the
  timeout path exists to park.
- **Span attribute — `agent.tool.*` spans now carry `tenant.id`:**
  `ToolRegistry` takes an optional `tenant_id=` (falling back to `$TENANT_ID`)
  and passes it to `record_tool_call`. Tool spans were the only spans in the
  system emitted without tenant attribution, so filtering a shared Phoenix
  instance to one tenant hid every tool call.
- **`runtime.input_guardrail.detect_pii(text)`** — new: counts PII by type
  without rewriting the text, delegating to the same `_default_scrub` the
  pre-call guard uses. For output-side checks (a tenant moderation hook, an
  audit assertion) that must classify text identically to the pre-call scrub.
  Re-deriving those patterns is what `runtime/luhn.py` was extracted to
  prevent: KYC Sentinel's moderation hook had drifted to a card regex with no
  Luhn call, blocking rationales over long non-card digit runs the pre-call
  guard deliberately ignores.

### Added / Fixed — Testbed feedback (2026-07-21)

Found by building the KYC Sentinel testbed tenant
(`docs/testbed-tenant-spec.md`); full analysis in
`TestbedFeedback-2026-07-21.md`.

- **Gateway (behaviour change):** `complete_stream()` now streams
  **Anthropic** (Messages SSE) in addition to OpenAI-compatible providers,
  and **falls back to `complete()` instead of raising `NotImplementedError`**
  for providers with no shared SSE surface (`vertex_ai`, `azure_openai`,
  `bedrock`, `huawei_modelarts`), returning `ttft_ms=None`. Previously the
  TTFT budget could not be applied to any frontier provider — the obvious
  shape for a latency-critical route. Callers gating on TTFT must assert
  `ttft_ms is not None` rather than assume it is populated.
- **Gateway (behaviour change):** the budget-breach degrade ladder now walks
  the **whole** `degrade_to` chain to the first free tier instead of
  descending a single rung, so SPECS §29's "Local — switch to Ollama" rung
  is reachable when a paid tier sits between the caller's role and the local
  one. Previously such a call degraded to the next *paid* tier and then
  hard-failed its reservation.
- **`CompletionResult`:** new `guardrail_counts` and `prompt_guard_reasons`
  fields expose the guardrail evidence the gateway already computes
  (backward-compatible; both default to empty). Decision-path apps no longer
  need to re-run the PII scrub to record what was redacted.
- **New `runtime/testing.py`:** shipped `FakeGateway` / `RecordingGateway`
  test doubles for tenant suites, deliberately no more capable than the real
  gateway (a double that over-promises hid the streaming bug above).
- **Internal:** `LLMGateway._resolve_endpoint()` extracted — `_invoke()` and
  `complete_stream()` shared near-duplicate endpoint resolution and the
  streaming copy silently omitted the `anthropic` branch.
- **Prompt guard — new `warn` mode (G9):** `PROMPT_GUARD` accepts
  `off | warn | default | strict` (`block` is an alias for `default`).
  **No change to what ships:** `default` still blocks, and unrecognised
  values still fall back to it, so upgrading cannot silently stop blocking
  an existing deployment. What's new is the observe-first tier — `warn`
  lets a flagged prompt through and surfaces the findings on
  `CompletionResult.prompt_guard_reasons`, so a tenant can tune its
  denylist against real traffic before enforcing. Previously `default` and
  `strict` both hard-blocked despite the module documenting `default` as
  non-raising, and the only way to observe the guard was to disable it.
  New `prompt_guard.is_enforcing()` is the single definition of "blocking".
- **`SEC-PROMPT-001` now checks enforcement, not just detection:** the
  runner previously called `scan_prompt()` only, so the control could
  report *Met* while nothing was blocked at the gateway. It now reports
  `fail` when `PROMPT_GUARD=off`, `warn` on the non-enforcing `warn` tier
  (so it fails `--strict` CI), and `pass` only when the configured mode
  actually blocks. The mode is recorded in the evidence pack.
- **Tenant security pack is now seeded (G5):** `install-ai-stack.sh` vendors
  `fixtures/security/templates/*.yaml` into
  `~/.agent-framework/shared/security/`, and `hooks/post-checkout` seeds any
  missing artifact into an opted-in repo's `.agent-rfc/security/` (printing
  which files are placeholders). Existing files are **never overwritten** — a
  filled-in risk register is the tenant's own document. Previously the SEC-*
  harness looked for these four artifacts in every tenant repo while nothing
  ever put them there.
- **`runtime/` is now a pip-installable package (G6):** new `pyproject.toml`
  publishes it as `agentsmith-runtime` (imports as `runtime`), with optional
  extras `[postgres] [redis] [temporal] [hitl] [cloud] [all]` mirroring the
  runtime's lazy backend imports. Consequences:
  - The `try: from runtime.X import Y / except ImportError: from X import Y`
    dance is **gone** — 16 blocks removed across 6 runtime modules. Modules
    now import each other as `runtime.X`, unconditionally.
  - Tenants no longer need a `sys.path` bootstrap, and a tenant Dockerfile
    builds from the tenant repo alone instead of `COPY`-ing the framework
    from a parent directory.
  - `scripts/` that touch the runtime now put the repo **root** on
    `sys.path` (not `runtime/`) and import `runtime.X`; a flat `runtime/`
    path can no longer satisfy the runtime's internal package imports.
  - Import name stays `runtime` so every existing call site keeps working.
    Renaming it to `agentsmith_runtime` is a follow-up for a major version —
    it would break every tenant's imports at once.
- **New `runtime/judging.py` (G7):** the citation-grounding and pair-parity
  checks are now shared primitives. `scripts/run-evals.py._pair_parity`
  delegates to `judging.pair_parity`, so the CI fairness gate and any
  tenant's per-request parity check run one implementation instead of two
  copies that can drift. `citations_grounded` is the hard hallucination
  check (every citation must resolve to a retrieved id) a decision-path app
  wants alongside the judge-model-scored suite.
- **New `runtime/tracing.py` (G8):** `agent_span()` puts a tenant's non-LLM
  pipeline steps onto Phoenix, and `ToolRegistry.invoke` now emits a child
  span per tool call (`agent.tool.<name>` with allow/deny outcome, duration,
  error). Previously tool calls emitted nothing despite the "every tool call
  streamed to Phoenix" claim. All of it no-ops cleanly without OpenTelemetry.
- **Docs:** SPECS §3/§5.5/§16, OPERATIONS TTFT + prompt-guard + install
  sections (incl. a rollout procedure and mode table),
  `docs/security-framework-map.md` SEC-PROMPT-001 row.

- **Declared moderation hook (G10):** a tenant can now commit
  `moderation.hook: "module.path:callable"` in
  `.agenticframework/tenant.yaml` (or set `MODERATION_HOOK_PATH`). The
  runtime auto-registers it on first use, and the SEC-MOD-001 runner
  imports and smoke-tests **that same classifier** under
  `MODERATION_HOOK=required` — it must return a `ModerationResult` and must
  not block benign text. Previously `required` failed unconditionally
  (the runner cannot see a `register_output_moderator()` call made in the
  worker process), so the setting regulated tenants are told to use was the
  one that made their strict CI un-passable. An imperative registration
  still wins over the declaration; a broken declaration now raises
  `ModerationHookImportError` rather than silently skipping moderation.

### Added — Security Compliance Harness (P12, 2026-07-15)

- **Harness:** `scripts/run-security-checks.py` + `fixtures/security/control_registry.json`
  (`SEC-*` controls) with smoke / ci / full modes, `--strict`, and
  `--evidence-pack` (OWASP / NIST / ATLAS / ISO markdown rollups).
- **CI:** `workflow-templates/eval-security.yml`; framework Self-Test and
  Python FastAPI tenant template run with `strict: true`.
  `verify_system.py --check-security` smoke path.
- **Runtime:** `prompt_guard.py`, `structured_output.py`, `tool_registry.py`,
  `moderation.py` wired through `llm_gateway`; adversarial eval suite
  (`run-evals.py --suite adversarial`).
- **Portal:** `SSO_REVOCATION_MODE=fail-open|fail-closed` (503 when
  session-status unreachable in fail-closed).
- **Docs:** [`docs/security-framework-map.md`](./docs/security-framework-map.md),
  ISO map + UAE regulatory cross-links, tenant `.agent-rfc/security/` templates.

## [1.0.0] — 2026-07-11

Initial public release. Licensed under AGPL-3.0 (see `LICENSE`;
trademark policy in `TRADEMARK.md`).

- **Dev lifecycle (Layer 1):** global git hooks (opt-in per repo), IDE
  config generation from `templates/agent-rules.yaml` (Cursor / Claude Code /
  Antigravity), AST Knowledge Graph, dev-mode cost routing, golden-dataset
  eval gate, HITL promotion loop, dual-tier financial circuit breaker.
- **Production runtime (Layer 2):** `runtime/` — LLM gateway with atomic
  per-tenant budget reservation and degrade ladder, environment-aware trace
  redaction with encrypted HITL blobs, Postgres/Redis idempotency store and
  DLQ, Temporal base workflow with HITL approve/reject, edit-and-resume
  (recoverable step), and opt-in LLM self-correction; cloud provider
  adapters (Vertex AI live-verified; Azure OpenAI / Bedrock / Huawei
  ModelArts mock-tested).
- **Observability:** OTel → Arize Phoenix span contract, Ops Portal
  (RBAC, HMAC-signed append-only audit log, DLQ triage with replay webhook,
  SSO/OIDC with server-side revocation), In-App Widget.
- **Multi-tenancy:** `ai-tenant-init` / `ai-tenant-promote`, per-tenant
  GitHub Environments, shared/dedicated worker isolation
  (`runtime/k8s/dedicated-tenant/`).
- **CI/CD:** per-stack tenant workflows (TS/React, Python/FastAPI, Go) +
  reusable eval workflows (scorecard, fairness, hallucination, TTFT-live) +
  composite deploy actions (`gcp-auth`, `build-push-ghcr`,
  `deploy-placeholder`, `rollback-notify`), GCP Cloud Run via WIF verified
  end-to-end.
- **Reliability & compliance pack v1:** hallucination-rate hard gate,
  fairness suite with pair parity, TTFT streaming budget
  (`complete_stream` + `verify_ttft.py`), pre-call PII input guardrail
  (PDPL / Emirates ID), conversation memory + vector-store RAG substrate,
  UAE sovereign Falcon 3 template, Delivery Model soft gate, ISO/IEC 42001
  thematic control map.
- **Enterprise pack:** GPG-signed hook bundles + MDM deploy, HMAC-validated
  break-glass bypass tokens, RFC-enforcement hooks.
