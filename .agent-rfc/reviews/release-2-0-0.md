# Review — release 2.0.0

Design: `.agent-rfc/designs/release-2-0-0.md`. Owner decision, 2026-09-19: 2.0.0, not 1.4.0.

**Built evidence (2026-09-19):** the version is `2.0.0` in `pyproject.toml`, `install-ai-stack.sh`
and `docs/DESIGN.md`'s header, and `scripts/test/test_version_consistency.py` passes over all
three and the new `CHANGELOG.md` section. Every heading under the old Unreleased section was read
to decide the number and write the compatibility row.

## Pass 1 — findings: 1

- `docs-match-behaviour` — **finding:** the version question put to the owner named one break —
  the `ai-*` shell functions — and the Unreleased section holds another a 1.3.0 user meets: the
  core documents were renamed (`SPECS.md` → `docs/DESIGN.md`, `FIXES_AND_CLEANUP.md`,
  `Product_Archive.md`) and numbered section anchors are gone, which breaks links from outside the
  repository. It is in the 2.0.x row. It only strengthens the owner's choice of a MAJOR.

## Pass 2 — findings: 0

The row against each Changed and Removed entry in the 2.0.0 section; the Wire Contract table
against what is new on a wire since 1.3.0 (the Dev record); the backlog's current-state line.
Considered and declined: re-pinning KYC Sentinel's `@v1.3.0` requirement — it is that
repository's upgrade to take on its own schedule, and the backlog already carries it.

## Pass 3 — findings: 1

After the release push, from Self-Test's Ops Portal job.

- `run-the-gates-ci-lists` — **finding:** `portal/test/wireContract.test.ts` failed: it required
  `FIRST_VERSIONED_RELEASE` (1.3.0) to be no older than the newest compatibility-matrix row — the
  right check while 1.3.0 was pending, and false for every release after it. The constant is right;
  the test had expired. It now checks the constant names a release in the matrix and that the Wire
  Contract table dates `frameworkVersion` to it; setting the constant to `1.4.0` and to `1.2.0`
  each fails it. I ran the Python gates for the release and not the portal's `npm test`, which CI
  also runs; the release assets carry no portal code, so v2.0.0 as published is unaffected.

## Pass 4 — findings: 0

The new test, the constant's comment, and `npx tsc --noEmit` over the portal.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      none — scripts/test/test_version_consistency.py already pins the three
Mutation-checked:          yes — the wire-contract test, with the constant at 1.4.0 and 1.2.0
Fixtures re-pinned:        none
KG query:                 kg:813655c6d413
Gates run locally:         the version, release-artifact and documentation tests; the full pytest run;
                          the portal's `npm test` and `npx tsc --noEmit`
Declared gaps:             none
```
