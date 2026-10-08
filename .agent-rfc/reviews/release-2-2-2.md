# Review — release 2.2.2

Design: `.agent-rfc/designs/release-2-2-2.md`. Owner request, 2026-10-08: cut the release carrying
`env-file-credentials`.

**Built evidence:** the version is `2.2.2` in `pyproject.toml`, `install-ai-stack.sh` and
`docs/DESIGN.md`'s header; `scripts/test/test_version_consistency.py` passes over all three and the
new `CHANGELOG.md` section, whose one heading is the credential-precedence change.

## Pass 1 — findings: 1

- `docs-match-behaviour` — **finding:** the first draft of the 2.2.x row said only that `.env` now
  wins for credentials. A developer who exports a key on purpose — to test a second account — needs
  the way back in the same sentence: `env_overrides` in `tenant.yaml`. Added, with the note that CI
  and deployments have no `.env`.

## Pass 2 — findings: 0

The 2.2.2 section against `env-file-credentials`'s commit — one Changed heading, nothing else since
v2.2.1; a patch adds no compatibility row, so the 2.2.x row carries it; `docs/DESIGN.md`'s mirror,
the backlog and the archive say the same; no portal file changed since `v2.2.1`.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — version strings only; one test holds the three declarations together.
Group 2 · Quality / safety — [x] checked — `test_version_consistency.py` over the installer, the package, the design header and the new CHANGELOG section; the change it carries is reviewed in `.agent-rfc/reviews/env-file-credentials.md`.
Group 3 · Architecture / hygiene — [x] n/a — no code changes in this commit.
Group 4 · Process — [x] checked — design before the version moved; backlog current-state line and archive entry; the release goes through a pull request and CI, then a tag on the merged commit.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — the 2.2.x row says what a developer will notice from 2.2.2 and how to keep the shell winning for a key.
Group 7 · Auth & session integrity — [x] checked — the release carries the credential-precedence fix; the release workflow's signing secrets are unchanged and read by name.

Tests added: none — the existing version pin covers the release.
Mutation-checked: n/a — no logic changed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` — this design's node.
Gates run: full `pytest` on the staged tree (2327 passed, 10 skipped); the self-test's knowledge-graph gate; portal not run — no portal file changed since `v2.2.1`; `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `declared-vs-enforced`, `docs-match-behaviour`.

KG query: kg:de6105f67dae
