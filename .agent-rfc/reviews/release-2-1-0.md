# Review — release 2.1.0

Design: `.agent-rfc/designs/release-2-1-0.md`. Owner request, 2026-10-05: cut the release.

**Built evidence:** the version is `2.1.0` in `pyproject.toml`, `install-ai-stack.sh` and
`docs/DESIGN.md`'s header, and `scripts/test/test_version_consistency.py` passes over all three and
the new `CHANGELOG.md` section. Every heading under the old Unreleased section was read to decide
the number and write the compatibility row.

## Pass 1 — findings: 3

Each claim in the row checked against the CHANGELOG entry it summarises.

- `docs-match-behaviour` — **finding:** the first draft said "the bypass sweep refuses a push",
  as if new. The sweep shipped in 2.0.0; what 2.1.0 adds is that a sync gives it to a tenant armed
  before it existed (KYC Sentinel, OTS). Reworded.
- `docs-match-behaviour` — **finding:** it said the gates workflow's new rules check "fails once"
  after a sync. It does not: the sync rewrites the rule files in the same commit that adds the
  check. Reworded to what happens.
- `docs-match-behaviour` — **finding:** it said `main` has refused its owner "since 2.0.0"; the
  required check landed on 2026-09-29, after 2.0.0, in this release's own Unreleased section.
  Dated correctly.

## Pass 2 — findings: 0

The 2.1.x row against each Changed and Fixed entry in the new 2.1.0 section and the contracts'
own entries; the Wire Contract table's 2.1.0 row against the telemetry catalogue (pinned by
`test_telemetry_contract.py`); `docs/DESIGN.md`'s mirror holds the current row only; the portal's
`wireContract.test.ts` (13 checks) — the test 2.0.0's release missed until CI.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — version strings only; one test holds the three declarations together.
Group 2 · Quality / safety — [x] checked — `test_version_consistency.py` over the installer, the package, the design header and the new CHANGELOG section; the Wire Contract table pinned to the telemetry catalogue; the portal's `wireContract.test.ts`.
Group 3 · Architecture / hygiene — [x] n/a — no code changes.
Group 4 · Process — [x] checked — design before the version moved; backlog current-state line and archive entry; the release goes through a pull request and CI, then a tag on the merged commit.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — the 2.1.x row says what a tenant will notice and that nothing breaks; each claim checked against the entry it summarises (pass 1).
Group 7 · Auth & session integrity — [x] n/a — the release workflow's signing secrets are unchanged and read by name.

Tests added: none — existing version and wire-contract pins cover the release.
Mutation-checked: n/a — no logic changed.
Fixtures re-pinned: none.
Gates run: full `pytest` on the staged tree (2215 passed, 10 skipped); portal `npm test` and `npx tsc --noEmit`; `ruff check .`; the self-test's py_compile, tree, knowledge-graph and shell-syntax gates; `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `declared-vs-enforced`, `docs-match-behaviour`, `run-the-gates-ci-lists`.

KG query: kg:75f3096f8eb5
