# Review — the source-checkout marker is tested wherever the tests run

Design: `.agent-rfc/designs/version-marker-test.md`. Owner's instruction, 2026-09-18: fix the
surviving mutant.

**Built evidence (2026-09-18):**

- **Cause confirmed before the fix.** On this machine `framework_version()` returns `1.3.0`: the
  package is installed, so the version comes from its metadata and never carries `+src`. The
  strip in `runtime/cli.py` had nothing to remove, and every version test passed with it deleted.
  In CI nothing is installed, so the same mutant died there — the gate reported the machine.
- **The test now sets the marker itself.** `test_the_declared_version_carries_no_source_marker`
  patches `runtime.version.framework_version` to `1.3.0+src` and asserts the declared version
  equals `1.3.0`. `test_a_released_version_is_declared_unchanged` pins the other branch.
- **Mutation checks:** `python3 scripts/mutation_check.py tenant_scaffold` — 6 mutations, all
  caught, on the machine where one survived. One more by hand, reverted: stripping the last four
  characters unconditionally — caught by the new released-version test.

## Pass 1 — findings: 1

- `run-the-gates-ci-lists` — **finding:** `gates run` failed `verify_system.py --check-kg`. The
  committed graph did not have the new test or this change's two records, so CI would have failed
  the push. `.agent-rfc/fixtures/knowledge_graph.json` is regenerated and in this commit.

## Pass 2 — findings: 0

Every lever over the final diff, the regenerated graph included. Considered and declined:

- `test-the-contract` on `test_the_scaffold_declares_the_installed_version`, which still computes
  its expected value by repeating the strip. Its job is the real `framework_version()` reaching
  the scaffold, not the strip; the two new tests pin the strip with literals, and the `9.9.9` test
  pins that the value is read rather than hardcoded. Left as it is.
- Patching `_cached` in `runtime.version` instead of the function: that tests the caching as well
  and would leak between tests if a patch were missed. Patching the function via `monkeypatch`
  is undone after each test.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_cli.py (1 rewritten, 1 added)
Mutation-checked:          yes — the tenant_scaffold suite, 6 of 6 caught locally; one more
                          by hand, reverted
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json (pass 1)
KG query:                 kg:84e7f02f02d6
Gates run locally:         the full pytest run (1668 passed, 10 skipped), `agentsmith gates
                          run`: 13 passed, 0 failed, 6 skipped (they need services) — 67 of
                          67 mutations caught
Declared gaps:             none
```
