---
status: active
scope:
  - runtime/test/test_cli.py
---
# The source-checkout marker is tested wherever the tests run

## Problem

`scripts/mutation_check.py` reports one survivor on a developer machine and none in CI:
`tenant_scaffold` — "the source-checkout marker leaks into the tenant's declared version". The
mutant deletes the line in `runtime/cli.py` that strips `+src` from the version a scaffolded
`tenant.yaml` declares.

The code is right. The tests only look right where they happen to run:

- `framework_version()` prefers the installed package's metadata and only falls back to the
  checkout's `pyproject.toml` (which is what adds `+src`). In CI nothing is installed, so the
  version is `1.3.0+src`, the strip has work to do, and the mutant dies. On a machine where
  AgentSmith is installed — the owner's — the version is `1.3.0`, the strip is a no-op, and
  deleting it changes nothing a test can see.
- `test_the_declared_version_carries_no_source_marker` asserts `"+src" not in declared`, which
  holds trivially when there was never a marker to strip.
- `test_the_scaffold_declares_the_installed_version` computes its expected value by repeating the
  strip, so it agrees with whatever the code does.

A test whose verdict depends on what is installed on the machine running it is a test of the
machine. The mutation gate's "12 passed, 1 failed" has read that way locally since 2026-09-16.

## Approach

Make the test put the marker there itself. `test_the_declared_version_carries_no_source_marker`
sets `runtime.version.framework_version` to return `1.3.0+src` and asserts the declared version
is exactly `1.3.0` — the equality, not the absence, so a strip that removed too much fails as
well as one that removed nothing. `_default_framework_version` imports `framework_version` at
call time, so the patch reaches it.

A second case pins the other branch: a version with no marker is written unchanged.

No runtime code changes. The mutation entry in `scripts/mutation_check.py` already names this
line and stays as it is — it was right; the test under it was not.

## Pillars

- P1 applies — this note precedes the change: `.agent-rfc/designs/version-marker-test.md`.
- P2 n/a — no dependency added or changed.
- P3 n/a — a test changes; no runtime path is added.
- P4 applies — the change IS the test: `runtime/test/test_cli.py`, confirmed by re-running the surviving mutant in `scripts/mutation_check.py`.
- P7 n/a — no new production code.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model calls.
- P11 n/a — no untrusted input.
- P12 n/a — no credentials.
- P13 applies — a gate that read green in CI and red locally was reporting the environment; after this, `agentsmith gates run` means the same thing on both.
- P14 applies — the expected value is a literal the test sets, not a recomputation of the code under test: `test_the_declared_version_carries_no_source_marker`.
- P15 applies — "the mutant survives here but not in CI" was an ambiguous signal; the cause is named in this note and pinned by `test_a_released_version_is_declared_unchanged` and its sibling.
- P16 n/a — no failure path added.

## Deviations

none

## Dependencies

None added.

## Levers

- `environment-parity` — the test's verdict no longer depends on whether AgentSmith is installed where it runs.
- `test-that-cannot-fail` — `"+src" not in declared` could not fail where no marker was ever produced.
- `test-the-contract` — the assertion is the value the tenant receives, a literal the test chose, not a recomputation of the strip.
- `gate-integrity` — the fix is proven by the surviving mutant dying on this machine, and the mutation gate reads the same locally and in CI.
