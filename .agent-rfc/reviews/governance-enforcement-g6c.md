# Review — governance enforcement, G6c (the gates CI lists, run locally)

Design: `.agent-rfc/designs/governance-enforcement.md` § G6, with the amendment written before
this code: the table is generated where the stale hand-written copy was, and the tag grammar.

**Built evidence (2026-09-17):**

- **Failing tests first.** `test_gate_steps.py` (24) was written before `gate_steps.py`; the
  module did not exist on the first run, and the four repo-level pins stayed red until the
  workflows were tagged, the table generated and the CLI wired.
- **The runner found two flaws in itself, by being run.** The first full `agentsmith gates run`
  reported four gates FAILED with exit 127 — `pip` is not on this machine's PATH, because CI's
  steps install their tooling into a fresh runner first. Two consequences, both fixed and both
  tested: dependency-install lines are dropped and named (a local run must not pip-install into
  whatever environment is active), and **exit 127 is reported as skipped, not failed** — a command
  that does not exist here is an infrastructure answer, and reporting it as a quality failure is
  how a team learns to stop reading the output (P13).
- **It runs.** 19 gates tagged here: 11 pass locally, 1 fails, 7 are skipped with a reason each.
  The failure is `mutation_check.py`'s known `tenant_scaffold` survivor, which is in the backlog —
  the tool's first real run reported the thing that is actually true.
- **Mutation checks (each reverted):** sixteen — an untagged step counted, a tag on a step that
  runs nothing, a tag with no name, the job's env dropped, an unresolvable expression run anyway,
  services ignored, `no-services` ignored, a missing tool ignored, a failure reported as a pass,
  a skip counted as a pass, `--only` ignored, install lines run anyway, a missing command counted
  as a failure, the table forgetting a gate, the table not escaping pipes, and the templates run
  as this repo's gates. Fifteen caught; the sixteenth is finding 1 below.

## Pass 1 — findings: 2

- `test-that-cannot-fail`, `provenance-and-precedence` — **finding:** the "tag with no name"
  mutation survived, and the reason was worse than the mutation. The name search walked outwards
  from the tag to the nearest `name:`, which escapes the step and finds the **job's** name — so an
  unnamed step's tag was attributed to a step called "Python scripts/runtime/examples" and then
  rejected for not existing. The test passed on the right outcome for the wrong mechanism, and a
  job whose name matched a real step's would have tagged the wrong gate. The search is bounded to
  the step's own list item now, with a test for the borrowing case specifically.
- `aggregates-name-their-scope` — **finding:** the table flattened multi-line scripts into
  `cmd-a ; cmd-b`, which reads as a command someone could paste and is not one — a heredoc became
  `python3 - <<'EOF' ; import fnmatch, re…`. And an unescaped `|` inside a command split the row
  into extra columns, so the `py_compile` row rendered as nonsense. One-line steps are quoted;
  anything longer says `(script)` and the job column names the file. Pipes are escaped, with a
  test.

## Pass 2 — findings: 0

Every lever over the final diff: the tag grammar and its two errors, the bounded name search, the
expression table, the skip reasons, the install-stripping, the table renderer, the generator mode,
the CLI, and the tags in four workflows. Considered and declined: `uses:`-based gates (ShellCheck
here) cannot be tagged, because an action is not a script this can run — the tag raises rather
than pretending, and those gates stay CI-only. Declined too: a drift step in `self-test.yml` for
the generated table — the registry's drift is pinned by a test that CI runs, and a second
mechanism for the same kind of check would be the duplication this slice exists to remove.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_steps.py (24)
Mutation-checked:          yes — sixteen, each reverted; the survivor became finding 1
Fixtures re-pinned:        yes — .agent-rfc/fixtures/knowledge_graph.json; the generated
                          gates table in docs/validation-checklist.md is itself drift-tested
Gates run locally:         `agentsmith gates run` — 11 passed, 1 failed (the known
                          tenant_scaffold mutant), 7 skipped with reasons; plus the full
                          pytest suite, ruff, and the gates-table drift check
Declared gaps:             (1) the runner executes a step's script with bash in the working
                              tree — not the runner image, not the `uses:` steps before it,
                              not a service container. CI stays the authority;
                          (2) a `uses:`-based gate cannot be tagged and stays CI-only;
                          (3) the expression table is four entries — anything else makes a
                              step skipped rather than guessed at;
                          (4) `services:` is read per job, so a step that does not need them
                              says `no-services` for itself; nothing verifies that claim.
```
