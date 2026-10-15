---
status: done
scope:
  - scripts/mutation_check.py
  - scripts/test/test_mutation_check_scope.py
  - scripts/gate_steps.py
  - scripts/test/test_gate_steps.py
  - scripts/test/test_framework_python_env.py
  - docs/validation-checklist.md
  - .github/workflows/self-test.yml
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Curated mutations: only what a pull request can affect, in parallel

## Problem

Self-Test's "Python scripts/runtime/examples" job takes about 42 minutes on every pull request.
Measured on #54's run (38470842052):
- 39 minutes of it is one step, `mutation_check.py`: 31 suites and 224 mutations, one after
  another;
- the rest of the job is about 3 minutes.

Only `tenant_adopt` declares `watch` (`mutation-ci-scope`, owner 2026-09-19), so the other 30
suites run on every pull request. #55 changed one requirements line and a test, and #57 only
version strings and docs, yet each waited the full run. The heaviest suites:

| Suite | Minutes |
|---|---|
| `framework_sync` | 10.0 |
| `tenant_adopt` | 5.5 |
| `security_contract` | 4.7 |
| `evals_contract` | 2.8 |

The owner asked on 2026-10-14 whether this could be optimised, and approved the approach below,
to be built after the 3.0.0 release. It supersedes the 2026-09-19 decision that only
`tenant_adopt` is narrowed.

## Approach

- **Every suite is narrowed on a pull request, by files it already names.** A suite's triggers
  are:
  - its `watch` globs (`tenant_adopt` keeps its list);
  - the file each of its mutations edits;
  - its test files;
  - the repository modules those test files import directly, read from their syntax tree: a
    sibling test helper such as `test_process_gate`, a script such as `process_gate`, or a
    `runtime.*` module;
  - a set shared by every suite, whose change can alter how any test runs:
    `scripts/mutation_check.py`, both `conftest.py`, `scripts/_shared.py`, the requirements files
    and lock, `pytest.ini`, `.python-version` and `self-test.yml`. Not `pyproject.toml`: pytest
    reads `pytest.ini` here, and the rest of that file is packaging and lint.

  `--changed-since` skips a suite none of whose triggers changed, named as before. When the base
  is unknown it still runs everything.
- **On `main`, everything runs.** A push to `main` and a weekly schedule run every suite without
  `--changed-since`. A gap in the narrowing then surfaces at the next merge, not never.
  `workflow_dispatch` runs everything too.
- **In parallel, in its own job.** The mutation step moves into `mutations`, a four-way matrix,
  "Curated mutations (shard N/4)". `--shard N/4` takes the selected suites and deals them into
  four bins, heaviest first. The weight is mutations × test files, and the result is the same on
  every shard, because each computes it from the same selection. A shard with no suites passes
  and says so. Separate jobs run on separate runners, so the in-place edits the runner makes
  never meet.
- **The required check keeps its meaning.** `main` requires "Python scripts/runtime/examples" by
  name (checked 2026-10-14), not a new job. That job now `needs: mutations`, runs
  `if: !cancelled()`, and its first step fails unless every shard succeeded. A failed, cancelled
  or skipped shard fails the required check. No branch-protection change, and no weaker gate. The
  job's other steps start after the shards, so the wall time is the slowest shard plus about 3
  minutes.
- **The held-back mutation lands.** A `scratch_build` suite runs `test_scratch_tenants.py` against
  the Python template's bare-`pytest` mutation (`vendoring-retired` pass 16). Narrowed like every
  suite, it runs only when its files change.
- **Expected:** a pull request like #55 or #57 runs a few suites, in minutes. A full run is about
  a quarter of 39 minutes per shard, about 12 minutes wall time with the job's own steps.

## Pillars

- P1 applies — the owner approved this approach on 2026-10-14, recorded in `.agent-rfc/designs/mutation-ci-fast.md`, superseding `.agent-rfc/designs/mutation-ci-scope.md`'s single narrowed suite.
- P2 n/a — no dependency added; `ast`, `fnmatch` and `subprocess` are the standard library.
- P3 n/a — a developer tool with no service path.
- P4 applies — tests first in `scripts/test/test_mutation_check_scope.py`: triggers derived from a suite's own files and its tests' imports, the shared set, a shard plan that covers every selected suite exactly once, and the workflow's wiring.
- P7 n/a — no model built from external data; `Suite` stays a frozen dataclass of constants.
- P8 n/a — no telemetry.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 n/a — the inputs are git's changed paths and this repository's own test files.
- P12 n/a — no secret is read; the workflow passes commit SHAs only.
- P13 applies — narrowing a required gate: `main` and the weekly run are never narrowed, an unknown base runs everything, and the required check fails unless every shard succeeded (`.github/workflows/self-test.yml`, `test_the_required_check_fails_unless_every_shard_passed`).
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned with this change.
- P15 applies — a skipped suite is named with its reason, each shard prints the suites it was dealt, and an empty shard says it had none (`scripts/mutation_check.py`).
- P16 applies — a shard that fails is re-run alone from the Actions page; locally, `mutation_check.py` with no flags still runs every suite in one process.

## Deviations

none

## Dependencies

None added.

## Levers

- `gate-integrity` — the narrowing applies to pull requests only; the required check still fails on any failed shard.
- `declared-vs-enforced` — the triggers come from the files a suite already names, so a new mutation's file is a trigger without anyone remembering to add it.
- `failure-mode-visibility` — every skip and every shard's share is printed; "all caught" never counts a suite that did not run.
- `ambiguous-signals` — a skipped or cancelled shard is not a pass.
- `test-the-contract` — the selection is tested against real git history, and the workflow's wiring is read from the file CI runs.
