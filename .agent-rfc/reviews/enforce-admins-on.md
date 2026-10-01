# Review — enforce-admins-on

Design: `.agent-rfc/designs/enforce-admins-on.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 2

1. **The descriptions were wrong about more than the admin.** Searching for
   every statement of the setting (`git grep enforce_admins`) found
   `docs/process-gates.md` › Limits also naming ONE required check,
   `Process gates (design + review)`, where all seven have been required since
   2026-09-30. Corrected with the dates of both changes. Two done designs and the
   tenant guide `docs/team-observability.md` also mention `enforce_admins`; the
   designs are dated decision records, and the tenant guide recommends it for
   tenant repositories — both left as they are, deliberately.

2. **My archive entry claimed an outcome that had not happened.** It said PR #20
   "could not merge until it was fixed", which reads as merged. At the time of
   writing the fix was pushed and its checks not yet back. Reworded to what was
   true: GitHub reported it `BLOCKED`, and the missing entry was added on the
   same branch.

## Pass 2 — findings: 0

Re-read the workflow comment, the Limits section, the archive entry and the
CHANGELOG entry against the setting as the API reports it:
`enforce_admins: true`, seven required contexts, `strict: false`, no
`required_pull_request_reviews`, force pushes and deletion off. Each statement
matches; the one thing not demonstrated — a refused direct push — is said to be
not demonstrated, in both the Limits section and the archive.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — documentation and one comment; nothing duplicated or shared.
Group 2 · Quality / safety — [x] checked — every statement checked against `gh api …/branches/main/protection`; the CI gate run locally over this branch's range before pushing.
Group 3 · Architecture / hygiene — [x] n/a — no structure changes; the setting lives in GitHub, not in this repository.
Group 4 · Process — [x] checked — designed before the edit; both backlog items closed in the same change, with evidence, into the append-only archive.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — "configured and read back" is kept apart from "demonstrated" everywhere the refusal of a direct push is mentioned.
Group 7 · Auth & session integrity — [x] checked — the change documents a stronger control: the admin bypass is gone. What stays open (no approving review, `strict` off) is stated with its reason.

Tests added: none — no behaviour in this repository changes; the setting is GitHub's and is read back from its API.
Mutation-checked: n/a — no code.
Fixtures re-pinned: none.
Gates run: the process gate's design and stop checks, the artifacts gate (archive append-only: +26 −0), and `python3 scripts/process_gate.py ci --base origin/main --head HEAD` — the CI gate over this branch's range, CHANGELOG rule included — before pushing.

Levers reviewed: `docs-match-behaviour`, `declared-vs-enforced`, `backlog-discipline`.

KG query: kg:ad1283d8cfbf
