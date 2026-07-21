# What Building a Tenant Taught Us — AgentSmith feedback from KYC Sentinel

**Source:** first full build of the `KYC_Sentinel` testbed tenant
(`Apps/KYC_Sentinel`, spec: `docs/testbed-tenant-spec.md`), 2026-07-21.
**Method:** every claim below was reproduced against the real framework
code, not inferred from docs. Reproduction commands are inline.

The testbed paid for itself: it surfaced one **High** framework gap that
no unit test could have caught, because it only appears when two
separately-tested features are combined the way a real tenant would
combine them.

---

## A. Framework gaps

> **Status 2026-07-21 (same day):** G1–G6, G9 and G10 are **fixed** — see
> the per-item notes and CHANGELOG [Unreleased]. Framework suite 170 →
> **252 passing**; the testbed tenant 25 → **35**, and the tenant now runs
> entirely against the installed package. Only **G7 and G8** remain open.
> Three findings were discovered by fixing others: G9 while wiring G3, G10
> while hardening the tenant's security CI after G5, and G6's `scripts/`
> breakage while removing the import fallbacks — each fix exposed the next
> layer down, which is the argument for keeping the testbed permanently.

### G1 — `complete_stream()` cannot stream the frontier providers (**High**) ✅ FIXED

`complete_stream()` raises `NotImplementedError` for `anthropic` and for
every cloud-native provider (Vertex / Bedrock / Azure / Huawei). Only
`openai`, `ollama`, and `groq` work.

```
$ python3 - <<'EOF'   # gateway with analyst=claude-sonnet-4-6 (provider anthropic)
asyncio.run(gw.complete_stream("hi", model_hint="analyst"))
EOF
NotImplementedError: complete_stream currently supports OpenAI-compatible providers only; got 'anthropic'.
```

Why this matters: the TTFT budget is the framework's latency guarantee,
and the docs present it unconditionally —

- SPECS §3: "TTFT via opt-in `LLMGateway.complete_stream()`"
- SPECS §5.5 / §16: "`complete()` + `complete_stream()` (ttft_ms)"
- OPERATIONS "TTFT on the streaming path", CHANGELOG 1.0.0

None of them mention a provider restriction. The natural tenant design —
frontier model on the user-visible latency-critical path — is exactly the
configuration that cannot use TTFT. `verify_ttft.py` smoke-tests Ollama, so
CI never noticed.

**Fix options:** (a) implement Anthropic SSE in `complete_stream` (its
streaming API is well-defined and `provider_dispatch` already owns the
request/response envelope); (b) at minimum, make `complete_stream`
fall back to `complete()` with `ttft_ms=None` and a logged warning
instead of raising, so a provider swap in `models.yaml` can't take a
tenant's pipeline down; (c) document the restriction everywhere TTFT is
claimed. Recommend (a) + (c); (b) as the interim.

**Fixed:** all three. `provider_dispatch.parse_stream_delta()` +
`supports_streaming()` own the per-provider SSE envelope (Anthropic's
`content_block_delta` text events; non-text frames return `None` so TTFT is
timed from the first real *token*, not the first protocol frame).
Cloud-native providers fall back to `complete()` *before* any budget
reservation or run-status row, so `complete()` owns the whole call — no
double reservation. `_resolve_endpoint()` was extracted because the
streaming path's near-duplicate copy silently omitted the `anthropic`
branch, which is part of why this never worked. Tests:
`runtime/test/test_stream_providers.py` (9). Docs: SPECS §3/§5.5,
OPERATIONS TTFT section, CHANGELOG.

### G2 — The degrade ladder only descends one rung (**Medium**) ✅ FIXED

`_degrade_chain()` correctly builds the full chain, but `_resolve_role()`
returns `chain[1]` — one hop — and `complete()` then hard-fails if the
reservation still doesn't fit:

```
full chain from analyst: ['analyst', 'research', 'intake']
resolve(analyst) when breached -> ('research', 'downgrade')
resolve(research) when breached -> ('intake', 'local')
```

A caller always asking for `analyst` therefore never reaches the free
`intake` rung: it degrades to the *paid* `research` tier, and when that
reservation fails it raises `BudgetExceededError`. SPECS §29's documented
ladder ends in "4. Local — switch to Ollama … 5. Alert", but rung 4 is
unreachable whenever a paid tier sits between the caller's role and the
local one — which is the normal shape of a cost ladder.

