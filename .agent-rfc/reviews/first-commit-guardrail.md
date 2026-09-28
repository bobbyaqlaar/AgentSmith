# Review — first-commit-guardrail

Design: `.agent-rfc/designs/first-commit-guardrail.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 1

1. **`no-copy-paste` — I duplicated a six-line comment verbatim.** Both
   `write_text` sites in `scripts/verify_system.py` got the same explanation of why
   the marker literal is assembled, twelve lines for one idea. The first site keeps
   the explanation; the second says "Assembled for the same reason as repo1 above."

**Examined and cleared, not a finding:** splitting `"# TODO: " + "agent fix this"`
could have broken the detection that code exists to prove. It does not —
`verify_system.py --check-hooks` still reports "opted-in repo: pre-commit enforces
guardrail 1 (exit 1)", because the file written at runtime is byte-identical. Run,
not reasoned about.

## Pass 2 — findings: 2

1. **`docs-match-behaviour` — the design described a smaller change than shipped,
   in three ways.** It covered only the empty-except guardrail, and said nothing
   about (a) the three omissions in the shared `install` fixture, (b) the second
   guardrail — unresolved AI markers — refusing the same commit for a different
   reason, or (c) the two guard tests. P4 claimed "two tests" where four shipped.
   All four corrected. Third slice in a row where my own record described the plan
   rather than the result; the cause is that I write pillar answers before the work
   and do not re-read them against it.
2. **`fixture-truth` — the fixture docstring still overclaimed after I fixed it.**
   It says "a complete `~/.agent-framework` … as install-ai-stack.sh lays them
   out", and it is still not complete: the installer builds a venv and the fixture
   does not. That absence is load-bearing — it is why callers must name
   `AGENTSMITH_PYTHON` — so the docstring now states what it has, what it lacks,
   and that every omission so far has hidden a defect.

## Pass 3 — findings: 1

1. **`test-that-cannot-fail` — my own sweep carried an exemption that matched
   nothing.** `_tracked_python_files()` filtered `fixtures/` and
   `scripts/test/fixtures/` for "deliberately bad code". `git ls-files 'fixtures/*.py'`
   returns **zero** files: there is no Python under either path. The filter
   protected nothing and implied a category of pre-approved exceptions that does
   not exist. Removed, with the reasoning recorded in its place: if such a fixture
   is ever added, this test failing is the right outcome, so someone decides rather
   than inheriting a pass.

## Pass 4 — findings: 1

1. **The same commit is still refused on an enterprise machine, and this slice
   does not fix it.** `hooks/pre-commit` Guardrail 4 requires at least one `*.md` at
   `.agent-rfc/` **depth 1** where an org policy file exists; `tenant init` writes
   `.agent-rfc/designs/scaffold.md`, at depth 2. Verified, not inferred: an
   isolated HOME carrying `agenticframework-org.yaml`, everything else in this
   slice applied, and the printed commit refused with "Enterprise policy requires
   at least one RFC under `.agent-rfc/`".

   Not fixed here on purpose. Counting recursively would make a design note satisfy
   an RFC requirement, and writing a top-level RFC stub from `tenant init` would
   create the kind of empty artifact the artifacts registry refuses — both change
   what a contract means, which is the owner's call. Recorded in
   `docs/PRODUCT_BACKLOG.md` with the trigger already fired, stated in the design,
   and stated in `test_first_commit.py`'s own docstring so nobody reads its green as
   covering enterprise. The CHANGELOG entry was written before this was found and
   said "every repository onboarded from `git init` hit this" without qualification;
   it now says which half is fixed.

## Pass 5 — findings: 0

Fresh sweep, nothing new.

- All twelve markers carry a specific reason; none is a bare `# fail-open:`. The
  thirteenth handler is restructured, not labelled.
- No `# fail-open` without the colon remains in `scripts/` or `runtime/`; the five
  other matches are prose about fail-open behaviour, not suppression markers.
- `check_bare_except.py`'s docstring cites `runtime/llm_gateway.py`'s
  `_record_span_attributes` as its example — checked, still there at line 885, so
  the example did not go stale under this change.
- The whole tracked tree passes the checker, and the two end-to-end tests pass with
  the pre-commit guardrail observed running and passing.
- `tenant adopt` is unaffected: `hooks/post-checkout` does not vendor `scripts/`,
  `runtime/` or `fixtures/` into an adopted repository, so its commit never stages
  them.
- Guardrail 3 (direct `cost_router` imports, enterprise only) cannot fire on the
  vendored tree: its regex anchors on a line beginning `import`/`from`, and the only
  match in `runtime/` is prose inside a docstring.
- `scripts/test/` and `hooks/` also carry the AI markers and are **not** vendored,
  so they cannot block a tenant; only `verify_system.py` could, and did.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the `install` fixture is shared through
                                          conftest.py rather than copied, following the precedent
                                          already there for `gated_repo`; the duplicated comment
                                          found in Pass 1 was collapsed to one statement
Group 2 · Quality / safety            [x] checked — twelve comments and one restructure; the
                                          restructure is behaviour-identical and the one behavioural
                                          edit (an assembled string literal) was re-verified against
                                          the check it exists to satisfy
Group 3 · Architecture / hygiene      [x] checked — no allowlist file, no new module, no change to
                                          the checker; each exemption lives on the line it excuses
Group 4 · Process                     [x] checked — five passes; Pass 3 found my own sweep exempting
                                          a directory that does not exist, Pass 4 found the half of
                                          the bug this slice does not fix
Group 5 · Intuitive UI                [x] n/a — no screen. The reader-facing surface is the commit
                                          command `tenant init` prints, which now works on a default
                                          machine and is tested by running it
Group 6 · Signal integrity            [x] checked — "flagged" now means "nobody said why"; the one
                                          handler that was not a fail-open is not labelled as one;
                                          the CHANGELOG no longer claims a fix wider than it is
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; no credential read.
                                          The test repos have no remote and AGENTSMITH_AUTOPUSH=0,
                                          so post-commit cannot push anywhere

Tests added/updated:      4 new across scripts/test/test_bare_except_tree.py (the tree sweep, plus a
                          guard that it is sweeping a real list) and scripts/test/test_first_commit.py
                          (the printed commit succeeds; the pre-commit guardrail is observed running
                          and passing rather than absent). Three fail before this change and pass
                          after, proven by reverting the source fixes and re-running. The `install`
                          fixture gained the two templates, three docs and three machine hooks the
                          installer ships, which is what made any of this observable.
Mutation-checked:          not applicable — nothing branches. The equivalent check is the pair of
                          end-to-end tests, and the revert-and-rerun proof above.
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json via map_codebase.run_map(force=True);
                          test_kg_drift_gate.py passes
KG query:                 kg:eb5f8244eff2
Gates run locally:         full suite (1962 passed / 10 skipped), the four fixture-consuming suites
                          together (166 passed), ruff check + ruff format --check, verify_system.py
                          --check-hooks, artifacts, pillars, KG drift
Declared gaps:             (1) an enterprise machine still cannot make the first commit — verified,
                              unfixed, backlog Trigger FIRED; (2) the tests cover the python-fastapi
                              stack on a default machine, which is the configuration where the
                              framework's own .py files are what trip the guardrails; (3) a tenant
                              still runs these guardrails over vendored code it did not write —
                              deferred with its own backlog row and reasoning.
```
