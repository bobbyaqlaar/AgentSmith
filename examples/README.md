# AgentSmith — Reference Examples

This directory contains reference tenant application examples.

## Important

> **Copy and rename these directories into your own repository.**
> Do NOT deploy from `AgentSmith/examples/` directly.
> Examples are reference implementations, not production deployment targets.

Each example demonstrates the full tenant application pattern:
- `.agenticframework/tenant.yaml` — tenant configuration
- `.agent-rfc/` — spec files and fixtures
- `scripts/` — vendored framework scripts (Option A)
- `.github/workflows/` — per-environment CI/CD workflows
- Domain agents and workflows

## Available Examples

### `oil-price-agent/`

A reference AI agent for oil price prediction and decision-making.
Demonstrates:
- Temporal workflow with three nodes (ingestion → prediction → decision)
- HITL pause/resume for price anomaly alerts
- Per-tenant budget configuration
- Shadow eval setup (5% production trace sampling)
- Full OTel instrumentation with `tenant.id` on all spans

**Status:** Phase 2 (stub — full implementation pending)

## Creating Your Own Tenant Repo

```bash
# Use the scaffolding command
ai-tenant-init <your-tenant-id> --stack python-fastapi

# This creates:
#   .agenticframework/tenant.yaml
#   .agent-rfc/fixtures/golden_evals.json  (bootstrapped from framework base)
#   .github/workflows/ci-python-fastapi.yml
#   .github/workflows/cd-staging.yml
#   .github/workflows/cd-production.yml
```

Or fork `examples/oil-price-agent/` and replace the domain logic.
