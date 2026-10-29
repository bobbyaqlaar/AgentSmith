# Review — a scaffolded tenant's graph knows the records the scaffold wrote

Design: `.agent-rfc/designs/scaffold-graph-knows-its-own-records.md`. Raised by
`kg-check-sees-tracked-guardrails` turning
`test_kg_check_fails_a_stale_graph_and_passes_once_regenerated` red: a freshly
scaffolded, committed tenant stopped passing `kg check`. Both the gate and that
assertion were right; the scaffold between them was wrong.

**Built evidence (2026-10-30):**

- **Bisected rather than guessed.** The failure had two causes and the first was
  not code:

  | cause | evidence | remedy |
  |---|---|---|
  | stale machine install | `~/.agent-framework/scripts/map_codebase.py` hashed to commit `7854bd1`, predating `6fafbd0`; no `_mapped()`, no `--exclude-standard` | re-ran `install-ai-stack.sh` from this checkout — absolute `source_file` paths went 17 → 0 |
  | the mapper ran before the records | `init_tenant` calls `_provision_governance` (which mapped) before `write_scaffold_records` (which writes the rfc docs) | this slice |

- **Line order was not call order**, which is why reading the file misleads: the
  mapper sat at `runtime/cli.py:746` and the records at `:436`, but 746 is
  inside `_provision_governance`, called first. Established with an AST lookup
  of each line's enclosing function rather than by eye.
- **The measurement that proved the second cause:** on one uncommitted scaffold,
  the init-time graph held **17** guardrails and no `rfc:` node; the same
  installed mapper, same `--quiet`, same `cwd`, run again a moment later held
  **19**, including `rfc:001-scaffold.md` and `rfc:designs/scaffold.md`. Nothing
  on disk changed between the two runs except the graph.
- **A fresh scaffold now, end to end:** 19 guardrails, 0 absolute, both rfc
  nodes present, and on its first commit
  `✅ … compared 0 tracked file(s), 19 guardrail(s) and 0 edge(s)`.
  The `0 tracked file(s)` is correct, not a second bug — checked: the
  `python-fastapi` scaffold writes no source files at all, so there is no
  `CodebaseFile` node to compare.
- **Three mutants, all caught:**

  | mutant | tests that failed |
  |---|---|
  | mapper never runs | `kg_check_fails_a_stale_graph…`, `scaffolded_graph_knows_the_scaffold_records` |
  | scaffold records never written | `scaffolded_graph_knows_the_scaffold_records` (its `assert records` guard) |
  | **mapper moved back before the records** | `kg_check_fails_a_stale_graph…`, `scaffolded_graph_knows_the_scaffold_records` |

  The third is the one that matters: it restores the exact defect and the tests
  refuse it.
- `ruff` clean, `py_compile` clean, 16 tests pass in
  `scripts/test/test_vendoring_retired.py` (14 before).

## Pass 1 — findings: 4

- `no-copy-paste` — splitting the old two-script loop left the
  `! … did not complete:` report written twice, once per tool. A split copy of
  an error message is how two messages stop agreeing. One `_run_tool(script,
  root, *args)` serves both.
- house style — I had used `if (gen := …).is_file():`. `grep -c ":="` over
  `runtime/cli.py` returned **1**, my own: the file does not use the walrus.
  Plain call instead.
- `one-verdict` — `framework = _framework_dir()` is already bound at the top of
  `init_tenant`, and both my new call and the pre-existing
  `seed_tenant_data(root, _framework_dir())` re-derived it. Both now use
  `framework`; the second was not mine but is the same line and the same
  reasoning.
- `no-redundant-artifacts` — with both tool runs behind `_run_tool`,
  `_provision_governance`'s function-local `import subprocess as sp` became
  dead. `ruff` caught it (`F401`) and an AST check confirmed the function
  references `sp` nowhere before removing it.

## Pass 2 — findings: 0

- `gate-integrity` — the two new tests assert the scaffold's **graph contents**,
  not `kg check`'s verdict, so the gate change in the previous slice cannot make
  them pass. Verified by reading them: neither invokes the gate.
- `test-that-cannot-fail` — `test_the_scaffolded_graph_knows_the_scaffold_records`
  derives its expectation from `scaffolded.glob(".agent-rfc/*.md")` and would
  pass over an empty list, so it asserts `records` is non-empty first. The
  "scaffold records never written" mutant proves that guard fires.
- `when-the-fallback-fails` — `_run_tool` returns silently when the script is
  absent and prints without raising when it fails, which is the behaviour the
  loop it replaced had. A scaffold is still completed, and the tenant's own
  `kg build` fixes a graph that did not get written.
- `ambiguous-signals` — "a graph file exists" and "the graph is current" are now
  answered in two places, and the comment in `_provision_governance` says which
  question the placeholder answers.
- `environment-parity` — the remaining environment dependence is real and
  stated: an installed mapper older than `6fafbd0` reintroduces the absolute
  paths. `test_the_scaffolded_graph_stores_repository_relative_sources` fails
  with the remedy in its message, and the CHANGELOG entry says it too, so the
  next person loses minutes rather than the hours this cost.
- Considered and declined: moving `write_scaffold_records` before
  `_provision_governance` instead. Provisioning writes
  `.agenticframework/process-gates.json`, which the records step reads to know
  what is gated, so reversing them makes the records depend on a file that does
  not exist yet.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — Pass 1 removed a duplicated error report,
                                          a dead import and two redundant _framework_dir() calls
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked — CHANGELOG entry under [Unreleased];
                                          runtime/** requires one, scripts/test/** does not
Group 5 · Intuitive UI                [x] n/a — no screen or control; `tenant init`'s stderr
                                          is the only surface and its wording is unchanged
Group 6 · Signal integrity            [x] checked — 3 mutants, including the one that restores
                                          the original ordering
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; runs an
                                          installed script against a directory the caller named

Tests added/updated:      scripts/test/test_vendoring_retired.py — 14 tests to 16:
                          test_the_scaffolded_graph_knows_the_scaffold_records and
                          test_the_scaffolded_graph_stores_repository_relative_sources,
                          both over the scaffold's graph contents rather than a verdict
Mutation-checked:         by hand, 3 mutants on the ordering and the mapper call, all caught.
                          mutation_check.py's curated suite has no entry for runtime/cli.py's
                          scaffold path — the same gap recorded for _kg_shape, and the same
                          consequence: CI will not re-run these.
Fixtures re-pinned:       .agent-rfc/fixtures/knowledge_graph.json — node ids diffed, and this
                          time `gate kg check` is a control worth having, since the previous
                          slice is what made it one
KG query:                 kg:977ff8849a0c
Gates run locally:        pytest (full suite), ruff, py_compile, agentsmith gate kg check,
                          process gate (design + review), artifacts; mypy's scope is
                          [tool.mypy] files = ["runtime"], so runtime/cli.py IS in it — not
                          installed here, so CI is the first place it runs
Declared gaps:            one, stated in the design and in the test's own failure message: an
                          installed mapper older than 6fafbd0 writes absolute source_file
                          paths, and nothing stops a machine running one. The test names the
                          remedy when it fails; it does not prevent the state.
```
