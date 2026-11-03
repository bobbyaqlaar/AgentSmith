# Review — release 3.0.1

Design: `.agent-rfc/designs/release-3-0-1.md`. Owner request, 2026-11-03: fix the installer and cut the release.

**Built evidence:**
- The version is `3.0.1` in `pyproject.toml`, `install-ai-stack.sh` and `docs/DESIGN.md`'s header, and
  `scripts/test/test_version_consistency.py` passes over all three and the new `CHANGELOG.md` section.
- The section is what was already under Unreleased. The note in the 3.0.x row and DESIGN's mirror is new.
- The scratch tenants were green on `81a7e05`, the install fix.

## Pass 1 — findings: 2

1. `docs-match-behaviour` — **The backlog ticked "verify job green" in the commit that makes the tag possible,** before
   any such run can exist. **Fix:** the step stays open until the published release has passed, and the state line says
   what `release.yml` does rather than what it did.
2. `docs-match-behaviour` — **The row said a 3.0.0 installer notices when run "against a newer release's URL".** Read from
   the tag, it downloads from `releases/latest`, so a saved copy notices with no URL chosen at all. **Fix:** the row, its
   mirror and the design say that.

## Pass 2 — findings: 0

- **A patch is the right size:** no `contract/` file or wire row changes. `remove_node` has no reference in `runtime/` or
  `contract/`, and is absent from the imports read from KYC Sentinel; OTS imports nothing of AgentSmith.
- **The assets named as removed** are the ones `scripts/build_release_assets.sh` no longer builds.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — version strings and records.
Group 2 · Quality / safety — [x] checked — `scripts/test/test_version_consistency.py` holds the versions together; `verify-published-release` runs after publishing.
Group 3 · Architecture / hygiene — [x] n/a — no dependency or structural change.
Group 4 · Process — [x] checked — design before the bump; CHANGELOG section and row; archive and backlog; two shipped designs marked done.
Group 5 · Intuitive UI — [x] n/a — no screen or message changes.
Group 6 · Signal integrity — [x] checked — the backlog claims no verification that has not run.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: none — `scripts/test/test_version_consistency.py` already covers a release.
Mutation-checked: n/a — no code changes.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `agentsmith gates run` for py_compile, repo-tree, Commit guardrails, check-kg, bash -n and the release install; ruff; artifacts; `test_version_consistency.py`. The full suite ran on the same tree less the bump (2479 passed); Self-Test runs it again on this commit.

Levers reviewed: `declared-vs-enforced`, `docs-match-behaviour`, `when-the-fallback-fails`.

KG query: kg:6d93758d4a6e
