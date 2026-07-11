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
