---
status: active
scope:
  - .github/workflows/self-test.yml
  - scripts/test/**
---
# Branch protection enabled on main

## Problem

Three places state that the CI gate cannot refuse a push, and give the same
reason: branch protection needs GitHub Pro for a private repository.

- `.github/workflows/self-test.yml:18` — "It cannot REFUSE a push: branch
  protection on a private repo needs GitHub Pro, so a failing range is red after
  the fact, not blocked."
- `docs/process-gates.md:755` — the first entry under "Limits, stated".
- `docs/PRODUCT_BACKLOG.md:198` — the backlog item, already marked
  **Trigger: FIRED** when the repository was made public.

The repository is public as of 2026-09-27 and branch protection was enabled on
`main` on 2026-09-29:

    required checks : ['Process gates (design + review)'] (strict: False)
    enforce_admins  : False
    force pushes    : False
    deletions       : False
    PR reviews req  : False

So all three statements are now false, and the backlog item is partly done. The
danger is the opposite error: the backlog says making the gate refuse takes four
things — "protect `main`, require the `process-gates` check, require a pull
request, and stop pushing to `main` directly." Two are in place. Writing "the
gate now refuses" would relabel a half-closed control as closed, which is the
failure this repository has a rule about.

## Approach

Record exactly which half is enforced, and keep the other half open with its
trigger.

**Enforced now.** A push to `main` whose head fails `Process gates (design +
review)` is rejected for anyone who is not a repository admin, as is any pull
request merge. `allow_force_pushes` and `allow_deletions` are off as
well. The first draft of this design asserted those two bind admins too;
nothing I can read says so, and the way to find out is to force-push `main`, so
the claim is withdrawn — assume an admin bypasses all of it.

**Not enforced.** `enforce_admins` is false, so the owner — the only admin —
can still push directly to `main` past a failing check. No pull request is
required. That is deliberate rather than an oversight: turning it on makes the
owner's own `git push origin main` impossible, which is a change to how this
repository is worked in every day, and the backlog item says in as many words
that it is "not something to switch on as a side effect of anything else." It
stays the owner's decision, and one line of API call away.

So the three statements become one accurate statement in each place, split the
way the SEC-* controls were: the proven half asserted, the unproven half
declared as a gap, never the two merged into a claim.

`CHANGELOG.md` gets an [Unreleased] entry, because the governance behaviour a
reader of this repository depends on has changed. The released `[2.0.0]` section
says the same thing at line 1039 and is **left alone**: it was true on
2026-09-19, and a changelog that edits shipped entries stops being a history.

One unrelated staleness found while reading the install docs for this slice:
`docs/UserManual.md:1301` offers `VERSION=v1.1.1` as the pinned-install example,
two majors behind the `v2.0.0` release the same page links to. Fixed to a
version-neutral instruction rather than a number that goes stale again.

## Pillars

- P1 applies — this design, before the edit; scope `.github/workflows/self-test.yml`, reviewed in `.agent-rfc/reviews/branch-protection-enabled.md`, with the prose changes in `docs/process-gates.md`, `docs/PRODUCT_BACKLOG.md`, `docs/UserManual.md` and `CHANGELOG.md`.
- P2 applies — three grep-confirmed statements of the same claim (`.github/workflows/self-test.yml:18`, `docs/process-gates.md:755`, `docs/PRODUCT_BACKLOG.md:198`); the sweep for `branch protection|GitHub Pro|cannot REFUSE` found no fourth in a tracked `.md` or `.yml` outside `.agent-rfc/`. No code changes, no dependencies.
- P3 n/a — a comment and four prose blocks; no execution path added.
- P4 applies — this answer was wrong when written: it said nothing executable changes, so no test could fail before and pass after. The review found one that can. `scripts/test/test_required_check_name.py` pins the job's `name:` in `.github/workflows/self-test.yml` to the exact string branch protection requires, and to the string `docs/process-gates.md` gives a reader to copy — proven by renaming the job and watching it fail, and it caught a real defect on its first run (the check name was line-wrapped in the doc, so the string a reader would copy did not exist). Protection state itself is asserted against GitHub by reading `gh api /repos/bobbyaqlaar/AgentSmith/branches/main/protection`, quoted in this design and re-read after the commit. No mutation target, because no branch was added.
- P7 applies — a YAML comment in `.github/workflows/self-test.yml` and Markdown elsewhere; the one Python file added, `scripts/test/test_required_check_name.py`, parses that workflow with `yaml.safe_load` behind `pytest.importorskip` rather than regex, and `test_the_job_name_is_not_generated_from_something_else` rejects a templated job name that would make its own comparison vacuous. No shell touched.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 n/a — no untrusted content read; the protection state is read from GitHub with `gh` and quoted, not executed.
- P12 applies — the change names no credential. `enforce_admins` and the required-check list are repository settings the owner holds; nothing here reads or writes a token, and the protection was applied with the owner's already-authenticated `gh`.
- P13 applies — **this is the pillar this slice is about, and it cuts both ways.** No check gets weaker: `Process gates (design + review)` becomes required where it was advisory. But the control is not fully closed, so it is split — the admin exemption and the absent pull-request requirement are stated as the remaining gap in `docs/process-gates.md` and left open in `docs/PRODUCT_BACKLOG.md` with a trigger, rather than being dropped because the headline is now true.
- P14 applies — no fixture, baseline or golden changes; `.agent-rfc/fixtures/knowledge_graph.json` is re-checked with `scripts/test/test_kg_drift_gate.py` and re-pinned only if the tracked file set moved.
- P15 applies — "protected" must not read as "cannot be bypassed". Each place says who is refused and who is not, so a reader cannot take the admin path as covered; `docs/process-gates.md` keeps the statement under "Limits, stated" rather than deleting the entry, because there is still a limit to state.
- P16 applies — when the required check cannot report at all (the billing refusal of 2026-09-27, where every job produced zero steps), a required check that never arrives leaves the push blocked for a non-admin rather than admitted, and the admin path is then the only way to land a fix. That is the safe direction, and it is why the admin exemption is written up in `docs/process-gates.md` as a recovery path as well as a gap, and why `scripts/test/test_required_check_name.py` exists: a renamed job produces exactly the same never-arriving check, from a cause no one would look for.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the whole slice: three documents declared a limit that no longer holds, and a control that is now half-enforced must not be written up as enforced.
- `docs-match-behaviour` — the three statements against the protection the API reports.
- `ambiguous-signals` — "protected" meaning both "refuses everyone" and "refuses everyone but the one person who pushes here".
- `backlog-discipline` — the item is not deleted on the strength of the headline; the unfinished half keeps a trigger.
- `provenance-and-precedence` — the released `[2.0.0]` entry and the new [Unreleased] one both describe the same setting at different times; history is not edited to agree with the present.
- `every-line-earns-its-place` — a shorter accurate comment in the workflow, not a longer one.
