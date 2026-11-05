---
status: done
scope:
  - agentsmith/**
  - runtime/**
  - scripts/**
  - templates/**
  - workflow-templates/**
  - examples/**
  - enterprise/**
  - contract/**
  - fixtures/**
  - init-db/**
  - portal/**
  - .github/**
  - .githooks/**
  - .agenticframework/process-gates.json
  - .claude/settings.json
  - install-ai-stack.sh
  - pyproject.toml
  - pytest.ini
  - requirements*.txt
  - docker-compose*.yml
  - .agent-rfc/fixtures/knowledge_graph.json
---
# The package imports as `agentsmith`

## Problem

The library installs as the top-level name `runtime`, a generic word that collides in any tenant holding a `runtime/`
directory or dependency, and that says nothing about whose it is. `pyproject.toml` has named this a follow-up for a major
version since 1.1.0. Going public fixes the name for everyone after, so the owner decided on 2026-11-03: rename it, before the
launch.

## Approach

- **Import name `agentsmith`:** `runtime/` moves to `agentsmith/`, and every import, `-m`, dotted path and repository path follows.
  The console script becomes `agentsmith = "agentsmith.cli:main"`.
- **Distribution stays `agentsmith-runtime`:** `agentsmith` on PyPI is an unrelated Neo4j tool, last released in 2019.
- **MAJOR, 4.0.0, with no `runtime` shim.** A shim would keep the collision this removes. A tenant pinned to 3.x keeps working until it
  moves, and the 4.0.x row says what to change.
- **What does not change:**
  - `agentsmith.runtime`, the OpenTelemetry scope in `contract/telemetry/v1`: a wire value, not an import.
  - Legacy `runtime` in `agentsmith/adopt.py`'s and `scripts/verify_system.py`'s detection of a vendored copy: it names what a pre-3.0.0
    tenant holds.
  - History: `CHANGELOG.md`'s released sections, `docs/PRODUCT_ARCHIVE.md`, `docs/REVIEW_LOG.md` and `.agent-rfc/` records.
  - English: "at runtime", the portal's Edge runtime, "the production runtime".
  - The label of the required check `Python scripts/runtime/examples`: `main` requires it by name, so changing it is a branch-protection decision.
- **KYC Sentinel moves in its own PR** after the release, the one tenant importing the library. Tenant B imports nothing of it.

## Pillars

- P1 applies — `.agent-rfc/designs/package-agentsmith.md` records the owner's decision and what stays named `runtime`.
- P2 applies — `pyproject.toml` declares the one name; no dependency is added and no shim kept.
- P3 applies — `contract/telemetry/v1/attributes.json` keeps its scope value, so spans read the same, and `agentsmith/tracing.py` only moves.
- P4 applies — `scripts/test/test_package_name.py` fails if a tracked file imports the old name, and the existing suites run at their new paths.
- P7 applies — `agentsmith/cli.py` and the Pydantic models move unchanged; only their import paths differ.
- P8 applies — `contract/telemetry/v1/fixture.json` is unchanged, which `scripts/test/test_telemetry_contract.py` holds.
- P9 n/a — no orchestration logic changes.
- P10 n/a — `agentsmith/llm_gateway.py` routes as before; no model choice changes.
- P11 n/a — no new reading of untrusted content.
- P12 n/a — no secret is read or moved.
- P13 applies — `.agenticframework/process-gates.json` gates `agentsmith/**` in place of the old path, in the same commit, so no code leaves the gate.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated for every moved file.
- P15 applies — `CHANGELOG.md`'s 4.0.x row names the one change a tenant makes; a stale import fails with `ModuleNotFoundError`, not silently.
- P16 applies — `.github/actions/setup-agentsmith/action.yml` installs what a tag declares, so a tenant recovers by pinning back to `@v3.0.1`.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the name is held by a test over every tracked file, not by a search done once.
- `docs-match-behaviour` — what stays `runtime`, and why, is written down and tested.
- `two-owners-two-cadences` — tenants move on their own schedule; the row is their path, and KYC's PR is the worked example.
- `environment-parity` — the end-to-end release install runs on this tree, so a name missed in a packaged path fails there.
- `when-the-fallback-fails` — detection of a pre-3.0.0 copy is the path nobody runs by hand, and the rename nearly silenced it.
- `test-the-contract` — the required job's name and the wire scope are contracts a text substitution cannot see.

## Correction, 2026-11-05

"A tenant pinned to 3.x keeps working until it moves" was wrong for one file: a 3.x `agentsmith-sync.yml` follows the latest release, so it fails once 4.0.0 is out. Found cutting the release; `.agent-rfc/designs/release-4-0-0.md` handles it. No shim: nobody known holds that file, and `agentsmith sync` by hand repairs it.
