---
status: active
scope:
  - contract/evals/v1/**
  - scripts/run-evals.py
  - scripts/evals_port.py
  - scripts/gate_models.py
  - runtime/cli.py
  - runtime/conformance.py
  - runtime/adopt.py
  - .githooks/process-gate
  - workflow-templates/**
  - scripts/test/**
  - scripts/mutation_check.py
  - .agenticframework/process-gates.json
  - contract/rules/v1/extends.schema.json
---
# C6 — The evals contract: a tenant's datasets, judged by the provider it declares

Slice C6 of `.agent-rfc/designs/governance-contracts.md`. An eval is a command port, like the gate
and the rules: the tenant owns its datasets and its application's outputs; a provider judges them and
answers with a scorecard. Today the only judge is a framework script every tenant runs by path.

## Problem

Measured on 2026-10-06:

- **Every tenant runs the judge by path.** The eval workflow templates (`eval-scorecard.yml`,
  `eval-fairness.yml`, `eval-hallucination.yml`) run `python3 scripts/run-evals.py` — the vendored
  copy; KYC Sentinel's CI runs `$AGENTSMITH_DIR/scripts/run-evals.py` from a checkout four times;
  OTS's eval workflows run its vendored copy.
- **What a tenant owns has no published shape.** Five suites read five dataset files
  (`.agent-rfc/fixtures/{golden,fairness,hallucination,rag_poison}_evals.json`,
  `.agent-rfc/security/adversarial_evals.json`) and their judge criteria; the fields are whatever
  `run-evals.py` reads.
- **The scorecard has no published shape either**, though three readers depend on it: the security
  harness (`adversarial_miss_rate`), the promotion loop and the evidence pack (`delivery_evidence.py`).
- **A case without an output is filled by the framework's own pipeline.** When a case carries no
  `actual_output`, `run-evals.py` generates one with AgentSmith's Architect→Developer→Validator
  *code-generation* pipeline — right for AgentSmith's own suite, meaningless for an application
  tenant (KYC's fairness cases once all scored 0.00 that way; it pins outputs with its own script
  now). The provider running the tenant's application, or a stand-in for it, is the coupling the
  programme removes.
- **Four verdicts, two of them easy to confuse.** `pass`, `fail`, `no_verdict` (the judge could not
  answer: an expired key, an exhausted quota — exit 0 with a warning) and skipped (fewer than three
  cases — exit 0). In CI the last two read as green.

## Approach

### `contract/evals/v1/` — a command port

`<evals-command> run` — cwd is the repository; stdin one request
(`request.schema.json`: `suite`, optional `fail_below`/`fail_above`); stdout one scorecard; exit 3 for
"cannot run here". An answer is a scorecard on stdout; anything else is no answer.

- **Datasets are the tenant's** — `dataset.schema.json` per suite, generated from models in
  `scripts/gate_models.py`: each case's `id`, `input`, **`actual_output` (required)**, the suite's own
  fields (`pair_id` and the protected attribute for fairness; `context` and the declared control for
  hallucination; `expect` for adversarial and rag_poison). The paths stay where tenants keep them.
- **The tenant produces the outputs.** A case without `actual_output` is reported **not gradable**
  and counts against the suite — never filled by a provider's pipeline. Generating outputs is the
  tenant's own step, before the eval (KYC's `pin_eval_outputs.py` is the model). AgentSmith's own
  golden suite keeps its generator behind a provider flag that is not part of the contract.
- **The scorecard** — `scorecard.schema.json`, generated: `suite`, `verdict`, the aggregate the
  suite gates on, the threshold applied, `cases_total`, `cases_graded`, per-case rows, the judge
  that answered. Its existing keys are kept, so the three readers stay unchanged.
- **Five verdicts, stated:** `pass`, `fail`, `no_verdict` (the judge did not answer — with why),
  `not_gradable` (cases without outputs, or fewer than the suite's minimum), and the exit code
  follows: 0 for `pass`, 1 for `fail`; for the other two the **caller** decides.
- **Failure is closed in CI**, as the umbrella's table says — a verdict that did not run is not a
  pass. The launcher fails the step on `no_verdict` and `not_gradable` **unless the tenant's
  declaration says otherwise**: `providers.json` `evals` may name `"no_verdict": "warn"` per suite —
  an always-governed file, so the choice is reviewed and visible. Today's behaviour (both green)
  becomes a declared exception rather than a default.
- **Thresholds** come from the request, else the tenant's declaration (`extends.evals` in
  `process-gates.json`: per-suite `fail_below` / `fail_above`), else the provider's defaults —
  never from the environment of whoever runs CI.

### Amended while building (2026-10-06)

- **The provider exits 0 whenever it answers**; the verdict is in the scorecard, and the caller maps
  it to the step's result — as the gate contract does. ("Exit 0 for pass, 1 for fail" above is the
  launcher's mapping, not the provider's.)
- **`actual_output` is required for the judged suites** — golden, fairness, hallucination. The
  adversarial and rag_poison suites score the provider's guard on the input itself, with no judge
  and no output to supply.
- **No dataset is `not_gradable`.** `run-evals.py` seeds AgentSmith's own base cases when a tenant
  has no file; a contract run judges the tenant's data only.
- **The eval workflow templates stay as they are until C9.** They serve `tenant init`'s vendored
  tenants, whose workflows have no provider setup step to call; a tenant on the contracts calls the
  launcher from its own CI, as KYC's will.
- **The judge's calibrated bar is a declaration too.** `models.yaml`'s judge role may carry a
  per-suite `fail_below` (KYC's does: 0.95 for golden and fairness), calibrated for that grader. It
  is the tenant's committed file, not the environment, so it stays — after the request and
  `extends.evals`, before the provider's default.
- **A judge model that is no longer served is `fail`, not `no_verdict`.** `run-evals.py` already
  goes red on it: a repointed role is a broken configuration in the tenant's repository, which no
  later run clears, and a declared `no_verdict: warn` must not hide it. Verdicts from more than one
  judge or rubric are `fail` too, as they are today.
- **`extends.evals` is part of the one `extends` the rules contract publishes**
  (`contract/rules/v1/extends.schema.json` gains the optional key); the evals contract does not
  publish a second copy.
- **`agentsmith evals` already exists** (sync HITL feedback, then the scorecard). With no verb it
  keeps doing that; `agentsmith evals run` is the contract's verb.

### AgentSmith as the provider

- **`agentsmith evals run --suite <s>`** through `_provider_scripts()` — `scripts/evals_port.py`
  over `run-evals.py`'s scoring, so the judging logic is not duplicated. `run-evals.py` keeps its
  flags for this repository and vendored tenants until C9.
- **`providers.json` gains an `evals` port**; `adopt` writes it, `sync` adds it to a declaration it
  wrote. The launcher answers `process-gate evals run --suite <s>`, as it does `rules check`.
- **The eval workflow templates** call `bash .githooks/process-gate evals run --suite <s>` after the
  provider's setup step, instead of a script path.

### Conformance

`agentsmith conformance --port evals --provider "<command>"` builds `fixture.json`'s repository —
datasets for each suite with **fixed outputs**, and a **stub judge** the provider is pointed at (the
conformance cases must not depend on a live model) — and runs `cases.json`: a dataset that passes, one
that fails, cases without outputs (`not_gradable`), a judge that does not answer (`no_verdict`), a
fairness pair scored apart, an adversarial miss above its limit, thresholds from the request beating
the declaration. AgentSmith is scored by it; a stub provider that reports `pass` when the judge never
answered is shown to fail.

### Tenant steps — after the release that carries it

- **KYC Sentinel**: its four `run-evals.py` steps become `process-gate evals run --suite …` through
  the gates job's setup step; it declares `no_verdict: warn` for the suites its judge's free-tier
  quota exhausts, so the exception it lives with is written down.
- **OTS**: its eval workflows call the declared command against its own datasets (governance only).

**Deliberately not done:** the TTFT and shadow evals (`verify_ttft.py`, `shadow-eval.py`) — live
measurements against a deployed service, closer to Ops records (C8); the security harness, whose
adversarial suite C7 owns the control registry for (this slice publishes the dataset and scorecard
it reads, unchanged).

## Pillars

- P1 applies — `.agent-rfc/designs/governance-contracts.md` defines C6; this design precedes the code; the owner's decision on closed-by-default is called out below.
- P2 applies — `scripts/run-evals.py` keeps its scoring; `scripts/evals_port.py` wraps it rather than duplicating it; `runtime/conformance.py` gains the port. No dependency added.
- P3 applies — `scripts/gate_tracing.py` `gate_span` wraps each `evals run` as `gate.evals_run` with the suite and verdict, as the rules port does.
- P4 applies — `runtime/conformance.py`'s evals suite against AgentSmith and a lying stub provider; tests for each verdict and for threshold precedence. Mutations: `no_verdict` reported as `pass`, a case without output graded, the environment beating the declaration, the launcher passing a `not_gradable`.
- P7 applies — `scripts/gate_models.py`: the datasets and the scorecard are Pydantic V2 models with generated schemas.
- P8 n/a — no telemetry wiring.
- P9 n/a — no orchestration.
- P10 applies — `scripts/run-evals.py` routes the judge through the gateway and the tenant's `models.yaml` judge role, unchanged; conformance uses a stub judge so no model is called.
- P11 applies — `scripts/evals_port.py` treats dataset files and outputs as data: the judge prompt quotes them, as `run-evals.py` already does.
- P12 applies — `scripts/run-evals.py` reads the judge's API key by the variable `models.yaml` names; the contract carries no credential.
- P13 applies — `.githooks/process-gate` makes `no_verdict` and `not_gradable` fail CI by default where they passed; an exception must be declared in an always-governed file.
- P14 applies — `contract/evals/v1/fixture.json` pins fixed outputs and a stub judge's answers, so a conformance run never drifts with a model.
- P15 applies — `scripts/evals_port.py` keeps pass, fail, no verdict and not gradable apart, and says which and why.
- P16 applies — `providers.json` lets a tenant declare `no_verdict: warn` per suite, a recorded route for a judge it cannot always reach.

## Deviations

none

## Dependencies

none

## Levers

- `failure-is-not-a-result` — no verdict and not gradable stop reading as green.
- `declared-vs-enforced` — an exception to closed-in-CI is a reviewed declaration, not a default.
- `environment-parity` — thresholds come from the request or the declaration, not the runner's environment.
- `single-source-of-truth` — one scoring implementation behind the script and the port; schemas generated from models.
- `test-the-contract` — a stub judge makes conformance deterministic, and a lying provider is shown failing.
