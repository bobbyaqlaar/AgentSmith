---
status: done
scope:
  - scripts/mutation_check.py
  - scripts/test/test_mutation_check_scope.py
  - .github/workflows/self-test.yml
  - .agent-rfc/fixtures/knowledge_graph.json
---
# The slow mutation suite runs when what it protects changes

## Problem

The `tenant_adopt` suite in `scripts/mutation_check.py` (18 mutations, each running four
end-to-end test files) took Self-Test's curated mutation step from about 2 minutes to 14 minutes
12 seconds (run 35450928052), on every push — including pushes that touch nothing it protects.
The repository is private, so that is Actions minutes spent on every docs commit.

Owner decision, 2026-09-19: run it only when its files change (option 1 of three offered; the
others were nightly, or leave it).

## Approach

- **A suite may declare `watch`** — globs of the files whose change could break a property it
  defends. A suite without `watch` runs on every invocation, as every suite does today. Only
  `tenant_adopt` declares one: the hooks (`.githooks/**`, `hooks/**`), the adopt and tenant code
  (`runtime/adopt.py`, `runtime/cli.py`, `runtime/architectures.py`,
  `templates/architectures.yaml`), the gate (`scripts/process_gate.py`, `scripts/gate_*.py`),
  the gates workflow template, its four test files, and `scripts/mutation_check.py` itself, so an
  edit to the catalogue runs it.
- **`--changed-since REF`** narrows a run to suites whose `watch` matches a file changed between
  `REF` and `HEAD`. A skipped suite is named, with the reason, and the closing line counts it —
  a skip is never silent.
- **When it cannot tell, it runs everything.** An empty `REF`, the all-zeros SHA GitHub sends for
  a new branch, or a commit this clone does not have (a force-push, a shallow checkout) means the
  changed files are unknown, and unknown is treated as "everything changed", said in the output.
- **Without the flag nothing changes**: a local `python3 scripts/mutation_check.py` runs every suite.
- **Self-Test** passes the same base the process-gate job uses (the pull request's base, else
  the push's `before`), and the Python job's checkout fetches full history so that base exists.

## Pillars

- P1 applies — the owner chose this option before the code, recorded in `.agent-rfc/designs/mutation-ci-scope.md`.
- P2 n/a — no dependency added; `fnmatch` and `subprocess` are the standard library.
- P3 n/a — a developer tool with no service path.
- P4 applies — tests first in `scripts/test/test_mutation_check_scope.py`: selection by changed files, the fall-back to everything, and the named skip.
- P7 n/a — no model built from external data; `Suite` stays a frozen dataclass of constants.
- P8 n/a — no telemetry.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 n/a — the only input is git's list of changed paths in this repository.
- P12 n/a — no secret is read; the workflow passes commit SHAs only.
- P13 applies — narrowing a gate is a gate-integrity question: the default is still every suite, only a suite that declares `watch` can be skipped, and any doubt about the base runs everything (`select_suites` in `scripts/mutation_check.py`).
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned with this change.
- P15 applies — a skipped suite is printed with the reason and counted apart from the ones that ran, so "all caught" never includes a suite that did not run (`test_the_cli_names_a_skipped_suite_and_does_not_count_it_as_caught`).
- P16 applies — an unusable base falls back to running everything, and says which base it could not use (`test_a_base_the_clone_cannot_use_means_unknown`, `test_the_cli_says_why_it_ran_everything`).

## Deviations

none

## Dependencies

None added.

## Levers

- `gate-integrity` — only a suite that declares `watch` can be skipped, and doubt runs everything.
- `failure-mode-visibility` — a skip is named and counted, never folded into "all caught".
- `ambiguous-signals` — "the base is unknown" is its own answer, and it is not "nothing changed".
- `test-the-contract` — the selection is tested against real git history, not a stub.
