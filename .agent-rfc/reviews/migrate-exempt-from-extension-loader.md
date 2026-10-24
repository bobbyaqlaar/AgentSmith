# Review — `db:migrate` cannot pass a loader the runtime image does not carry

Design: `.agent-rfc/designs/migrate-exempt-from-extension-loader.md`. Raised by
`pytest` on the full suite before pushing: `3439bd2` (the portal migrate fix)
removed the loader flag from `db:migrate` and left
`test_every_runner_invocation_passes_the_loader` red. Nothing was pushed, so
`main` was never red.

**Built evidence (2026-10-24):**

- **The premise, read from the files, not assumed.** `portal/Dockerfile` lines
  36–38: the `runner` stage copies `scripts`, `db` and `package.json`, not
  `test` — so `db:migrate` cannot name `./test/ts-extension-loader.mjs`.
  `portal/scripts/migrate.ts` imports `node:fs`, `node:url`, `node:path` and
  `pg` and nothing relative, so the loader was never load-bearing there.
  `portal/tsconfig.json` declares one alias, `@/*`, which the bare runner does
  not resolve either, so the premise check rejects that prefix too.
- **A hole found while checking the guard still works.** Deleting the loader
  from the FIRST link of `scripts.test` left the file **green**: the sweep
  tested each script as one string, and the other nineteen links still mentioned
  the flag. `_shell_invocations()` splits on `&&`/`||`/`;`, so the unit of the
  assertion is now the unit of the defect — 29 assertions over
  `portal/package.json` where there were 2.
- **Ten mutants, all caught** (`scripts/test/test_ts_runner_invocations.py`,
  `portal/package.json`, `portal/scripts/migrate.ts`; each reverted, working
  tree verified clean after each): five import forms added to `migrate.ts`;
  loader dropped from the first and from the last chain link; `db:migrate`
  renamed; `_shell_invocations` not splitting; `_specifiers` → `[]`;
  `_alias_prefixes` → `set()`; entry point dropped from the `where` label;
  `_needs_resolution` losing each half in turn; `_missing_loader` → `False`.
  Three of those **survived** before the fixes they prompted — recorded per pass
  below.
- `ruff check` clean, `python3 -m py_compile` clean, 8 tests pass (5 before).

## Pass 1 — findings: 3

- `every-line-earns-its-place` — `_alias_prefixes` bound `paths` to the whole
  tsconfig and then to `compilerOptions.paths` one line later. Renamed the first
  to `tsconfig`.
- `test-that-cannot-fail` — nothing pinned that `_invocations()` splits a chain,
  which **is** the fix: a sweep that stopped splitting would report one entry for
  `scripts.test` and keep passing while nineteen call sites went unchecked.
  `test_the_sweep_finds_the_known_invocations` now counts the sweep's entries for
  `scripts.test` against `script.count(RUNNER)` — against the script text, not a
  number written in the test that would need editing per portal suite added.
- `test-that-cannot-fail` — the premise loop computed `offenders` from
  `_specifiers(...)` with no check that the parse found anything; a broken regex
  would make it examine nothing and pass. Added an explicit emptiness assertion
  naming both causes.

## Pass 2 — findings: 2

- `test-the-contract` — the emptiness guard is not enough: if only the
  dynamic-import alternative of `_IMPORT_SPECIFIER` broke, `migrate.ts`'s four
  static imports would still parse, the guard would pass, and
  `await import("./x")` would walk through. Added `SPECIFIER_SAMPLE` /
  `EXPECTED_SPECIFIERS` and `test_the_specifier_sweep_recognises_every_import_form`,
  which pins ten forms and records the one known false positive (a commented-out
  import — the same limitation `EXEMPT` already documents, and harmless because
  it errs toward failing).
- `aggregates-name-their-scope` — `where` is a lookup key, not a caption: the
  premise test indexes exemptions by it. Two invocations sharing one label would
  be collapsed by that dict and only one checked, silently. Added a duplicate-label
  assertion, deriving `where` from a `labels` list so the tree is swept once.

## Pass 3 — findings: 1

- `guards-must-be-able-to-fail` — the mutant that deleted the alias half of the
  offender filter **passed all six tests**: nothing in the repository imports
  anything aliased, so that branch was unreachable and therefore not a guard.
  Extracted `_needs_resolution(specifier, aliases)` and added
  `test_what_counts_as_needing_resolution`, which supplies the input: four
  specifiers that need resolution (relative, parent-relative, absolute, aliased)
  and five that do not (`pg`, `node:fs`, `node:path`, `next/server`,
  `@opentelemetry/api` — the last to keep a scoped package from being read as an
  alias). Both halves of the predicate now fail when deleted.

## Pass 4 — findings: 1

- `failure-mode-visibility` — `assert checked == ["portal/scripts/migrate.ts"]`
  carried no message, so a second exemption would fail with a bare list and no
  statement of what the reader must confirm. Message added, and the comment says
  why the list is written out rather than counted.

## Pass 5 — findings: 1

- `one-verdict` — `test_the_sweep_finds_the_known_invocations` called
  `_invocations()` twice, once for a set and once for a list, sweeping the tree
  twice for the same data. One call, `where` derived from `labels`.

## Pass 6 — findings: 1

- `gate-integrity` — replacing the loader rule's condition with `False` left all
  seven tests green. It had to: when the test passes, the tree it scanned was
  clean, so the rule's own correctness was never asserted — only my hand-run
  mutation of `portal/package.json` showed it. Extracted `_missing_loader(where,
  text)` and added `test_the_loader_rule_reports_a_missing_flag`, a positive
  control over two synthetic invocations plus each exemption. The mutant now
  fails.

## Pass 7 — findings: 0

- `declared-vs-enforced` — every constant added is read by a test:
  `EXEMPT_INVOCATIONS` by the loader rule and the premise test (which also
  rejects a stale entry), `EXPECTED_SPECIFIERS` by the form test,
  `_alias_prefixes()` by the predicate test.
- `environment-parity` — nothing added reads the environment, a clock, a network
  or `git` state. `_candidate_files()`'s `git ls-files --cached --others` is
  untouched, so the CI-vs-local parity its docstring records still holds.
- `single-source-of-truth` — the `where` string is built in exactly one place
  (`_invocations`) and consumed by the two rules; the exemption and the premise
  test agree by construction because both look the entry point up through it.
- `no-redundant-artifacts` — `portal/test/runtimeImageScripts.test.ts` and this
  sweep now check opposite directions of the same fact (a script must not name a
  file the image lacks; an invocation must pass the loader unless it has nothing
  to resolve). Neither is removable and neither duplicates the other.
- Considered and declined: resolving the import graph transitively. The entry
  point is the only edge out, so a one-level check is complete, and a transitive
  walk would need a module resolver in a test file.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — one `where` builder, one predicate per rule
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked — six of seven passes were this group
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; reads two
                                          tracked files and executes nothing

Tests added/updated:      scripts/test/test_ts_runner_invocations.py — 5 tests to 8:
                          test_the_loader_rule_reports_a_missing_flag,
                          test_what_counts_as_needing_resolution,
                          test_the_specifier_sweep_recognises_every_import_form,
                          test_the_exempt_invocations_import_nothing_needing_resolution;
                          test_the_sweep_finds_the_known_invocations extended
Mutation-checked:         by hand, 10 mutants, all caught — curated mutation_check.py
                          mutates shipped code, and this slice changes only a test
Fixtures re-pinned:       .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:5f754a769ac4
Gates run locally:        pytest (full suite, 2419 tests), ruff, py_compile,
                          process gate (design + review), artifacts, gate kg check
Declared gaps:            none
```
