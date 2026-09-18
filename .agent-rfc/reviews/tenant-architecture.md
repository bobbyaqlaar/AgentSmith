# Review — a new tenant starts from its architecture, and its first commit can go in

Design: `.agent-rfc/designs/tenant-architecture.md`. Owner decisions, 2026-09-18: `tenant init`
writes the design from the kind of application; five structural styles plus an agentic overlay;
the scaffold commit passes review only when verifiably untouched.

**Built evidence (2026-09-18):**

- **Found by rehearsing the demo, not by the tests.** A freshly `tenant init`-ed repository could
  not make its first commit, and the test named `test_a_scaffolded_tenant_can_commit_a_governed_change`
  only asserted the refusal. Renamed to what it checks
  (`test_code_committed_with_the_scaffold_and_no_design_is_refused`); the success is now tested
  through the real hooks in `scripts/test/test_scaffold_review.py`.
- **Failing tests first.** `runtime/test/test_architectures.py` (22) and
  `scripts/test/test_scaffold_review.py` (9) were written before `runtime/architectures.py` and the
  gate rule; the first run failed on the missing module.
- **The journey, end to end with the real CLI** in a throwaway repository:
  `tenant init demo-app --architecture clean --agentic` → it prints the first commit → that commit
  goes in with `ℹ️ Review: n/a: generated scaffold — 20 gated file(s) match
  .agenticframework/scaffold.json`, and `docs/DESIGN.md` carries the hexagonal layers with
  `app/…` paths and the agent layer.
- **Mutation checks (each reverted):** ten — any commit claiming the scaffold, no manifest
  accepted, an unlisted file accepted, the hash not compared, acceptance made silent, the root flag
  lost in CI, the manifest vouching for every file in the repository, the scaffold design left
  active, the agent layer always rendered, the path placeholder unresolved. Nine caught on the
  first run; the survivor is finding 3.

## Pass 1 — findings: 4

- `environment-parity` — **finding:** five `runtime/test/test_cli.py` tests crashed. This Mac's
  `~/.agent-framework` is an install from before the registry existed — it has the gate scripts
  and no `templates/governance.json` — and `_framework_dir()` prefers it to the checkout. A stale
  install now gets a warning naming the fix, and the scaffold design is skipped rather than written
  with pillars nobody can list; the manifest is still written.
- `test-that-cannot-fail` — **finding:** no test covered a file the tenant already had before
  `tenant init` ran. The manifest lists only what the run wrote, and a mutation hashing every file
  in the repository would have passed; `test_a_file_the_tenant_already_had_is_not_vouched_for`.
- `test-the-contract` — **finding:** mutation "unlisted file accepted" survived. With the check
  gone the gate crashed on a `KeyError` whose traceback happened to name the file, and the tests
  only looked for the file name. A crash is not a verdict; the tests assert the gate's own words.
- `provenance-and-precedence` — **finding:** `runtime/architectures.py` located the catalogue
  beside the package, which an installed `agentsmith-runtime` does not carry. It searches where the
  rest of `tenant init` does: `$AGENTSMITH_DIR`, the machine install, then the checkout.

## Pass 2 — findings: 0

Every lever over the final diff, the manual's tenant section, `docs/process-gates.md` and the
CHANGELOG. Considered and declined:

- Signing the manifest. There is no key a new repository could hold that an agent in the same
  repository could not also use; the limit is stated in the design and the docs instead, and the
  escape is narrowed to the root commit and made a visible note.
- Creating the style's directories. Git does not track empty directories, and placeholder files
  are code nobody reviewed; `docs/DESIGN.md` names the paths, and the first design creates them.

**Found alongside, not fixed here:** `tenant init` points git at `.githooks`, which has no
`post-checkout`, so the machine's vendoring hook never runs in a `tenant init` repository and its
CI's `scripts/*.py` steps fail. The run's own closing message tells the user to `git checkout` to
vendor, which does nothing. Present since G7 armed `.githooks`; reported to the owner for its own
change.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — a command-line change; its output was read end to end
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      runtime/test/test_architectures.py (22),
                          scripts/test/test_scaffold_review.py (9),
                          scripts/test/test_governed_tenant.py (1 renamed to what it tests)
Mutation-checked:          yes — ten, each reverted; one survivor became finding 3
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:bc47659b325b
Gates run locally:         ruff, the suites above, runtime/test/test_cli.py, the repo-tree gate,
                          the full pytest run (1806 passed), the end-to-end journey above
Declared gaps:             (1) the manifest is not signed — a rewritten file and hash defeat it,
                              once, on the root commit, visibly;
                          (2) `tenant init` repositories are never vendored (see above)
```
