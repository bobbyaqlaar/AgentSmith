---
status: done
scope:
  - .github/workflows/*.yml
  - agentsmith/models.yaml
  - agentsmith/test/*.py
  - scripts/security/runners/*.py
  - scripts/test/*.py
  - templates/agent-rules.yaml
  - workflow-templates/*.yml
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Name no private tenant or cloud project

## Problem

The owner decided on 6 Nov that one private tenant and the GCP project are not to be named in this public repository.
KYC Sentinel stays named. The tree names both about 230 times, in comments, docstrings, docs and records, and every
record a change writes is a chance to name them again.

## Approach

- One pass over every tracked text file: the tenant becomes "Tenant B", and the project becomes `$GCP_PROJECT_ID` in
  commands (the manual already defines it) and `PROJECT_ID` elsewhere. A lever-notes header name and a test lever lose
  the tenant's prefix. Records are edited too, because they are read on the repository's page like any other file.
- `scripts/test/test_private_names.py` fails on any tracked file holding one of the names. It holds them as SHA-256
  digests of exact tokens, so the guard does not publish what it guards.
- Git history keeps the names. Rewriting it would change every commit and invalidate every published tag that tenants
  pin, so that is left to the owner and not done here.

## Pillars

- P1 applies — `.agent-rfc/designs/name-no-private-tenant.md` records the owner's decision and its limit (history).
- P2 n/a — no code path or dependency changes; comments, docstrings and docs only.
- P3 n/a — no traced code path changes.
- P4 applies — `scripts/test/test_private_names.py` holds the decision for every later change.
- P7 n/a — no stack-specific rule changes.
- P8 n/a — no telemetry changes.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — no untrusted content is read.
- P12 applies — `scripts/test/test_private_names.py` keeps a cloud project identifier out of public commands; no secret is involved.
- P13 n/a — no gate changes; the new test runs in the existing pytest job.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated from the edited docstrings.
- P15 n/a — no signal is read.
- P16 n/a — a text change; reverted by reverting the commit.

## Deviations

none

## Dependencies

none

## Levers

- `every-line-earns-its-place` — a name the owner does not want public earns no line.
- `test-the-contract` — the decision is held by a test, not by memory.
