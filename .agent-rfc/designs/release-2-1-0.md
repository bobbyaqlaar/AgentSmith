---
status: done
scope:
  - pyproject.toml
  - install-ai-stack.sh
---
# Release 2.1.0

## Problem

`main` carries everything since v2.0.0 (2026-09-19) under `CHANGELOG.md` › Unreleased, and the
tenants cannot use the part they are waiting for. The governance contracts C1–C5 are built and
merged, and every tenant step behind them needs a tag: the gates workflow's setup step is
`bobbyaqlaar/AgentSmith/.github/actions/setup-agentsmith@<release>`, which does not exist at
v2.0.0; KYC Sentinel's pin and OTS's move onto the contracts both name a release; and the
telemetry catalogue already dates `governance.telemetry.contract` to 2.1.0.

The owner asked for the release on 2026-10-05; the programme has named it v2.1.0 since C1.

## Approach

- **2.1.0, a MINOR.** Every heading under Unreleased was read. The contracts are additive: a tenant
  meets each one only when it syncs or adopts, contracts 1 and 2 stay published and served, and
  `@framework/` paths are still read. Nothing a 2.0.0 tenant runs today stops working on upgrade.
- `pyproject.toml` and `install-ai-stack.sh` declare `2.1.0`; `docs/DESIGN.md`'s header follows,
  as `scripts/test/test_version_consistency.py` requires.
- `CHANGELOG.md`: Unreleased becomes `[2.1.0] — 2026-10-05` with a new, empty Unreleased above it,
  and a `2.1.x` compatibility row that names what a tenant **will notice** though nothing breaks:
  - a machine committing to a tenant that declares gate contract 3, or names `"provider"`
    documents, needs this release installed — an older one refuses, closed;
  - a sync rewrites a tenant's rule files (pillar 8's new wording; renders no longer read the
    environment) in the same commit that adds the gates workflow's new rules check, which from
    then on holds them to what the declared rules provider renders;
  - a sync gives a tenant armed before the sweep existed (KYC Sentinel, OTS) the gate's `pre-commit`
    and `pre-push`, so from then on a push is refused while a commit that skipped the gate is
    unrepaired — 2.0.0's sweep, newly reaching them.
  `docs/DESIGN.md` mirrors the current row.
- `docs/PRODUCT_BACKLOG.md`: v2.1.0 is the latest release; the contracts' tenant steps are
  unblocked. `docs/PRODUCT_ARCHIVE.md`: the release.
- **Through a pull request** — `main` has refused direct pushes, its owner's included, since
  2026-09-29 — and then an annotated tag
  `v2.1.0` on the merged commit, pushed; `release.yml` builds the artifacts from it, and the setup
  action exists at that ref from then on.

## Pillars

- P1 applies — `.agent-rfc/designs/release-2-1-0.md` records the version and the reading of Unreleased before any file changes.
- P2 n/a — no dependency changes; only the version strings.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together and requires a CHANGELOG section for the version; the Wire Contract table's 2.1.0 row is pinned to the telemetry catalogue by `scripts/test/test_telemetry_contract.py`.
- P7 n/a — no code changes.
- P8 n/a — no telemetry wiring changes; the 2.1.0 Wire Contract row documents one already merged.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — `.github/workflows/release.yml` signs with secrets it reads by name, unchanged.
- P13 applies — the release commit goes through the commit gate and CI like any other, with `.agent-rfc/reviews/release-2-1-0.md`.
- P14 n/a — no fixture or baseline changes.
- P15 applies — `CHANGELOG.md`'s 2.1.x row says plainly what a tenant will notice and that nothing breaks.
- P16 applies — `.github/workflows/release.yml` publishes only from a tag; a bad tag is deleted and re-cut before anyone pins it.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the version is declared in three places and one test holds them together.
- `docs-match-behaviour` — the compatibility row describes what a 2.0.0 tenant actually meets.
- `run-the-gates-ci-lists` — the portal's suite runs before the push this time, not after (2.0.0's pass 3).
