---
status: done
scope:
  - fixtures/**
  - contract/compliance/**
  - contract/runtime/**
  - install-ai-stack.sh
  - contract/ops/**
  - agentsmith/**
  - scripts/**
  - .githooks/process-gate
  - workflow-templates/**
  - templates/**
  - portal/**
  - .github/**
  - docker-compose.yml
  - requirements*.txt
  - requirements*.lock
  - pyproject.toml
  - .agenticframework/process-gates.json
---
# Compliance build: the `dubai-gov` profile, Phases 1 to 6

The build half of `.agent-rfc/designs/compliance-readiness.md`. The owner directed on 2026-11-08 that the whole set lands
together in one pull request, so this one design and one review record cover Phases 1 to 6, where the umbrella planned one
per slice.

## Problem

`.agent-rfc/designs/compliance-readiness.md` lists the measured gaps. Phase 0 corrected the claims; none of the capabilities exist.

## Approach

As the umbrella describes, with the owner's decisions of 2026-11-08:

- A failed control or expired attestation blocks production on the profile; exceptions only through `agentsmith approve`.
- Basic auth is refused on the profile.
- The portal may be down as long as the record reaches the database. **A tenant app on the profile raises an error and stops the
  affected function when its record cannot be written.** Only that function stops: the rest of the app keeps running.
- `compliance_officer` attests. The aim is to help an enterprise become ready for a DESC certification.

**What is "affected".** A gated action (`needs_hitl` in the agency manifest), a model call on data classed as classified, and an action
while the stop flag is set. Each refuses with `agentsmith.compliance.ComplianceRefused`, which names the obligation.

**Where things live.** `agentsmith/compliance.py` is the runtime side a deployed app imports: declaration, refusal, outbox, stop flag.
`scripts/compliance_port.py` is the provider side: `check`, `status`, `export`, `sync`. `fixtures/compliance/catalogue.json` is the one
catalogue, shipped where the security fixtures ship. `contract/compliance/v1` publishes the shapes. Portal state is read through a generated
copy of the catalogue, held to the source by a check.

**Adoption.** `compliance` in `.agenticframework/process-gates.json` plus `.agenticframework/compliance.json`, written by
`agentsmith compliance enable`. Without them nothing changes: every new branch in the runtime is behind `profile_active()`.

### Close-out (owner, 2026-11-08)

Batch 1: portal seen in a browser; pytest 9; LangGraph and LangChain 1.x; `requested_by` required; `proxy.ts`; audit views scoped; `SEC-AUDIT-002` bound; the launcher test; `security check` on an open pipe; `contract/` and the compliance files installed. Batch 2: a scratch tenant on the profile; MCP tool-definition hashes; EU AI Act Article 50(2) marking; a local sidecar, `agentsmith runtime serve`, so other stacks use the same Python guards.

## Pillars

- P1 applies — `.agent-rfc/designs/compliance-readiness.md` is the plan and this file the build.
- P2 applies — `scripts/security_port.py` is the shape the new port copies; no new service.
- P3 applies — `agentsmith/llm_gateway.py` emits the refusal on its existing span path; a refusal is an attribute, not a new exporter.
- P4 applies — `scripts/test/test_security_contract.py` is the model for the new contract tests; each check is mutation-tested through the scratch tenant.
- P7 applies — `scripts/gate_models.py` is the pattern: every declaration and attestation crossing a boundary is a Pydantic model.
- P8 applies — `contract/telemetry/v1/protocol.md` is unchanged; new attributes are additive.
- P9 n/a — no orchestration graph changes; the base workflow gains a named decision signal.
- P10 n/a — no routing change; the gateway only refuses.
- P11 applies — `portal/lib/devIngest.ts` is the pattern: attestations and decisions from outside are validated whole or refused.
- P12 applies — `scripts/send_dev_record.py` is the pattern: tokens by name from the environment, never written or printed.
- P13 applies — `agentsmith/machine/governance.py` is the pattern for terminal-only attestation, and `scripts/gate_pillars.py` for the ratchet.
- P14 applies — `scripts/test/test_security_registry.py` is the pattern: generated copies are held to their source.
- P15 applies — `contract/security/v1/protocol.md` separates a verdict from no answer; "could not reach" is never a pass on the profile.
- P16 applies — `CHANGELOG.md` names the additive migration; the schema change is `IF NOT EXISTS` and a tenant leaves the profile through a recorded deviation.

## Deviations

none

## Dependencies

No package is added to the runtime. One Python package is new to the repository: `langchain-protocol`, required by LangChain 1.x, in `requirements-pipeline.lock` only. Existing locked packages move to fixed releases:
aiohttp, certifi, multidict (6 to 7), yarl, pyasn1, pyjwt, urllib3, cryptography (43 to 50) and the opentelemetry set. Two transitive packages are new, required by that set:
opentelemetry-exporter-http-transport and opentelemetry-exporter-otlp-common. `pydantic` becomes direct.
LangGraph, LangChain and what only they need leave `requirements.lock` for `requirements-pipeline.lock`. Both now move: pytest 9, pytest-asyncio 1.x, LangGraph and LangChain 1.x. No package is added to the runtime. Portal: Next.js 16 and React 19; `npm audit fix` moves nanoid and source-map-js.
CI tools (pip-audit, bandit, cyclonedx-bom) install inside the job, pinned, and enter no lock.

Entries `requirements-pipeline.lock` gains, direct and transitive. Each was in `requirements.lock` before this change except `langchain-protocol`: `annotated-types`, `anthropic`, `anyio`, `charset-normalizer`, `distro`, `docstring-parser`, `h11`, `httpcore`, `httpcore2`, `httpx`, `httpx2`, `httpx2-jsfetch`, `idna`, `jiter`, `jsonpatch`, `jsonpointer`, `langchain-anthropic`, `langchain-core`, `langchain-openai`, `langchain-protocol`, `langgraph-checkpoint`, `langgraph-checkpoint-postgres`, `langgraph-prebuilt`, `langgraph-sdk`, `langsmith`, `openai`, `opentelemetry-api`, `orjson`, `ormsgpack`, `packaging`, `psycopg`, `psycopg-pool`, `pydantic-core`, `pyyaml`, `regex`, `requests`, `requests-toolbelt`, `sniffio`, `tenacity`, `tiktoken`, `truststore`, `typing-extensions`, `typing-inspection`, `tzdata`, `uuid-utils`, `websockets`, `xxhash`, `zstandard`.

Entries `portal/package-lock.json` gains, all from Next.js 16 and its optional image optimiser: `@emnapi/runtime`, `@img/colour`, `@img/sharp-darwin-arm64`, `@img/sharp-darwin-x64`, `@img/sharp-freebsd-wasm32`, `@img/sharp-libvips-darwin-arm64`, `@img/sharp-libvips-darwin-x64`, `@img/sharp-libvips-linux-arm`, `@img/sharp-libvips-linux-arm64`, `@img/sharp-libvips-linux-ppc64`, `@img/sharp-libvips-linux-riscv64`, `@img/sharp-libvips-linux-s390x`, `@img/sharp-libvips-linux-x64`, `@img/sharp-libvips-linuxmusl-arm64`, `@img/sharp-libvips-linuxmusl-x64`, `@img/sharp-linux-arm`, `@img/sharp-linux-arm64`, `@img/sharp-linux-ppc64`, `@img/sharp-linux-riscv64`, `@img/sharp-linux-s390x`, `@img/sharp-linux-x64`, `@img/sharp-linuxmusl-arm64`, `@img/sharp-linuxmusl-x64`, `@img/sharp-wasm32`, `@img/sharp-webcontainers-wasm32`, `@img/sharp-win32-arm64`, `@img/sharp-win32-ia32`, `@img/sharp-win32-x64`, `detect-libc`, `semver`, `sharp`.

The `python-dubai-gov` scratch tenant declares `opentelemetry-api` so its health route opens a real span. It is that throwaway app's requirement and enters no AgentSmith lock.

## Levers

- `declared-vs-enforced` — each obligation is enforced, verified or attested.
- `implemented-not-invoked` — the scratch tenant runs the profile end to end.
- `single-source-of-truth` — one catalogue generates the portal copy and the documents.
- `gate-integrity` — attestation is terminal-only or by a signed-in named person; the profile ratchets.
- `failure-is-not-a-result` — unreachable is never a pass on the profile.
