---
status: active
scope:
  - scripts/build_release_assets.sh
  - scripts/test/test_release_artifact_contract.py
  - scripts/mutation_check.py
  - .agent-rfc/fixtures/knowledge_graph.json
---
# The release build reports a file missing only when it is

## Problem

Tagging `v3.0.1` failed `release.yml` at the build step: "agentsmith-source.tar.gz is missing install-ai-stack.sh",
beside `printf: write error: Broken pipe`. The file was in the archive. `scripts/build_release_assets.sh` checks each name
with `printf '%s\n' "$listing" | grep -qxF "$needed"` under `set -o pipefail`. `grep -q` exits at its first match, the
`printf` still writing fails, `pipefail` makes the pipeline fail, and the check reads that as absent. It depends on timing,
so Self-Test had passed on the same commit, and no release was published.

## Approach

- **No pipe:** `grep -qxF "$needed" <<<"$listing"`, so the writer cannot be left behind.
- **A test that fails every time on the old form:** a stub `tar` lists every needed name first, followed by more than a pipe
  buffer's worth of padding, so the old form's writer is always still writing when `grep` exits. A curated mutation
  restores the pipe.

The other `pipefail` scripts that pipe into `grep -q` or `head` were read: each pipes a line or two, one write that finishes
before the reader can leave. They do not change.

## Pillars

- P1 applies — `.agent-rfc/designs/release-build-false-missing.md` records the failed run before the change.
- P2 n/a — a one-line correction; no dependency.
- P3 n/a — a build script; no traced path.
- P4 applies — `scripts/test/test_release_artifact_contract.py` fails deterministically on the old form, and `scripts/mutation_check.py` proves it.
- P7 n/a — shell; no stack-specific rule applies.
- P8 n/a — no telemetry.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 n/a — reads the archive this script just built.
- P12 n/a — no secret involved.
- P13 applies — `scripts/build_release_assets.sh` still fails closed when a name really is absent, which `scripts/test/test_release_artifact_contract.py` holds.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `scripts/build_release_assets.sh` no longer turns a broken pipe into a claim about the archive.
- P16 applies — `.github/workflows/release.yml` publishes nothing when the build fails, and its job can be re-run on the tag, as this one was.

## Deviations

none

## Dependencies

none

## Levers

- `guards-must-be-able-to-fail` — the guard failed when nothing was wrong, and a test now pins both directions.
- `failure-mode-visibility` — the message named a missing file when the cause was a pipe.
- `environment-parity` — Self-Test passed and the release failed on the same commit, by timing alone.