**Fix:** walk the chain until a role's reservation succeeds (or the chain
is exhausted), rather than taking a single step; prefer the first free
tier when the budget is breached. Add a test asserting `analyst` resolves
to `intake` when both `analyst` and `research` are unaffordable.

**Fixed:** `_resolve_role` now walks the whole chain to the first free
tier (the budget is already breached, so a paid rung only buys one more
call before failing, while a free rung keeps the tenant serving), falling
back to the next configured paid rung only when the chain has no free
tier. Tests: `runtime/test/test_degrade_ladder.py` (8), including the
testbed's real `analyst → research → intake` shape, broken chain links,
and a cyclic `degrade_to`.

### G3 — Guardrail evidence is unreachable by the caller (**Medium**) ✅ FIXED

`complete()` runs the PII scrub internally and records the counts to logs
and span attributes — but `CompletionResult` exposes only
`text, model_used, input_tokens, output_tokens, cost_usd, degrade_tier,
ttft_ms`. An app that must record *what was redacted* in its own decision
record (any PDPL/GDPR decision-path app — the exact use case the framework
markets) cannot get the counts back.

KYC Sentinel worked around this by re-running `scrub_text()` in the intake
agent before calling the gateway, which means the scrub runs twice per
application. It's idempotent, so it's safe — but it's a workaround every
compliance-minded tenant will independently reinvent.

**Fix:** add `guardrail_counts: dict[str, int]` and `prompt_guard_reasons:
list[str]` to `CompletionResult`. Cheap, backward-compatible, removes the
double scrub.

**Fixed:** both fields added (defaulting empty, so every existing caller is
unaffected) and populated on both the streaming and non-streaming paths.
Tests: `runtime/test/test_guardrail_evidence.py` (4), which also asserts
the redacted text is what actually reached the provider. Fixing this
surfaced **G9** below.

### G4 — No test double for the gateway (**Medium**) ✅ FIXED

Nothing in `runtime/` provides a fake/recording `LLMGateway`, so the
tenant wrote ~60 lines of `FakeGateway` (`agents/gateway.py`) before it
could test anything. Every tenant will write that same class, differently,
and each one will drift from `CompletionResult`'s real shape.

**Fix:** ship `runtime/testing.py` with `FakeGateway` (scripted responses,
recorded calls, `degrade_tier`/`ttft_ms` simulation) and a
`RecordingGateway` wrapper for live-call assertions. This is the single
highest-leverage addition for tenant developer experience — it is what
made the whole testbed runnable offline.

