# Review — governance enforcement, G5a (one artifact per type, as code)

Design: `.agent-rfc/designs/governance-enforcement.md` § G5, with the owner's 2026-09-16
decision that G5a is the code and G5b the document migrations (OTS first, AgentSmith second).

**Built evidence (2026-09-17):**

- **Failing tests first.** `test_gate_artifacts.py` (14) and `test_gate_records_single.py` (9) were
  written before the checks; 8 of 12 and 6 of 9 failed on the first run, the rest passing for the
  wrong reason until the implementation landed.
- **Dogfooded here.** AgentSmith runs `artifacts: report` and the check lists 21 problems — five
  missing artifacts, four second-copies (`FIXES_AND_CLEANUP.md`, `OPERATIONS.md`, `SPECS.md`, the
  `ReviewFindings`/`TestCoverageReview`/`TestbedFeedback` files) and the strays under
  `docs/session-handoff/` and `docs/superpowers/`. That list IS the G5b work, generated rather than
  copied into the backlog.
- **`records: single` reuses the rules.** A `## Active change: <slug>` section is normalised — the
  fenced `governance` block becomes front matter, `### X` becomes `## X` — and the existing
  `check_design` / `check_review` read it. One set of rules, two shapes.
- **Mutation checks (each reverted):** eleven — a second file of a type not reported, every file
  counted as reference, a missing artifact ignored, report blocking, enforce reporting, the xref
  exemption ignored, xref problems never reaching the commit gate, a legacy trailer accepted in
  single mode, review entries not filtered by slug, and a section's subsections left undemoted.
  Ten caught; the eleventh is pass 1 below.

## Pass 1 — findings: 3

- `one-verdict`, `test-that-cannot-fail` — **finding:** the eleventh mutation survived.
  `cmd_artifacts` decided report-versus-enforce itself, duplicating the decision in
  `artifacts_report` that the sweep and CI use — so breaking the shared one changed nothing any
  test saw. The command now prints what `artifacts_report` returns, and two tests cover the sweep
  in each mode; the mutation is caught.
- `gate-integrity` — **finding:** the framework's `reference` globs included `docs/*.md`, which
  made the check toothless in the repo that defines it: every project record this rule exists to
  consolidate lives under `docs/`. Replaced with the shipped documentation named one by one.
  Without this, AgentSmith's own report was "no strays" while carrying four second-copies.
- `provenance-and-precedence` — **finding:** `agentsmith artifacts` read the index, so a change to
  `artifacts` in the config had no effect until it was staged — confusing for a command a person
  runs to ask "what does this repo look like now?". It reads the working tree; the sweep and
  commit-msg keep reading the index, which is what those commits will contain. Both stated in the
  docstring.

## Pass 2 — findings: 0

Every lever over the final diff: the registry and its compilation, the models' merge rule, the
artifacts check, the cross-reference rule, the single-record readers, the trailer rules, and the
docs. `scripts/test/` and `runtime/test/` 1432 passed with 10 skipped; `ruff check .`; SPECS tree
drift; `--check-hooks`; `--check-kg`; registry drift; `bash -n` and ShellCheck (0) on all hooks.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_artifacts.py (14), test_gate_records_single.py (9)
Mutation-checked:          yes — eleven, each reverted; the survivor became the one-verdict
                          finding in pass 1
Fixtures re-pinned:        yes — templates/governance.json regenerated from agent-rules.yaml
                          (the artifacts section is compiled, not hand-kept)
Gates run locally:         ruff, both suites, SPECS drift, --check-hooks, --check-kg, the
                          registry drift check, bash -n and ShellCheck, and
                          `process_gate.py artifacts` against this checkout
Declared gaps:             (1) AgentSmith and OTS run `report`; `enforce` comes with each
                              repo's G5b migration, in the same change;
                          (2) `records: single` is implemented and tested but no repo uses it
                              until G5b — deliberate, since a migration needs the reader first;
                          (3) the cross-reference rule follows the artifacts mode, so it is
                              reporting-only here until G5b;
                          (4) KYC Sentinel keeps `records: legacy` (D4, approved).
```
