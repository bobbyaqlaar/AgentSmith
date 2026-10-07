---
status: done
scope:
  - pyproject.toml
  - install-ai-stack.sh
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Release 2.2.0

## Problem

`main` carries the evals contract (C6), the adopted scratch tenant and the faster mutation runner
under `CHANGELOG.md` › Unreleased, and the tenants cannot use the part they are waiting for: KYC
Sentinel's four `run-evals.py` steps move to `process-gate evals run` through the setup step
`bobbyaqlaar/AgentSmith/.github/actions/setup-agentsmith@<release>`, which serves no `evals` command
at v2.1.0.

The owner asked for the release on 2026-10-07.

## Approach

- **2.2.0, a MINOR.** Every heading under Unreleased was read. The evals contract is additive: a
  tenant meets it only when it syncs or adopts (a `providers.json` `evals` port) and when its own
  CI calls `process-gate evals run`; `run-evals.py` and the eval workflow templates are unchanged.
  The scratch tenant and the mutation runner are AgentSmith's own CI. Nothing a 2.1.0 tenant runs
  stops working on upgrade.
- **Measured against a 2.1.0 install on 2026-10-07**, with a tenant declaring both new keys: the
  `evals` port in `providers.json` is accepted, and the rules check answers as before; but
  `extends.evals` in `process-gates.json` is refused — the gate reports the config broken and denies
  every edit but to the config. And `process-gate evals run` asked of a 2.1.0 `agentsmith` fails the
  step: the old CLI has no `evals run` (exit 2), which the launcher reports as a provider older than
  the contract. Both closed and loud, as intended — what a tenant will notice.
- `pyproject.toml` and `install-ai-stack.sh` declare `2.2.0`; `docs/DESIGN.md`'s header follows,
  as `scripts/test/test_version_consistency.py` requires.
- `CHANGELOG.md`: Unreleased becomes `[2.2.0] — 2026-10-07` with a new, empty Unreleased above it,
  and a `2.2.x` compatibility row that names what a tenant **will notice** though nothing breaks:
  - a sync adds the `evals` port to a `providers.json` the framework wrote;
  - a tenant that declares its own bars (`extends.evals`) needs 2.2.0 on every machine that edits or
    commits there — an older install refuses the config, closed;
  - `process-gate evals run` needs a 2.2.0 provider — locally and at the CI setup step's pin.
  `docs/DESIGN.md` mirrors the current row.
- `docs/PRODUCT_BACKLOG.md`: v2.2.0 is the latest release; C6's tenant steps are unblocked.
  `docs/PRODUCT_ARCHIVE.md`: the release.
- **Through a pull request**, then an annotated tag `v2.2.0` on the merged commit, pushed;
  `release.yml` builds the artifacts from it, and the setup action serves `evals` at that ref.

## Pillars

- P1 applies — `.agent-rfc/designs/release-2-2-0.md` records the version, the reading of Unreleased and the 2.1.0 measurement before any file changes.
- P2 n/a — no dependency changes; only the version strings.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_version_consistency.py` pins the installer, the package and the design header together and requires a CHANGELOG section for the version.
- P7 n/a — no code changes.
- P8 n/a — no telemetry wiring changes; no span attribute added since 2.1.0.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — nothing reads untrusted content.
- P12 applies — `.github/workflows/release.yml` signs with secrets it reads by name, unchanged.
- P13 applies — the release commit goes through the commit gate and CI like any other, with `.agent-rfc/reviews/release-2-2-0.md`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node, as every design adds one; the self-test's freshness check requires it.
- P15 applies — `CHANGELOG.md`'s 2.2.x row says plainly what a tenant will notice, measured against a 2.1.0 install, and that nothing breaks.
- P16 applies — `.github/workflows/release.yml` publishes only from a tag; a bad tag is deleted and re-cut before anyone pins it.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the version is declared in three places and one test holds them together.
- `docs-match-behaviour` — the compatibility row describes what a 2.1.0 install actually does with the new keys, measured.
- `run-the-gates-ci-lists` — the full suite and the self-test's gates run on the staged tree before the push.