**Fixed:** `runtime/testing.py` ships both, with scripted per-call response
queues, callables, budget-cap simulation raising the real
`BudgetExceededError`, and assertion helpers (`routes_used()`,
`calls_for()`, `assert_prompt_excludes()` — the last one turns "PII never
reached the model" into one line). Tests:
`runtime/test/test_testing_doubles.py` (9).

**The rule the double encodes:** it is deliberately *no more capable than
the real gateway* — `complete_stream` refuses to stream what the real
gateway can't. This is the lesson from G1: the testbed's hand-rolled
double aliased `complete_stream` to `complete`, so a guaranteed production
crash looked green offline for the entire build. A test double that
over-promises hides exactly the bugs a testbed exists to find.

KYC Sentinel now subclasses it (only ~45 lines of domain scripting remain),
which immediately exposed a second, smaller lesson: the extension point
must be named unambiguously. The tenant's `_respond()` helper collided with
the framework's internal method of the same name; the internal one is now
`_build_result()` and `_resolve_text(call)` is documented as the single
override hook.

### G5 — Tenant security pack is never seeded (**Medium**) ✅ FIXED

`fixtures/security/templates/` contains `agency_manifest.yaml`,
`nist_profile.yaml`, `risk_register.yaml`, `tool_allowlist.yaml`, and the
`SEC-*` harness has runners that look for them in a tenant's
`.agent-rfc/security/`. But nothing copies them there:

```
$ grep -rn "security/templates|agency_manifest|risk_register.yaml" install-ai-stack.sh hooks/post-checkout
(no matches)
```

So a new tenant starts with those controls skipping/failing and must
discover the templates by reading the framework tree. KYC Sentinel
hand-wrote `tool_allowlist.yaml` and never created the other three —
which is why its CI security step is currently `|| true`.

**Fix:** `ai-tenant-init` (and/or `post-checkout` on an opted-in repo)
copies `fixtures/security/templates/*` into `.agent-rfc/security/` when
absent — the same vendoring mechanism already used for
`agent-rules.yaml` and the golden-eval seeds.

**Fixed** via exactly that two-stage vendoring path:

1. `install-ai-stack.sh` copies `fixtures/security/templates/*.yaml` into
   `~/.agent-framework/shared/security/` (refreshed every install — these
   are pristine templates, never a tenant's edited copy).
2. `hooks/post-checkout` seeds any of the four that are **missing** from an
   opted-in repo's `.agent-rfc/security/`, and prints which ones are
   placeholders plus the command to verify them.

The never-overwrite guard is the important half: a filled-in risk register
is the tenant's own document — its content is precisely what the framework
cannot know — so a later branch switch must not clobber it. Tests:
`scripts/test/test_security_pack_seeding.py` (7), covering seed-all,
seed-only-missing, never-overwrite, the opt-in gate still applying, and a
machine whose install predates the step.

### G6 — `runtime/` is not an installable package (**Medium**) ✅ FIXED

There is no `pyproject.toml`/`setup.py` anywhere in the repo, so a tenant
cannot `pip install` the runtime. Consequences observed:

- The tenant needs a path-bootstrap module (`agents/_framework.py`) before
  any framework import.
- The `try: from runtime.X import … except ImportError: from X import …`
  dance appears in **7 of the framework's own runtime modules** and had to
  be replicated in 6 tenant files.
- `Dockerfile` must `COPY AgenticFramework/runtime` from a parent
  directory, so the tenant image can't be built from the tenant repo alone.

**Fix:** add a minimal `pyproject.toml` exposing `runtime` as
`agentsmith_runtime`, publish to an internal index (or install from git
ref). This also kills the dual-import boilerplate.

**Fixed.** `pyproject.toml` publishes `agentsmith-runtime` with backend
extras (`[postgres] [redis] [temporal] [hitl] [cloud] [all]`) mirroring the
runtime's lazy imports, so a tenant takes only what it uses.

*Deviation from the original note:* the import name stays **`runtime`**, not
`agentsmith_runtime`. Renaming would break every `from runtime.X import Y`
in every tenant repo simultaneously — a major-version change, not something
to land under a live tenant. The generic name is a real collision risk in a
crowded virtualenv and is recorded in `pyproject.toml` as the follow-up.

Removed: **16 dual-import blocks** across 6 runtime modules, plus 8 more in
the tenant. Verified the actual goal — from an unrelated working directory,
with no `sys.path` manipulation and no `AGENTSMITH_DIR`:

```
$ python -c "from runtime.testing import FakeGateway; ..."
gateway call: hello
cross-module import (trace_redactor -> environment) OK: [REDACTED]
```

and the tenant's full suite (35) plus all eight F-scenarios pass against the
installed package alone.

**What this nearly broke, and the lesson:** removing the fallbacks made
`scripts/verify_system.py --check-redaction` fail, which surfaced as
`SEC-PII-002` failing in the *tenant's* strict CI — several `scripts/`
imported runtime modules flat after inserting `runtime/` onto `sys.path`.
That works only while runtime modules don't import each other; the moment
they do, the package root is required. Those scripts now add the repo
**root** and import `runtime.X`. Worth noting the failure showed up two
layers away from the change, in a different repo's compliance gate — the
kind of coupling a packaging change is supposed to eliminate, caught only
because the tenant's security harness was already wired to hard-fail (G5).

### G7 — No runtime primitives for the two hard judge checks (**Low**)

Citation-grounding and pair-parity exist in `run-evals.py` as *offline
eval* suites, but a live app that wants to enforce them per-request writes
them itself (KYC Sentinel's `judge.check_citations` / `check_parity`,
~30 lines). These are the most reusable judge primitives in the framework.

**Fix:** promote both into `runtime/` (e.g. `runtime/judging.py`) and have
`run-evals.py` import them, so the CI gate and the production check are
provably the same logic — the same argument that justified `_shared.py`'s
`DEFAULT_JUDGE_MODEL`.

### G8 — Tenant pipeline steps have no span helper (**Low**)

The gateway emits richly-attributed spans for LLM calls, but a tenant's
non-LLM steps (tool invocations, scrub counts, judge verdicts, HITL
decisions) have no framework-provided way onto a span — the tenant must
hand-roll OpenTelemetry. The observability story is "every token and tool
call streamed to Phoenix", but tool calls through `ToolRegistry.invoke()`
currently emit nothing.

**Fix:** instrument `ToolRegistry.invoke()` with a span (name, args hash,
allow/deny outcome, duration), and expose a small
`runtime/tracing.py:agent_span(name, **attrs)` context manager for tenant
steps.

### G9 — `PROMPT_GUARD=default` behaves exactly like `strict` ✅ RESOLVED (option C)

Found while wiring G3. `prompt_guard.apply_prompt_guard()` documents three
modes and explicitly promises that **default does not raise**:

```python
# - default: scan; return result (caller may log); does not raise
# - strict:  scan; raise PromptGuardBlockedError when blocked
mode = resolve_mode()
return scan_messages(messages, raise_on_block=(mode == "strict"))
```

It keeps that promise — but the gateway then raises anyway, in both
`complete()` and `complete_stream()`:

```python
pg_result = apply_prompt_guard(messages)
if pg_result.blocked:
    raise PromptGuardBlockedError(...)   # regardless of mode
```

So the two modes are indistinguishable at the only call site that matters,
and `default` — which is the shipped default (`PROMPT_GUARD` unset →
`"default"`) — hard-blocks on heuristic matches. Consequences: the
documented mode contract is false; there is no "observe first" posture for
a tenant rolling out the guard; and a false positive is a hard outage
rather than a logged warning.

**This is not a drive-by fix** — it changes a security control's default
posture, so it needs an explicit decision:

- **(a) Make `default` warn-only** (raise only in `strict`). Matches the
  module's documented contract and gives tenants a safe rollout path; the
  already-wired `CompletionResult.prompt_guard_reasons` starts carrying the
  evidence with no further code change. Weakens the out-of-the-box posture.
- **(b) Keep blocking, fix the docs** (rename the modes, e.g.
  `off | block | strict`), and note that `prompt_guard_reasons` is
  structurally always empty.

A third option emerged while writing this up and is the one taken:

- **(c) Add an explicit `warn` tier and keep `default` blocking.** Modes
  become `off | warn | default(=block) | strict`. No upgrade regression, a
  real rollout path, and `prompt_guard_reasons` becomes meaningful for
  tenants who opt into `warn`.

**Resolved (option C, owner decision 2026-07-21).** Option (a) was rejected
precisely because of the upgrade risk: every deployment on the shipped
default would have silently stopped blocking injections, and — as this
finding also established — the security harness would not have caught it.
Adding the missing tier fixes the false contract without weakening what
ships.

Implemented:

- `PROMPT_GUARD=off|warn|default|strict`, `block` accepted as an explicit
  alias for `default`; unrecognised values still fall back to `default`, so
  a typo cannot disable the guard.
- New `prompt_guard.is_enforcing(mode)` — one definition of "blocking",
  used by both the gateway and the harness runner, so they cannot drift.
- The gateway raises in `default`/`strict` and logs-and-proceeds in `warn`,
  populating `CompletionResult.prompt_guard_reasons`.
- **`SEC-PROMPT-001` now proves enforcement, not just detection** (the
  second half of the same finding — the runner only called `scan_prompt()`,
  so the control reported *Met* regardless of whether anything was blocked).
  Verified end-to-end: `default → pass`, `warn → warn` (fails `--strict`),
  `off → fail`, with the mode recorded in the evidence pack.
- Tests: `runtime/test/test_prompt_guard_modes.py` (17) and
  `scripts/test/test_security_prompt_guard_enforcement.py` (6), including
  an explicit regression guard that an unset `PROMPT_GUARD` still blocks —
  i.e. that option (a) was not taken by accident.
- Docs: module docstring, OPERATIONS prompt-guard section (mode table +
  rollout procedure), SPECS §5.5, `docs/security-framework-map.md`, CHANGELOG.

### G10 — `MODERATION_HOOK=required` can never pass the harness ✅ FIXED (option a)

Found while flipping the testbed's security CI to hard-fail. The
`moderation_hook` runner calls `reset_output_moderator()` as part of its API
smoke test and then:

```python
if mode == "required":
    return ControlResult(status="fail",
                         message="no output moderator registered (MODERATION_HOOK=required)")
```

That branch is unconditional — the runner has just cleared any registration
and has no way to observe a durable one made in tenant code (a worker
registers its classifier at startup, in a different process from the
harness). So `required` always fails, while `optional` passes.

The consequence is backwards: FIXES_AND_CLEANUP and the P12 notes tell
regulated tenants to `set MODERATION_HOOK=required`, which is exactly the
setting that makes their strict CI un-passable. KYC Sentinel's CI therefore
runs `optional` with a comment explaining why.

**Root cause, stated precisely:** SEC-MOD-001 conflates two different
claims — "the framework's moderation API works" (framework-owned, always
checkable) and "this tenant has a classifier registered" (tenant-owned,
only observable if the tenant declares it somewhere the harness can read).
The runner proves the first and then fails the second by construction.

**Fix options:**

- **(a) Declared hook — recommended.** The tenant commits a dotted path,
  e.g. in `.agenticframework/tenant.yaml`:

  ```yaml
  moderation:
    hook: "agents.moderation:classify_output"
  ```

  Under `required`, the runner imports it, asserts it is callable, and runs
  the same smoke pair it already runs against its own lambda (clean text
  allowed, unsafe text blocked). Pass only if the tenant's *real* classifier
  behaves. This upgrades the control from "the API exists" to "this tenant
  has a working classifier", which is the evidence a regulated tenant
  actually needs — and it makes `required` usable, matching the guidance.

  Worth pairing with: have `runtime/moderation.py` auto-register from the
  same key at startup. Otherwise the declaration and what the worker really
  registers can drift, and the harness would be certifying the wrong thing.

- **(b) Keep the fail, fix the guidance.** Document `required` as a
  deployment-time setting that CI must not use, and correct the P12 /
  FIXES notes. Zero code change and honest, but SEC-MOD-001 then never
  proves anything tenant-specific — the weakest option for the control
  that regulated deployments lean on hardest.

- **(c) Split the control.** `SEC-MOD-001` stays the framework API smoke
  (owner: framework, always passes), and a new `SEC-MOD-002` covers tenant
  registration (owner: tenant, skips when undeclared). Architecturally the
  cleanest — it matches the registry's existing `owner` field, which today
  labels SEC-MOD-001 "Tenant" while the runner mostly tests framework code.
  Bigger change: new control id, registry entry, framework-map row, and
  evidence-pack columns.

(a) and (c) compose: (a) is the detection mechanism, (c) is the
bookkeeping. Whichever is chosen, the runner and the docs must stop
contradicting each other.

**Fixed (option a, owner decision 2026-07-21).**

- `moderation.hook: "module.path:callable"` in
  `.agenticframework/tenant.yaml`, overridable per-deployment with
  `MODERATION_HOOK_PATH`.
- **The runtime loads the same declaration** (`_ensure_declared_moderator()`
  on first use, imperative `register_output_moderator()` still wins). This
  binding is the point: a harness that checked a config key production
  ignored would be certifying the wrong thing.
- The SEC-MOD-001 runner imports the declared hook under `required` and
  smoke-tests **the tenant's own classifier** — it must return a
  `ModerationResult` and must not block benign text, so a block-everything
  stub cannot "pass" the control. A broken declaration fails loudly
  (`ModerationHookImportError`) rather than degrading to a silent skip,
  which would leave a regulated tenant unmoderated while CI looked green.
- `load_declared_moderator()` puts the tenant repo root on `sys.path` before
  importing: a declared hook is tenant code by definition, and the harness
  runs from the framework install, so without this every tenant would have
  had to set `PYTHONPATH` by hand.
- Tests: `runtime/test/test_moderation_declared.py` (12) and
  `scripts/test/test_security_moderation_declared.py` (8).

Verified on the testbed: KYC Sentinel declares
`agents.moderation:classify_output`, and `--mode ci --strict` with
`MODERATION_HOOK=required` now exits 0 with evidence reading *"tenant
moderator declared and verified (agents.moderation:classify_output)"* —
the control now proves something tenant-specific instead of only that the
framework API exists.

Option (c) — splitting into SEC-MOD-001 (framework API) and SEC-MOD-002
(tenant registration) — remains available and is still the cleaner
bookkeeping; it was not needed to make `required` satisfiable.

---

## B. Documentation corrections

| # | Where | Correction |
|---|---|---|
| D1 | `llm_gateway.complete()` docstring | Says `model_hint options: "architect" \| "developer" \| "validator" \| "fast"`. Misleading: `_resolve_role` uses `model_hint` as a direct key into the merged registry, so **tenant-defined roles work** (KYC Sentinel uses `intake`/`research`/`analyst`/`judge` via `tenant.yaml → gateway.routing_overrides`). Reword to "any role defined in the model registry; framework defaults are …". |
| D2 | SPECS §3, §5.5, §16; OPERATIONS TTFT section; CHANGELOG | State the `complete_stream` provider restriction (G1) until it's lifted. |
| D3 | SPECS §29 degrade ladder | Describe actual behavior (one hop) or fix the code (G2) — currently the doc over-promises. |
| D4 | SPECS §25 / tenant guidance | Record the architectural rule the build discovered: **keep domain logic in plain async functions; Temporal activities are thin wrappers.** The determinism sandbox rejects `Path.resolve()` and file I/O at workflow-module import time — the oil-price example knows this (buried in a code comment), but no tenant-facing doc says it. KYC Sentinel's `pipeline.py`/`activities.py` split exists solely because of it, and that split is also what makes every F-scenario runnable without an orchestrator. |

---

## C. Errors in the tenant app (KYC Sentinel's own bugs)

| # | Issue | Status |
|---|---|---|
| E1 | `agents/analyst.py` calls `complete_stream()` with an Anthropic route → guaranteed `NotImplementedError` in real mode (fake mode masked it). This is G1 landing as a live crash. | **Fixed** — provider-aware: stream when supported, else `complete()` with a logged reason. |
| E2 | The Research agent never makes an LLM call (`del gateway`), so the Groq route is only ever reached as a *degrade target*. The spec claims four exercised routes; only three are. | **Open** — give Research a real triage/summarization call so the cheap tier is genuinely exercised. |
| E3 | `tenant.yaml` sets `judge` and `analyst` to the same model id, contradicting RFC-002's judge/actor separation. | **Open** — point judge at a different model; consider a framework warning when a judge role resolves to the same id as the role it grades. |
| E4 | CI security step is `\|\| true` because the tenant `.agent-rfc/security/` pack is incomplete (see G5). | **Open** — author the three missing artifacts, then hard-fail. |

---

## D. What worked (worth preserving)

- **`parse_llm_json` + Pydantic composes exactly right with the recovery
  tiers.** The errors it raises are precisely what `run_with_recoverable_step`
  (F1) and `run_with_self_correction` (F2) consume. No adapter needed.
- **`ToolRegistry` strict + YAML allowlist:** deny-by-default worked first
  try; F4 needed no framework changes.
- **`MemoryVectorStore` + hash embedder:** deterministic RAG in CI with no
  model download — the reason the testbed runs offline.
- **`input_guardrail` counts** were directly usable as compliance evidence
  (the only friction is G3's plumbing).
- **`BaseAgentWorkflow`** delivered HITL/recoverable/self-correction
  without the tenant writing a single signal handler.

---

## Recommended order

1. ~~**G1** (High) — fallback now, Anthropic streaming next; fix D2 with it.~~ ✅ done
2. ~~**G4** (`runtime/testing.py`) — unblocks every future tenant, small.~~ ✅ done
3. ~~**G3** + **G2**~~ ✅ done (D2/D3 docs updated with them)
4. ~~**G9** — decide the prompt-guard mode semantics~~ ✅ done (option C + harness enforcement check)
5. ~~**G5** — one vendoring step; unblocks tenant strict CI.~~ ✅ done
6. ~~**G6** — packaging~~ ✅ done (24 dual-import blocks removed across both repos)
7. ~~**G10**~~ ✅ done (option a: declared hook, runtime-bound)
8. **G7/G8**, then D1/D4 in the next docs pass.

Tenant-side: E1 fixed; E2–E4 tracked in `KYC_Sentinel/DEVLOG.md`.

## Verification (2026-07-21)

| Suite | Before | After |
|---|---|---|
| Framework `scripts/test/` + `runtime/test/` | 170 passed | **252 passed**, 14 skipped |
| KYC Sentinel `test/` | 25 passed | **35 passed** (on the shipped double; + classifier tests) |
| `demo.py all` | 8 controls fire | 8 controls fire |

Also clean: `py_compile` sweep, `check_bare_except.py` on every changed
runtime module, and the SPECS §16 tree drift check.

**Behaviour changes to flag at release** (CHANGELOG [Unreleased] carries
these): `complete_stream` no longer raises for non-streaming providers —
callers gating on TTFT must assert `ttft_ms is not None`; and a
budget-breached call now lands on the first *free* rung of the degrade
chain rather than the next paid one, which changes which model serves a
degraded request.

**Caveat:** `ai-tenant-init` itself was never executed (no machine install
in this environment) — the tenant was bootstrapped by hand, so the
provisioning path remains unverified end-to-end. G5 was found by reading
it, not by running it.
