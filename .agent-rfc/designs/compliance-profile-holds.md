---
status: active
scope:
  - agentsmith/compliance.py
  - agentsmith/runtime_server.py
  - agentsmith/workflows/base_workflow.py
  - agentsmith/vector_store.py
  - agentsmith/mcp_pin.py
  - agentsmith/cli.py
  - agentsmith/test/test_compliance_runtime.py
  - scripts/compliance_checks.py
  - scripts/compliance_port.py
  - scripts/gate_shell.py
  - scripts/test/test_compliance_checks.py
  - scripts/test/test_compliance_port.py
  - workflow-templates/agentsmith-supply-chain.yml
  - .githooks/process-gate
  - .github/scratch-tenants/**
---
# The `dubai-gov` profile's checks and records hold

From the 4.1.0 release review: R12, R13, R14, R15, R16, R18, R19, R21 (the reserved kinds), R22, R24, R25, R26 and R29 (the runtime half). Follows `.agent-rfc/designs/compliance-build.md` (done), whose claims these were.

## Problem

Each finding let a "verified", "recorded", "signed" or "enforced" statement read true when it was not:

- **R12** `OB-SUPPLY-CHAIN` passed when the workflow file existed, and the template stayed green on a stack it did not know, writing no SBOM.
- **R13** `purge_runs` committed the delete, then could fail to record it; `set_stop` the same. `ops purge --apply` asked nobody.
- **R14** On the Temporal path, a decision stored after a timeout, or signalled early, answered the next request whatever its input.
- **R15** A signature with no `expires_at` (or 99,999 days) satisfied a recurring obligation for ever.
- **R16** The Arabic check read the trajectory suite (tool names) and failed on it, and passed with no suite at all, claiming the base suites have Arabic (only fairness does).
- **R18** `COPY . .` with `.agenticframework` in `.dockerignore` read as "the declaration ships"; a drill dated 2099 passed; the data-class message claimed every gateway call.
- **R19** A system prompt under eight words was never compared; an unsigned mark with a recomputed digest verified.
- **R21** The sidecar's reserved kinds were a second list, missing `retention_purge`.
- **R22** The security map said MCP servers are not checked at all, though the profile pins them.
- **R24** Deleting `compliance.json` while the config enforced the profile read as "no profile" and was green.
- **R25** A vector upsert keyed on id alone moved another tenant's row.
- **R26** MCP pinning read one file and the first page of tools.
- **R29** `requested_by` was free text compared with a sign-in email.

## Approach

- **Supply chain.** The check parses the workflow: it must run on `push` or `pull_request` and have a step that runs `pip-audit`, `npm audit` or `govulncheck`. The template gains npm and Go steps, Python for a lock, `requirements.txt` or `pyproject.toml`, an SBOM per stack in `sbom/`, a last step that fails when nothing was scanned, and `if-no-files-found: error`. The pass message names the MCP files read.
- **Records with their change.** `record()` is split so its insert (`_append`) can join another transaction. `_recorded_change` runs a change and its record in one transaction; the key is checked first. `purge_runs(apply=True)` and `set_stop` use it. `ops purge --apply` counts, then asks for the app id at a terminal, through the same helper `ops resume` now uses.
- **Temporal decisions.** `run_with_hitl_gate(compliance=True)` drops any decision held for the gate before asking, and waits only for one whose `payload_sha256` equals the digest of this request's input. The digest is computed in workflow code the same way as `compliance.payload_digest`; a test holds them equal.
- **Expiry from the catalogue.** `latest_valid` takes the row's `recurrence_days`: a signature counts until `attested_at + recurrence_days`, or its own `expires_at` if earlier. A signature dated in the future does not count. The row's `expires_at` reports the effective date. The portal's checklist gets the same rule in `.agent-rfc/designs/portal-compliance-holds.md`.
- **Arabic.** Only golden, hallucination, fairness and adversarial are read, by path. With none of the app's own, the check is `not_applicable` ("cannot be judged yet"), not `pass`; the evals job already refuses the ungraded suites, and a second red here would not add a fact (and would turn the `dubai-gov` scratch tenant red for a reason `expect-ungraded.sh` does not recognise).
- **Image, drill, data class.** An image ships the declaration when it copies it and `.dockerignore` does not exclude it, or when the Dockerfile sets `ENV COMPLIANCE_PROFILE`. A drill dated more than five minutes ahead is ignored. The `dubai-gov` scratch tenant's fixture drill was dated 2099 to keep it passing; `build.sh` now dates it when the tenant is built, and the fixture holds 1970, so a build that skipped the stamp fails. The data-class message says which receivers it read.
- **Leak and mark.** A system prompt of three to seven words is compared whole; under three is skipped as a common phrase. `verify_marking(require_signature=None)` requires a signature whenever a key is set.
- **One list of kinds.** `compliance.FRAMEWORK_KINDS`; the sidecar's `RESERVED_KINDS` is it.
- **Leaving a profile.** With `process-gates.json` enforcing a profile, a missing declaration fails both the launcher and the port, and `.agenticframework/compliance.json` joins the shell gate's protected paths.
- **Vectors.** The upsert's update applies only when the stored row's tenant is the writer's (`IS NOT DISTINCT FROM`, so the no-tenant case still updates), returns the id, and raises `ValueError` (after a rollback) when no row comes back.
- **MCP.** Servers are read from `.mcp.json`, `.cursor/mcp.json`, `.vscode/mcp.json` and `.gemini/settings.json` (a non-root server is named `<file>#<name>`), and `tools/list` is followed through `nextCursor`, up to 100 pages, over stdio and HTTP.
- **Requester.** On a compliance gate, `requested_by` must look like an email; the manual says it must be the sign-in email. The portal's comparison is in the portal design.
- **Docs.** The security map's ASI04 row says what the profile checks and what it does not; ASI01's last sentence names `SEC-CIAGENT-001` instead of calling CI unchecked. The manual's profile paragraph names `requested_by`, the image rule, leaving a profile and the purge confirmation.

## Pillars

- P1 applies — the review's findings are the requirement; `.agent-rfc/designs/compliance-profile-holds.md` is the plan.
- P2 applies — `agentsmith/compliance.py` gains `_append` and `_recorded_change` rather than a second writer; no new dependency.
- P3 n/a — no span is added or removed; records are the compliance chain, unchanged in shape.
- P4 applies — `agentsmith/test/test_compliance_runtime.py`, `scripts/test/test_compliance_checks.py` and `scripts/test/test_compliance_port.py` gain a test per finding, each failing on `origin/main`; mutation-checked by hand.
- P7 n/a — no model changes; `Obligation.recurrence_days` already existed.
- P8 n/a — the telemetry wire is untouched.
- P9 applies — `agentsmith/workflows/base_workflow.py` ties a human decision to the request it answers.
- P10 n/a — no routing.
- P11 applies — `agentsmith/mcp_pin.py` pins tool descriptions an outside server supplies, on every page; `agentsmith/compliance.py` refuses an unsigned mark where marks are signed.
- P12 applies — `agentsmith/compliance.py` checks `COMPLIANCE_RECORD_KEY` before any change, so no change is made that cannot be signed.
- P13 applies — `.githooks/process-gate` and `scripts/compliance_port.py` fail an enforced profile whose declaration is gone; `scripts/gate_shell.py` protects the file.
- P14 applies — `workflow-templates/agentsmith-supply-chain.yml` changes, and the tests that run its steps are updated with it.
- P15 applies — `scripts/compliance_checks.py` answers `not_applicable` where it cannot judge, never `pass`.
- P16 applies — `CHANGELOG.md` names each change; tenants take the template with `agentsmith sync`; a vector write that now raises names the id to change.

## Deviations

none

## Dependencies

The supply-chain template runs, on the tenant's runner, tools pinned by version: `pip-audit==2.9.0` and `cyclonedx-bom==7.1.0` (as before), `@cyclonedx/cyclonedx-npm@1.19.3`, `golang.org/x/vuln/cmd/govulncheck@v1.1.4`, `github.com/CycloneDX/cyclonedx-gomod@v1.8.0`, and the actions `actions/setup-node@v4` and `actions/setup-go@v5`. None is a dependency of AgentSmith itself.

## Levers

- `gate-integrity` — each check reads what the file is meant to do, not that it exists (R12, R18, R24).
- `early-exit-keeps-the-record` — a change and its record commit together (R13).
- `grep-for-siblings` — the Temporal path gets the store path's digest check (R14); ASI01's stale sentence beside ASI04.
- `declared-vs-enforced` — `recurrence_days` is read when judging (R15).
- `test-that-cannot-fail` — no suite is not a pass (R16).
- `guards-must-be-able-to-fail` — the short prompt and the unsigned mark (R19).
- `one-catalog` — one list of framework kinds (R21).
- `docs-match-behaviour` — the map's ASI04 and ASI01 rows (R22).
- `consistent-auth-gates` — the vector write is scoped like the read (R25).
- `aggregates-name-their-scope` — the MCP pass names the files read (R26).
- `validate-on-the-receiving-side` — `requested_by` is checked where it is sent (R29).
- `irreversible-needs-confirmation` — `ops purge --apply` (R13).
