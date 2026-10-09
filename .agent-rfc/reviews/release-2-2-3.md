# Review — release 2.2.3

Design: `.agent-rfc/designs/release-2-2-3.md`. Owner request, 2026-10-09: move AqlaarTeleologyStudio's
evals onto the contract — which needs a release carrying `setup-evals-provider`.

**Built evidence:** the version is `2.2.3` in `pyproject.toml`, `install-ai-stack.sh` and
`docs/DESIGN.md`'s header; `scripts/test/test_version_consistency.py` passes over all three and the
new `CHANGELOG.md` section, whose one heading is the setup step's Fixed entry.

## Pass 1 — findings: 0

The 2.2.3 section against the fix's commit — one Fixed heading, nothing else since v2.2.2; the
2.2.x row names the pin an eval job's setup step needs, and DESIGN's mirror, the backlog and the
archive say the same; no portal file changed since `v2.2.2`.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — version strings only; one test holds the three declarations together.
Group 2 · Quality / safety — [x] checked — `test_version_consistency.py` over the installer, the package, the design header and the new CHANGELOG section; the fix it carries is reviewed in `.agent-rfc/reviews/setup-evals-provider.md`.
Group 3 · Architecture / hygiene — [x] n/a — no code changes in this commit.
Group 4 · Process — [x] checked — design before the version moved; backlog current-state line and archive entry; the release goes through a pull request and CI, then a tag on the merged commit.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — the 2.2.x row names the setup-step pin an eval job needs to grade.
Group 7 · Auth & session integrity — [x] n/a — the release workflow's signing secrets are unchanged and read by name.

Tests added: none — the existing version pin covers the release.
Mutation-checked: n/a — no logic changed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` — this design's node.
Gates run: full `pytest` on the staged tree (2328 passed, 10 skipped); the self-test's knowledge-graph gate; portal not run — no portal file changed since `v2.2.2`; `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `declared-vs-enforced`, `docs-match-behaviour`.

KG query: kg:6d5bf7d8f29c
