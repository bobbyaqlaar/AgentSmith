---
status: done
scope:
  - scripts/process_gate.py
  - scripts/test/**
  - docs/process-gates.md
  - docs/DESIGN.md
  - docs/UserManual.md
  - CHANGELOG.md
  - .agent-rfc/fixtures/knowledge_graph.json
---
# The four things the audits left open

Owner, 2026-09-26: "Resolve the findings shown in the Honest notes." Those notes closed
`.agent-rfc/reviews/docs-vs-code-audit-2.md`; two of the four turn out to be defects in this
repository rather than in how I ran the audit.

## Problem

1. **Two planned passes never ran** — config keys and stated counts — stopped by the owner's rule.
   Config keys are untested ground: nothing checks that `.agenticframework/process-gates.json`'s keys
   are the ones the gate reads, or that a documented key exists.

2. **The env-var documentation gate scans no shell, and misses five Python directories.**
   `_source_files()` in `scripts/test/test_env_var_documentation.py` globs `runtime/*.py`,
   `scripts/*.py`, `runtime/workflows/*.py` and `portal/*.py` — so `install-ai-stack.sh`, `hooks/*`,
   `.githooks/*` and the on-prem shell scripts are outside every gate this repository has, as are
   `runtime/machine/`, `scripts/security/`, `scripts/security/runners/` and `examples/`. That is the
   same defect its own docstring records for the portal — *"a glob that reaches for a directory
   written in another language is not coverage"* — repeated one language further along. My throwaway
   detector was groping at this and reported 65 false positives because it could not tell a shell
   **input** from a **local**; that distinction is the work, and it belongs in the test.

3. **`_PASS` makes an unparseable heading invisible, and then blames the numbering.**
   `scripts/process_gate.py:338` anchors on `\s*$`, so `## Pass 4 — findings: 1 (CI, 2026-09-24)`
   matches nothing. `check_review` then sees passes `[1, 2, 3, 5]` and reports *"passes are numbered
   [1, 2, 3, 5], expected 1..4 in order"* — the symptom of a gap, for a heading that simply did not
   parse. One message for two causes (`ambiguous-signals`), and it sent me to the numbers three times
   in one session rather than to the syntax. A gate whose own author misreads it three times is
   reporting the wrong thing.

4. **The pillar tests pin presence, not correctness.** `### Pillar 15 — Anything At All` satisfies
   `test_every_pillar_the_gate_knows_has_a_section_in_the_design_doc`.

## Approach

- **A heading that was meant to be a pass heading is named as one.** `check_review` collects lines
  matching a loose `^##\s*Pass\b` and reports any the strict form did not capture, with the line, so
  "did not parse" and "numbered wrong" stop sharing a message. The strict form is unchanged: the
  point is the diagnosis, not a laxer rule.
- **The env sweep reaches shell, and every Python directory.** Python globs become recursive over the
  directories that hold shipped code; shell files are swept with a rule that separates inputs from
  locals — a name is an input when it is read before or without ever being assigned in that file, or
  read with a `${VAR:-default}`; a name assigned in the file and then used is a local. The dead
  `portal/*.py` glob goes, since `test_the_portal_sweep_actually_finds_portal_files` covers the
  TypeScript side and the Python one matches nothing by construction.
- **The pillar sections are checked for the right name**, not just a heading: `### Pillar N — <name>`
  must carry the registry's name for N.
- **The two passes run**, and anything they find is fixed here.

## Pillars

- P1 applies — this design precedes the code and names the four notes it closes, recorded in `.agent-rfc/reviews/audit-notes-resolved.md`.
- P2 applies — no dependency; the new sweep uses `git ls-files` and `re`, as the test already does.
- P3 n/a — no new execution path.
- P4 applies — each change is a test or is asserted by one: the diagnosis by `test_a_heading_that_does_not_parse_is_named_not_counted_as_a_gap`, the sweep by `test_the_shell_sweep_finds_shell_files` and `test_a_shell_input_is_told_from_a_local`, the pillar names by `test_a_pillar_section_carries_the_registry_name`.
- P7 applies — no new typed boundary; `check_review` keeps its `List[str]` return in `scripts/process_gate.py`.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the sweep reads this repository's own tracked files as data; `scripts/test/test_env_var_documentation.py` treats every match as a name to look up, never as something to execute.
- P12 applies — the sweep reads variable NAMES and never a value, which is the whole point of the control it guards (`scripts/test/test_env_var_documentation.py`).
- P13 applies — nothing is weakened and two checks get stronger: `_PASS` keeps its strict form and gains a diagnosis, and the env sweep grows rather than shrinks. Widening it may surface variables documented nowhere, which are fixed by documenting them, never by narrowing the glob.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned, since `scripts/process_gate.py` changes.
- P15 applies — its own subject: "this heading did not parse" and "the passes are numbered wrong" become different messages in `scripts/process_gate.py`.
- P16 applies — when the loose pass-heading scan finds nothing, `check_review` falls through to exactly the behaviour it has today, so a review with no pass headings at all still reports "records no passes".

## Deviations

none

## Dependencies

None added.

## Levers

- `ambiguous-signals` — one message for "unparseable" and "misnumbered" is the defect.
- `check-that-fires-on-everything` — a sweep that reaches no shell file is not coverage; the test asserts it finds some.
- `grep-for-siblings` — the portal glob defect, found once, is repeated for shell and for five Python directories.
- `declared-vs-enforced` — a config key nothing reads, and a documented key that does not exist.
- `test-the-contract` — the pillar sections are checked against the registry's names, not against their own presence.
