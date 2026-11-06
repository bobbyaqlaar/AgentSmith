# Review — release 4.0.1

Design: `.agent-rfc/designs/release-4-0-1.md`. Owner request, 2026-11-03: launch in two stages; the date moved to
Saturday 7 November on the 6th.

## Pass 1 — findings: 1

1. `docs-match-behaviour` — **The 4.0.x row said nothing about 4.0.1,** while `AgentStatus` now requires
   `widgetScriptUrl`, a compile error for a caller who omitted it. **Fix:** the row and its mirror in `docs/DESIGN.md` say
   4.0.1 changes no import or wire value, name the prop, and say who it can affect.

## Pass 2 — findings: 0

- **A patch is the right size:** every shipped change is a fix, a message, a document or a template a tenant copies; no
  import, span attribute, hook interface or contract file changes between `v4.0.0` and this commit.
- **The records match:** the backlog's current state names v4.0.1 and KYC on 4.0.0 (KycSentinel#7, merged), step 5 is
  ticked, and the target date is the owner's new one. The archive entry names each shipped design.
- **Seven designs move to done,** each merged before this commit; `hook-answers-without-its-payload` shipped in 4.0.0.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — version strings and records.
Group 2 · Quality / safety — [x] checked — `scripts/test/test_version_consistency.py` holds the versions together; `verify-published-release` runs after publishing.
Group 3 · Architecture / hygiene — [x] n/a — no dependency or structural change.
Group 4 · Process — [x] checked — design before the bump; CHANGELOG section and row; archive and backlog; shipped designs marked done.
Group 5 · Intuitive UI — [x] n/a — no screen or message changes.
Group 6 · Signal integrity — [x] checked — the backlog claims no verification that has not run.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: none — `scripts/test/test_version_consistency.py` already covers a release.
Mutation-checked: n/a — no code changes.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `test_version_consistency.py`, `test_release_install.py`, `test_private_names.py`; ruff; mypy; py_compile; the repo-tree check; check-kg; check-hooks; artifacts; the process gate. Self-Test runs the full suite on this commit.

Levers reviewed: `docs-match-behaviour`, `two-owners-two-cadences`.

KG query: kg:092006e2b188
