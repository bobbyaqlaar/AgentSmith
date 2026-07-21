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
| 1.0.x | 3.11 | 0.2 | 4.0 | Initial public release |

## [Unreleased]

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
- **Docs:** SPECS §3/§5.5/§16, OPERATIONS TTFT + prompt-guard sections
  (incl. a rollout procedure and mode table), `docs/security-framework-map.md`
  SEC-PROMPT-001 row.

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
