# Review — scaffold-rfc-and-vouched-skip

Design: `.agent-rfc/designs/scaffold-rfc-and-vouched-skip.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 4

1. **`guards-must-be-able-to-fail` — I reintroduced a fragility I had fixed two
   slices earlier.** Guardrails 2 and 3 skipped with `is_vouched "$file" && continue`.
   `hooks/pre-commit` has no `set -e` today, so it works — but the common path on
   a tenant's first commit is *not* skipping, where that one-liner returns 1, and
   the day anyone adds `set -e` the hook exits mid-loop. The identical pattern was
   removed from `hooks/post-checkout` on 2026-09-29 with a comment saying why, and
   I wrote it again here. Both are now `if is_vouched ...; then continue; fi`.

2. **The records described a smaller change than the code.** `write_scaffold_records`
   is shared with `tenant adopt`, so the RFC is written by **both** commands — my
   design and CHANGELOG both said `tenant init`. Corrected in both.

3. **`tenant adopt` was left half-fixed, by me.** Adoption now gets the RFC file,
   so Guardrail 4 passes — but `runtime/adopt.py`'s `commit_command()` printed no
   `RFC-NNN` trailer, so `hooks/commit-msg` would still refuse the adoption commit
   on an enterprise machine. Satisfying one of the two enterprise rules and not
   the other is worse than satisfying neither, because it looks fixed. `commit_command`
   now takes the reference and `_cmd_tenant_adopt` passes `_rfc_reference(plan.root)`.

4. **A third enterprise rule, found by running the test rather than reading.**
   The design set out to beat Guardrail 4; the enterprise test then failed on
   `hooks/commit-msg` requiring `RFC-NNN` *in the message*. That check greps the
   whole message, so the reference goes in a trailer and never touches the
   72-character subject rule — which is why the fix is a `Refs:` line and not a
   longer subject.

### Examined and cleared

- **Cost.** `is_vouched` runs one `grep` per staged file, which reads like a
  regression. It is the opposite: the hook previously ran **one `python3` per
  staged `.py`**, and a first commit stages 167 vendored ones. The vouch removes
  those processes, so the path this design is about gets faster, not slower.
- **Delivery.** The skip only happens if `scripts/vouched_files.py` reaches the
  machine. Both `install-ai-stack.sh` and `hooks/post-checkout` take
  `$FRAMEWORK_DIR/scripts` wholesale, so it ships and vendors like every other
  script — confirmed by the end-to-end test seeing 167 files vouched.

## Pass 2 — findings: 1

1. **`test-that-cannot-fail`, caught by an existing test rather than by me.**
   The RFC was added to `written` (which feeds the manifest) but not to `records`
   (which callers stage by name), so `tenant adopt` wrote a file and left it
   untracked. `test_tenant_adopt.py` said it plainly — *"every file adopt wrote was
   staged by name"* — and `test_the_machines_provisioning_hooks_are_not_chained_into_an_adopted_repository`
   failed with `?? .agent-rfc/001-scaffold.md`. Fixed; 26 pass. Worth recording
   because nothing I wrote would have caught it: my own tests only exercised
   `tenant init`.

## Pass 3 — findings: 1

1. **A suite must watch everything it mutates.** The two new mutations target
   `scripts/vouched_files.py`, and `tenant_adopt`'s `watch` list did not include
   it — so a change to the helper would not have triggered the suite that tests
   it. `test_mutation_check_scope.py` failed on exactly that. Added.

## Pass 4 — findings: 0

Fresh sweep, nothing new.

- All four guardrails accounted for: 1–3 take the skip, 4 cannot (it is a
  repository-level question) and is answered by Part A instead.
- Every failure path of the helper returns an empty list, each with its own test:
  no manifest, unparseable manifest, a manifest that is not a mapping, a manifest
  naming an unstaged or outside path, and no git repository at all.
- The vouch is judged on the **staged** blob, so a working-tree edit after
  `git add` cannot inherit or lose a vouch it did not earn — pinned by
  `test_a_staged_edit_after_add_is_judged_on_the_staged_copy`.
- `.agent-rfc/**` and `**.md` are both `not_gated`, so the RFC is invisible to
  `manifest_problems()` — it is in the manifest for `--force`, not for vouching.
  An earlier note of mine claimed the escape would break without it; that was
  wrong and the design records it as such.
- The scaffolded RFC's warning is indented, so it cannot fail
  `.github/scratch-tenants/build.sh`'s column-0 grep — asserted in the test, not
  just intended.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the manifest, its hashes and the "what the
                                          framework wrote" idea already existed; this reads them
                                          rather than adding a second notion. One helper, because
                                          POSIX shell cannot parse JSON — the same reason
                                          check_bare_except.py exists, resolved the same way
Group 2 · Quality / safety            [x] checked — a guardrail is relaxed, so every failure path
                                          was enumerated and tested, and each one relaxes nothing
Group 3 · Architecture / hygiene      [x] checked — no allowlist file, no second manifest, no
                                          change to the gate; the skip is computed where the data
                                          already lives
Group 4 · Process                     [x] checked — four passes; Pass 1 found me repeating a
                                          fragility I had removed two slices earlier, Pass 2 was
                                          an existing test catching what my own tests could not
Group 5 · Intuitive UI                [x] checked — the hook says how many files it skipped and
                                          why; the scaffolded RFC tells the reader it is a template
Group 6 · Signal integrity            [x] checked — "not checked" does not print as "checked and
                                          clean", and an unverifiable manifest reads as no vouch
                                          rather than a free pass
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; no credential read.
                                          The helper reads the git index and writes nothing

Tests added/updated:      3 in scripts/test/test_first_commit.py (a defect shipped in vendored code
                          does not block the first commit; a tenant edit to a vendored file is
                          checked again; the enterprise first commit now succeeds), 8 in
                          scripts/test/test_vouched_files.py (every failure path returns an empty
                          list, plus the staged-vs-worktree property), 2 in
                          scripts/test/test_vendored_markers.py (the Guardrail 1 counterpart to the
                          Guardrail 2 tree sweep, proven able to fail), and one older assertion
                          loosened from an exact `-m` count to the contract it meant.
Mutation-checked:          the two added here were applied and reverted BY HAND, each watched to
                          fail its own named test: the vouch degrading into a path allowlist ->
                          test_an_edited_file_loses_its_vouch; a manifest that is not a mapping being
                          trusted -> test_a_manifest_that_is_not_a_mapping_vouches_for_nothing.
                          The full tenant_adopt suite was NOT re-run to completion locally: it was
                          stopped at 2h44m ELAPSED (the harness restores on SIGTERM; the tree was
                          checked clean afterwards). That figure measured nothing — the machine had
                          been asleep, and `ps etime` counts sleep, so comparing it with an earlier
                          run's elapsed time was not evidence of anything. Recorded because the
                          first version of this sign-off treated it as a slowdown and a backlog item
                          was filed on it; both were wrong and the item is withdrawn. Its other 24
                          mutations were all caught on 2026-09-29 and none of their targets changed
                          here. CI runs `mutation_check --changed-since` on this push, which is
                          where the full suite is proven. scripts/vouched_files.py was added to the
                          suite's watch list so a change to it triggers them.
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json via map_codebase.run_map(force=True);
                          test_kg_drift_gate.py passes
KG query:                 kg:1bd8268bfd3d
Gates run locally:         full suite, the four slow tenant suites together (63 passed), ruff check
                          + ruff format --check, bash -n on hooks/pre-commit, verify_system.py
                          --check-hooks, artifacts, pillars, KG drift
Declared gaps:             (1) the skip covers Guardrails 1–3; a guardrail added later gets no
                              vouch unless someone wires it, and nothing enforces that; (2) the
                              tests cover python-fastapi on a default and an enterprise machine,
                              not the ts-react or go stacks, whose vendored .py set is the same;
                              (3) a tenant on an older release still vendors whatever that release
                              contained — this fixes the mechanism, not history.
```
