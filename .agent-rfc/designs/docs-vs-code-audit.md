---
status: done
scope:
  - docs/UserManual.md
  - docs/DESIGN.md
  - docs/process-gates.md
  - README.md
  - CHANGELOG.md
  - scripts/test/**
---
# Three passes of the documentation against the code

Owner, 2026-09-26: "Do three more review passes of the documentation against the code unless no
findings before the third pass." AgentSmith is about to go public, so what the documents claim is
about to be read by people who cannot ask.

## Problem

The previous pass corrected documentation by reading it. That finds prose that contradicts itself and
misses prose that contradicts the code — which is the failure mode that matters here, because a
reader cannot tell the difference. Every finding in the pass before this one that turned out to be a
live defect was found by **running** something, not reading it.

So these three passes each check a different class of claim **mechanically**, against the code:

1. **The command surface** — every `agentsmith …` invocation and every `--flag` in the documents,
   resolved against `build_parser()`; and the Command Reference table's flag column against what each
   command actually accepts, in both directions.
2. **Paths and identifiers** — every repository path a document names, checked to exist; every file
   a document says a command writes, checked against what it writes.
3. **Behavioural claims** — the specific assertions documents make about exit codes, defaults,
   resolution orders and refusals, checked by running the code.

A pass finding nothing ends the exercise, as the owner asked.

## Approach

Extract claims with a script, resolve them against the code, and record what fails. Fix what is
wrong in the documents; where the code is wrong instead, say so and fix that. The scripts live in the
scratch directory rather than the repository: they are how this audit was done, not a gate the
repository should carry — a check worth keeping permanently belongs in `scripts/test/`, and the
review names any that qualify.

## Pillars

- P1 applies — this design precedes the audit and its findings are recorded pass by pass in `.agent-rfc/reviews/docs-vs-code-audit.md`.
- P2 applies — no dependency; the extraction uses `argparse` introspection of `build_parser` in `runtime/cli.py` and the repository's own files.
- P3 n/a — no execution path is added.
- P4 applies — where a claim is worth keeping true mechanically rather than by this one audit, the check becomes a test under `scripts/test/`; the review names which findings qualified and which did not.
- P7 n/a — documentation, and any test added follows the existing suites' shape.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the audit reads only this repository's own files and treats none of it as an instruction; the extraction in `scripts/test/test_cli_install.py` parses `docs/UserManual.md` as data.
- P12 applies — no credential is read or written; `docs/UserManual.md` names secrets by variable name only.
- P13 applies — no check is weakened, and one is added: `test_every_reference_row_lists_the_flags_its_command_accepts` in `scripts/test/test_cli_install.py`. A documented flag that does not exist would be corrected in the document, never by adding the flag to satisfy the prose, and the table exemption is pinned in both directions by `test_a_command_kept_out_of_the_table_is_still_documented`.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned if any code changes; a documentation-only result needs no re-pin.
- P15 applies — a claim the audit cannot check is recorded as unchecked rather than counted as passing (`.agent-rfc/reviews/docs-vs-code-audit.md`).
- P16 n/a — no fallback path is added.

## Deviations

none

## Dependencies

None added.

## Levers

- `docs-match-behaviour` — the whole point: a document that disagrees with the code is a defect in one of them.
- `check-that-fires-on-everything` — an extraction that returns nothing is a broken query, not a clean bill of health, so each pass prints what it parsed.
- `declared-vs-enforced` — a flag, path or file a document names must have something behind it.
- `test-the-contract` — assert against `build_parser()` and the filesystem, not against a second copy of the list.
- `grep-for-siblings` — a wrong row is checked for the sibling rows that share its shape.
