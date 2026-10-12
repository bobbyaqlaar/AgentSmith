---
status: done
scope:
  - pyproject.toml
  - install-ai-stack.sh
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Release 2.4.0

## Problem

The Ops contract (C8, `ops-contract`) is merged (#52), and a tenant moves onto it only through a
release: its worker and CI take the provider from a tag. OTS's and KYC Sentinel's moves wait on it,
and so does an operator issuing Ops tokens and replay keys from a portal built at a tag. The owner
asked for the release on 2026-10-12.

## Approach

- **2.4.0, a MINOR.** The contract is additive: a new ingest, a new token scope, a new CLI verb and
  conformance port. Nothing a 2.3.x tenant runs stops working:
  - A vendored tenant keeps its own `scripts/sync-portal-history.py`, because a sync merges vendored
    files and never deletes one. The four `_shared.py` helpers it imports are all still there.
  - The route it posts to stays served while the portal keeps `OPS_PORTAL_SYNC_TOKEN`.
  - No tenant workflow calls `verify_system.py --check-history-sync` (OTS, KYC Sentinel and
    oil-price-demo were searched).

  The row names what does change for a tenant or an operator:
  - The deprecated history route no longer stores a replay URL or key. One already stored keeps
    working, because the migration only adds the token `scope` column.
  - `/api/tenants` refuses a replay key.
  - A worker on the shared token says once that its route is deprecated.
  - A replay webhook that answers with a redirect no longer gets the replay. A 2.3.x webhook reads
    only `taskId` and `payload` and already checks the V2 signature, so the request's new `schema`
    field changes nothing for it.
  - A sync refreshes only the gates and sync workflows, never a tenant's CD files. The history and
    Phoenix-feedback steps leave the templates new tenants get, and an existing tenant drops them
    when it moves.
  - The portal needs `npm run db:migrate`.
- `pyproject.toml` and `install-ai-stack.sh` declare `2.4.0`; `docs/DESIGN.md`'s header follows
  (`scripts/test/test_version_consistency.py`).
- `CHANGELOG.md`: Unreleased becomes `[2.4.0] — 2026-10-12`, and a 2.4.x compatibility row is added.
  `docs/DESIGN.md`'s mirror shows the 2.4.x row.
- `docs/PRODUCT_BACKLOG.md`: v2.4.0 is the latest release, and C8's tenants can move.
  `docs/PRODUCT_ARCHIVE.md`: the release. The C8 design is marked done.
- **Merged by rebase**, then an annotated tag `v2.4.0` on the merged commit, pushed;
  `release.yml` publishes it.

## Pillars

- P1 applies — `.agent-rfc/designs/release-2-4-0.md` records the version and why it is a minor before any file changes.
- P2 n/a — no dependency changes; only the version strings and records.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together and requires a CHANGELOG section for the version.
- P7 n/a — no code changes in this commit.
- P8 n/a — no telemetry wiring changes.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — `.github/workflows/release.yml` signs with secrets it reads by name, unchanged; the row tells an operator the replay key is now issued in the portal, never committed.
- P13 applies — the release commit goes through the commit gate and CI like any other, with `.agent-rfc/reviews/release-2-4-0.md`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `CHANGELOG.md`'s 2.4.x row names what a tenant and an operator will notice, and the portal migration the release needs.
- P16 applies — `.github/workflows/release.yml` publishes only from a tag; a bad tag is deleted and re-cut before anyone pins it.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the version is declared in three places and one test holds them together.
- `docs-match-behaviour` — the 2.4.x row says what changes for a tenant still on the shared token and for the portal's operator.
- `two-owners-two-cadences` — tenants pin the release and operators deploy the portal; the row is their compatibility window.
