---
status: done
scope:
  - scripts/requirements-gate.txt
  - .github/actions/setup-agentsmith/action.yml
  - scripts/test/**
  - scripts/mutation_check.py
---
# The CI setup step serves the evals provider too

Found 2026-10-09 moving AqlaarTeleologyStudio's evals onto `contract/evals/v1`.

## Problem

- **A tenant's CI that installs the provider through its setup step cannot grade a judged suite.**
  `.github/actions/setup-agentsmith` installs `scripts/requirements-gate.txt` — pydantic,
  OpenTelemetry, PyYAML — and puts `agentsmith` on PATH. The evals provider's judge path reaches
  every direct-API judge (Anthropic, OpenAI, Gemini, Groq, OpenRouter, any OpenAI-compatible route)
  through `httpx`, which that list lacks. Measured: the evals conformance suite against a provider in
  exactly that environment, 8/17 — every judged case `no_verdict`; with `httpx` added, 17/17.
- **The failure hides behind the contract's own exception.** A suite that cannot reach its judge
  answers `no_verdict`, and a tenant may declare `no_verdict: warn` for a judge out of quota — so a
  provider that can never grade reads as weather, every run. KYC Sentinel escaped it only because its
  job installs the whole framework from a checkout; OTS's eval jobs would use the setup step.

## Approach

- **`scripts/requirements-gate.txt` lists `httpx`** (the range `requirements.txt` uses), with the
  reason beside it — as it lists PyYAML for the rules port. The file is what the provider's CI
  setup installs; its name stays, every reference to it (the setup action, the sync workflow,
  self-test) unchanged.
- **The action's description** says it serves the declared ports, not only the gate.
- **A test runs a judged suite with `httpx` unimportable** and shows it answers `no_verdict`, so the
  listed package is the one the judge needs, and the list test names `httpx`.
- Judges on Vertex AI and Bedrock need their cloud SDKs (`google-auth`, `boto3`); those stay the
  tenant's to install — the routes are optional and heavy, and say which SDK is missing when used.
- Patch release 2.2.3 after merge, so a tenant's setup step can pin it.

## Pillars

- P1 applies — `.agent-rfc/designs/setup-evals-provider.md` records the measurement before the change.
- P2 applies — `scripts/requirements-gate.txt` stays the one list the provider's CI setup installs; no second file.
- P3 n/a — no tracing changes.
- P4 applies — `scripts/test/test_evals_contract.py` shows a judged suite without `httpx` cannot grade; `scripts/test/test_process_gate.py`'s list test names it.
- P7 n/a — no models change.
- P8 n/a — no telemetry wiring.
- P9 n/a — no orchestration.
- P10 applies — `scripts/requirements-gate.txt` lets the provider's CI environment reach the judge route `models.yaml` declares.
- P11 n/a — no untrusted content.
- P12 n/a — no credential handling changes.
- P13 applies — `.github/actions/setup-agentsmith/action.yml`'s environment can now grade, so a declared `no_verdict: warn` covers a judge that did not answer, never one that could not be called.
- P14 n/a — no fixtures.
- P15 applies — `scripts/requirements-gate.txt` closes a path where "the judge did not answer" meant "the provider could not call one".
- P16 n/a — no new fallback.

## Deviations

none

## Dependencies

- `httpx>=0.25,<1.0` in `scripts/requirements-gate.txt`, already a framework dependency in `requirements.txt` (transitively `httpcore`, `h11`, `anyio`, `idna`, `certifi`, `sniffio`).

## Levers

- `environment-parity` — the provider grades the same in a tenant's CI setup as in a full install.
- `failure-is-not-a-result` — an unreachable judge must not be a missing package wearing a quota's clothes.
- `test-the-contract` — the evals conformance suite, run against the setup step's environment, found it.
