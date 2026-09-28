# Review — branch-protection-enabled

Design: `.agent-rfc/designs/branch-protection-enabled.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 1

1. **`declared-vs-enforced` — I asserted an enforcement I had not verified, in
   four places, in a slice about not doing that.** The first draft said force
   pushes and deletion of `main` are "refused for everyone, admins included",
   in `docs/process-gates.md`, `CHANGELOG.md`, `docs/PRODUCT_BACKLOG.md` and the
   design itself. The API confirms `allow_force_pushes: false` and
   `allow_deletions: false`, and says nothing about how `enforce_admins: false`
   interacts with them. The only way to find out is to force-push `main`, which
   is not an experiment worth running on a repository. All four now state the
   settings and say the admin path should be assumed to bypass everything until
   someone verifies otherwise. The workflow comment never carried the claim.

## Pass 2 — findings: 3

1. **`declared-vs-enforced` — the protection hangs on a string nothing pinned.**
   GitHub matches a required check by the exact text `Process gates (design +
   review)` against the job's reported name. Renaming that job in
   `.github/workflows/self-test.yml` fails nothing locally: the renamed job
   reports under its new name, the required check never arrives, and pushes
   either sit blocked on a check that cannot come or sail past a protection
   matching nothing. `scripts/test/test_required_check_name.py` now pins the
   job's `name:` to that string and to the copy in `docs/process-gates.md`.
   Proven by renaming the job and watching it fail, then restoring.
2. **The same new test found a second defect on its first run.** The check name
   in `docs/process-gates.md` was **line-wrapped** across two lines, so the exact
   string a reader would copy to re-apply the protection did not exist in the
   document that tells them to copy it. Unwrapped, with the instruction to copy
   it exactly. This is the finding that justifies the test: reading the sentence
   does not reveal the wrap, and the wrap is what breaks it.
3. **`declared-vs-enforced` — `strict` is off and nothing said so.** A branch
   that passed the check against an older `main` can merge without being brought
   up to date, so the check proves that commit was compliant, not that it still
   is on top of what landed since. Added to the same "Limits, stated" entry.

## Pass 3 — findings: 1

1. **`docs-match-behaviour`, on my own design again — P4 claimed no test was
   possible.** It read "nothing executable changes, so no test can fail before
   and pass after", written before Pass 2 produced three tests, one of which
   fails on a rename and caught a real defect. The pillar answer is now what is
   true, including that it was wrong when written, and the design's scope was
   widened to cover `scripts/test/**`. Second slice running where my own record
   described the code beside it incorrectly; the pattern is that I write the
   pillar answers from the plan and do not re-read them against what shipped.

## Pass 4 — findings: 0

Fresh sweep, nothing new.

- `grep` for `cannot refuse|can only report|red after the fact|not blocked|
  GitHub Pro` across tracked `.md` and `.yml` returns one hit, `CHANGELOG.md`
  line 1053, inside the released `## [2.0.0] — 2026-09-19` section. Correctly
  untouched: it was true when written, and a changelog that edits shipped
  entries stops being a history.
- No remaining `admins included` anywhere in the repository.
- `README.md` makes no claim about the gates reporting rather than refusing, so
  nothing there went stale.
- The required-check name is identical in the workflow, the doc and the test,
  pinned in both directions.
- `.agenticframework/process-gates.json` is unchanged: what the repo gates did
  not change, only what GitHub does when the gate says no.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the required-check name exists in three places
                                          because GitHub, a reader and a test each need it; a test
                                          now pins them equal rather than a fourth copy being made
Group 2 · Quality / safety            [x] checked — no executable behaviour changed; the one
                                          unverifiable safety claim was withdrawn rather than softened
Group 3 · Architecture / hygiene      [x] checked — a shorter workflow comment than the one it
                                          replaced; no new file but the test
Group 4 · Process                     [x] checked — four passes; Pass 1 caught my own unverified
                                          claim, Pass 3 caught my own pillar answer
Group 5 · Intuitive UI                [x] n/a — no screen; the one reader-facing surface is the
                                          copyable check name, fixed in Pass 2
Group 6 · Signal integrity            [x] checked — "protected" no longer reads as "cannot be
                                          bypassed"; each statement names who is refused and who is not
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; no credential read or
                                          written, and the protection was applied with the owner's
                                          already-authenticated gh

Tests added/updated:      3 in scripts/test/test_required_check_name.py — the job reports under the
                          required name, the doc names it exactly, and the name is not templated
                          (which would make the first two vacuous). The first fails on a rename,
                          proven; the second failed on its first run and found the line-wrap.
Mutation-checked:          not applicable — no production code changed. The rename proof is the
                          equivalent check for the one coupling this slice introduces.
Fixtures re-pinned:        none required — no tracked file set moved; test_kg_drift_gate.py passes
KG query:                 kg:b4d2450f9d35
Gates run locally:         full suite, artifacts, pillars, KG drift, YAML parse of self-test.yml,
                          and the protection state re-read from the GitHub API after the commit
Declared gaps:             (1) enforce_admins is false and no pull request is required — the owner
                              still bypasses the check; open in docs/PRODUCT_BACKLOG.md with a
                              trigger; (2) whether an admin also bypasses allow_force_pushes and
                              allow_deletions is untested and assumed bypassable; (3) strict is off,
                              so a stale branch can merge on an old passing check
```
