---
status: active
scope:
  - contract/security/v1/**
  - scripts/run-security-checks.py
  - scripts/security/**
  - scripts/security_port.py
  - scripts/gate_models.py
  - scripts/_shared.py
  - runtime/cli.py
  - runtime/conformance.py
  - runtime/telemetry_contract.py
  - runtime/adopt.py
  - .githooks/process-gate
  - .github/actions/setup-agentsmith/action.yml
  - fixtures/security/**
  - scripts/test/**
  - runtime/test/**
  - scripts/mutation_check.py
  - .agenticframework/process-gates.json
---
# C7 — The security contract: a tenant's own posture, checked by the provider it declares

Slice C7 of `.agent-rfc/designs/governance-contracts.md`. Security is a command port, like the gate,
the rules and the evals: the tenant owns its security pack and its declared posture; a provider
checks them and answers with a result. Today the only checker is a framework script every tenant
runs by path, and much of what it reports is about AgentSmith rather than about the tenant.

## Problem

Measured on 2026-10-09:

- **Every tenant runs the harness by path.** OTS's `eval-security.yml` runs its vendored
  `scripts/run-security-checks.py --mode ci --strict`, then `--mode smoke --evidence-pack`; its
  `cd-staging.yml` and `cd-production.yml` run its vendored `scripts/verify_system.py
  --check-redaction`; it holds a vendored `fixtures/security/` identical to AgentSmith's. KYC's CI
  runs `$AGENTSMITH_DIR/scripts/run-security-checks.py --mode ci --strict` from a checkout of
  AgentSmith at `v2.2.3`.
- **A tenant's verdict depends on how AgentSmith is installed.** KYC's strict run, unchanged
  repository: from CI's full checkout SEC-AUDIT-001, SEC-RBAC-001, SEC-SSO-001 (the portal's
  TypeScript tests) and SEC-CHANGE-001 (AgentSmith's `hooks/`) run and pass; from the installed
  package (`~/.agent-framework`, no `portal/` or `hooks/`) the same four **fail** — "missing portal
  files"; in a vendored tenant (OTS) they are `not applicable`. Three answers, none about KYC.
- **Most "passes" are AgentSmith's own tests.** SEC-HITL-001, SEC-DLQ-001, SEC-SELF-001 and
  SEC-BUDGET-001 run `runtime/test/*.py` from the install; SEC-OUTPUT-001 smoke-tests
  `runtime/structured_output`; SEC-PII-001 and SEC-PROMPT-001 run AgentSmith's guard over AgentSmith's
  probe fixtures; SEC-SOV-001 checks AgentSmith's `templates/uae-sovereign/models.yaml`. Each is
  evidence about the provider's release, counted as the tenant's pass — whether or not the tenant
  uses that code (OTS's committed code imports nothing from `runtime/`).
- **One "tenant" control reads the provider instead.** SEC-GW-001 scans `agents/` and `workflows/`
  under the *install* root: in KYC it scans AgentSmith's checkout, never KYC's `agents/`.
- **The posture graded is the CI step's environment, not the repository's declaration.** KYC's step
  sets `PROMPT_GUARD=default`, `MODERATION_HOOK=required`, `TOOL_ALLOWLIST_STRICT=1`; OTS's sets
  `MODERATION_HOOK` from a repository variable; strictness is a flag or `SECURITY_STRICT`. The
  tenant's `tenant.yaml` declares a posture too (KYC's `security.prompt_guard: "default"`), and
  nothing checks that the two agree.
- **No published shape.** The result is stdout text and an exit code; the evidence pack
  (`security_report.json`) has no schema; a tenant's additive control registry (KYC's
  `SEC-KYC-FLOOR-001`) and its pack files have none, except a hand-written risk register schema read
  with `jsonschema`, which the provider's CI setup step does not install.
- **The redaction check grades AgentSmith's redactor, not the tenant's wire.** `--check-redaction`
  scrubs three fixed strings with `runtime.trace_redactor` under `$ENVIRONMENT`'s profile, and
  skips under `development`. The telemetry contract (`contract/telemetry/v1/protocol.md`) defers to
  this slice: "the security contract verifies the redaction".
- **OTS's strict run is red on `main`, honestly**: SEC-RISK-001 (its risk register still holds the
  template's `RISK-EXAMPLE-001`) and SEC-AGENCY-001 (its agency manifest is the shipped placeholder).
  That is the tenant's own content; this slice does not change it.

**The owner's decisions (2026-10-09):** controls that test the provider's own code are not the
tenant's — they do not run in a tenant's check, and are reported as the provider's; and redaction
is verified on the tenant's wire, by running the tenant's declared emitter.

## Approach

### `contract/security/v1/` — a command port, two verbs

```
<security-command> check
<security-command> redaction
```

Same protocol as the gate, rules and evals: cwd is the repository (or the request's `cwd`); stdin
one request; stdout one result and nothing else; the provider's report for a person on stderr;
**exit 0 whenever the provider answers**, exit 3 for "cannot run here". Anything other than a
result on stdout is no answer.

**`check`** — request (`request.schema.json`): optional `controls` (ids to check; default all) and
`evidence_dir` (where the provider writes its human-readable pack). Result (`result.schema.json`):

| Field | Means |
|---|---|
| `schema` | `1` |
| `verdict` | `pass` \| `fail` \| `not_gradable` |
| `reason` | why, in a sentence — required for anything but `pass` |
| `provider` | `{name, version}` — whose answer this is |
| `controls` | one row per control: `id`, `title`, `subject` (`repository` \| `provider`), `result` (`pass` \| `fail` \| `gap` \| `not_applicable`), `message`, `frameworks` (OWASP, NIST, ATLAS, ISO 42001 tags), `evidence` (string to string) |
| `counts` | rows per result |

- **`subject`** says whose evidence a row is. A `repository` control is checked against the
  repository's own pack, code and declarations. A `provider` control is about the provider's own
  code — in a tenant it is **not run** and reads `not_applicable`, naming the provider's version and
  that its own CI is the evidence. In the provider's own repository the two are the same thing, and
  every control runs.
- **The verdict is over what ran**: `fail` if any row fails; `not_gradable` when the repository's
  security declarations cannot be read (a tenant registry that does not match its schema);
  otherwise `pass`. A `gap` row is a gap the registry declares — visible in every result, not a
  failure.
- **There is no non-strict mode.** Today's `warn` (an undeclared gap, a guard in its observe-only
  tier) is a `fail` in the contract, as the umbrella's "closed in CI" says. A tenant cannot soften a
  provider's control: its registry is additive, as today.
- **The posture graded is the declared one.** The provider reads `tenant.yaml` (`security.*`,
  `moderation.*`) and never the environment of whoever runs the check — as the evals contract does
  for its bars.

**The repository controls every provider checks** (`controls.json`, the contract's catalogue):

| Id | Passes when |
|---|---|
| SEC-RISK-001 | `.agent-rfc/security/risk_register.yaml` matches `risk_register.schema.json` and holds no template entry |
| SEC-AGENCY-001 | `.agent-rfc/security/agency_manifest.yaml` matches its schema, holds no placeholder, and gates at least one action on a human |
| SEC-TOOL-001 | `.agent-rfc/security/tool_allowlist.yaml` exists and every tool the repository registers resolves the way it says, with the deny path exercised |
| SEC-PROMPT-001 | the declared `security.prompt_guard` enforces (`default` or `strict`; undeclared is the default) |
| SEC-PII-001 | the declared `security.input_guardrail` scrubs (not `off`) |
| SEC-MOD-001 | `moderation.mode` is declared; `required` names a hook that imports and answers benign text as allowed |
| SEC-PII-002 | `redaction` passes for `staging` and `production` with the declared emitter; `not_applicable` when the repository declares it emits no telemetry |
| SEC-CHANGE-001 | `providers.json` declares a gate provider (not `none`) |
| SEC-EVAL-001/002/003 | the golden, fairness, hallucination dataset is gradable under `contract/evals/v1` (≥3 cases, each with its output); `not_applicable` with no dataset |
| SEC-ADV-001, SEC-RAG-001 | the adversarial, rag_poison suite passes under `contract/evals/v1`; `not_applicable` with no dataset |

A tenant's own controls (`.agent-rfc/security/control_registry.json`, `registry.schema.json`) are
repository controls run by their declared `suite`, in the repository's own interpreter (`python3`
on PATH) — the provider never imports a tenant's code into its own process. A provider adds
controls of its own under either subject; AgentSmith keeps SEC-GW-001 as a repository control of its
own, now reading the repository.

**`redaction`** — request (`redaction-request.schema.json`): `environment` (`staging` \|
`production`), optional `emitter` (else the declaration's). The provider runs the emitter with its
OTLP destination pointed at a loopback receiver (its own destinations removed, as the telemetry
conformance does), `ENVIRONMENT` set to the request's, and **`SECURITY_REDACTION_PROBES`** — a JSON
array of probe strings the contract fixes (a bearer token, an API key, an email address, a card
number). **An emitter promises** to export one span carrying `security.redaction.probe: true` with
the probes in its payload attribute `input.value`, through whatever redaction it applies in that
environment. Result (`redaction-result.schema.json`): `verdict` — `pass` (the probe span arrived and
no probe appears verbatim in any attribute of anything exported), `fail` (one did — named by its
kind, never its value), `not_gradable` (nothing arrived, or no probe span), `not_applicable` (the
repository declares `"emitter": "none"`).

**The declaration** (`providers.schema.json`):

```json
{"providers": {"security": {"command": "agentsmith security", "version": "^2", "contract": 1,
                            "emitter": "python3 scripts/telemetry_smoke.py"}}}
```

`"emitter": "none"` declares the repository emits no telemetry; with no `emitter` at all,
SEC-PII-002 fails ("nothing verifies what this repository's telemetry carries"). `"security":
"none"` — the repository declares no security provider, and a step says so instead of checking.

### Amended while building (2026-10-09)

- **A judged dataset the repository declared `not_gradable: warn` for is a `gap`, not a failure.**
  OTS's golden dataset has no outputs, and its `providers.json` already says, in a reviewed file,
  that the golden suite's `not_gradable` only warns. SEC-EVAL-001 reports that as a declared gap —
  visible in every result — rather than failing a second time for a decision already recorded.
- **A tenant registry row claiming `met` or `partial` must name its `suite`**
  (`registry.schema.json`); a `gap` or `org-owned` row need not. A tenant row is run by its suite
  whatever `runner` it names — the old loader would have run `noop` for one that said so.
- **The OTLP destination list moved to `runtime/telemetry_contract.py`** (`OTLP_DESTINATIONS`), so
  the telemetry conformance and the redaction check strip the same variables.
- **The risk register's widened id pattern.** A control id may have parts (`SEC-KYC-FLOOR-001`);
  the old schema's `^SEC-[A-Z]+-[0-9]{3}$` refused a tenant's own control in a risk entry.

### Who asks

**CI**, through the launcher: `bash .githooks/process-gate security check [--evidence-dir D]` and
`security redaction --environment staging|production`. **Failure is closed**: only `pass` passes;
`not_applicable` passes for `redaction` with a notice; there is no declared warning, unlike evals —
nothing a check reads is a quota.

### AgentSmith as the provider

- **`agentsmith security check|redaction`** through `_provider_scripts()` — `scripts/security_port.py`
  over the existing runners, so the checks are not duplicated. Each registry row in
  `fixtures/security/control_registry.json` gains `subject`; `run-security-checks.py` keeps its
  flags, modes and output for this repository and vendored tenants until C9.
- **Runners split where a control has both halves.** SEC-PROMPT-001 and SEC-PII-001: detection over
  the provider's probes is the provider's own (run in its own repository), the declared posture is
  the repository's. SEC-MOD-001: the API smoke is the provider's; the declared mode and hook are the
  repository's, the hook smoke-tested in the repository's interpreter. SEC-GW-001 reads the
  repository root.
- **The pack models live in `scripts/gate_models.py`** (risk register, agency manifest, tool
  allowlist, tenant registry row, request, results, declaration) with generated schemas; the risk
  register runner validates with the model, and the hand-written schema and the `jsonschema` import
  go — the setup step's requirements are enough.
- **`redaction`** reuses `runtime.telemetry_contract.LoopbackCollector`; the old
  `verify_system.py --check-redaction` stays for this repository's own CD and self-test until C9.
- **`providers.json` gains a `security` port**; `adopt` writes it (no `emitter` — that is the
  tenant's to declare); the launcher answers `process-gate security …` as it does `evals run`.
- **The setup action's description** names the security port.

### Conformance

`agentsmith conformance --port security --provider "<command>"` builds `fixture.json`'s repository —
a complete security pack, a declared posture, a tenant control whose suite passes, and a stub
emitter — and runs `cases.json`, one change per case: a clean pack passes; a template risk entry, a
placeholder agency manifest, a missing allowlist each fail their control; a tenant registry that
redefines a contract control fails, one that does not match its schema is not gradable; a declared
`prompt_guard: off` and `warn` fail with `PROMPT_GUARD=default` in the environment (ignored); a
tenant control whose suite fails, fails; redaction with an emitter that redacts passes, one that
leaks fails, one that plants nothing is not gradable, and `"emitter": "none"` is not applicable; and
no answer to an unknown verb. A stub provider that reports `pass` on a leaking emitter is shown to
fail.

### Tenant steps — after the release that carries it (2.3.0)

- **KYC Sentinel**: its strict harness step becomes `process-gate security check`; `providers.json`
  declares the security port with `python3 scripts/telemetry_smoke.py` as its emitter, which plants
  the probes when asked; `tenant.yaml` declares `moderation.mode: required`; the step's posture
  variables go.
- **OTS**: `eval-security.yml` calls the declared command through the provider's setup step, with
  an evidence directory; its CD redaction steps call `security redaction`; it declares `"emitter":
  "none"` (its spans are in the frozen template work) and its moderation mode; vendored
  `fixtures/security/` goes. Its SEC-RISK-001 and SEC-AGENCY-001 stay red until the owner authors
  them — the contract reports them, it does not write them.

**Deliberately not done:** a release asset carrying the provider's own evidence pack for the
provider rows to cite (the owner chose not-run-and-named); the deployment's runtime posture (an
environment variable can still override `tenant.yaml` in a deployed process — the runtime's
documented precedence, not this check's); a tenant's own residency declaration for SEC-SOV-001; the
workflow templates, which stay as they are until C9 as C6 decided.

## Pillars

- P1 applies — `.agent-rfc/designs/governance-contracts.md` defines C7; the owner's two decisions are recorded in Problem; this design precedes the code.
- P2 applies — `scripts/security_port.py` wraps the existing runners rather than re-implementing them; `runtime/conformance.py` gains the port; `runtime.telemetry_contract.LoopbackCollector` is reused for redaction. No dependency added; `jsonschema` stops being needed by the port.
- P3 applies — `scripts/gate_tracing.py` `gate_span` wraps each `security check` and `redaction` as `gate.security_check` / `gate.security_redaction` with the verdict, as the evals port does.
- P4 applies — `runtime/conformance.py`'s security suite scores AgentSmith and a lying stub; tests for each verdict, the subject split, posture from the declaration, and redaction both ways. Mutations: a provider row run in a tenant, the environment's posture beating the declaration, a leaked probe passing, a `gap` failing the verdict.
- P7 applies — `scripts/gate_models.py`: the pack files, request, results and declaration are Pydantic V2 models with generated schemas.
- P8 applies — `contract/telemetry/v1/protocol.md` defers redaction to this contract; `redaction` judges what reaches an OTLP receiver, not what a helper returns.
- P9 n/a — no orchestration.
- P10 n/a — no model call; no check calls a judge.
- P11 applies — `scripts/security_port.py` treats the pack files and the tenant's registry as data; a tenant's suite, hook and emitter run as subprocesses in the repository's interpreter, never imported into the provider.
- P12 applies — `scripts/security_port.py`'s probes are fixed non-secrets in the contract; a leak is reported by the probe's kind, never its value, and the emitter's own OTLP credentials are removed from its environment.
- P13 applies — `.githooks/process-gate` makes the security port closed in CI with no non-strict mode; a tenant registry may only add controls.
- P14 applies — `contract/security/v1/fixture.json` carries the whole pack and a stub emitter, so a conformance run needs nothing from a provider's installation.
- P15 applies — `scripts/security_port.py` keeps pass, fail, gap and not applicable apart per row, and says whose evidence each row is.
- P16 applies — `providers.json` `"emitter": "none"` and `"security": "none"` are recorded routes for a repository with nothing to check.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the posture checked is the one the repository declares, not the one a CI step sets.
- `implemented-not-invoked` — a control passes on what the repository does, not on the provider's library tests.
- `failure-is-not-a-result` — no non-strict mode; a declared gap is visible, an undeclared one fails.
- `test-the-contract` — a stub emitter that leaks, and a lying provider, are shown failing.
- `single-source-of-truth` — the runners stay the one implementation; pack schemas generated from models.
- `environment-parity` — the verdict no longer depends on how the provider was installed.
