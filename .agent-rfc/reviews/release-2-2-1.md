# Review — release 2.2.1

Design: `.agent-rfc/designs/release-2-2-1.md`. Owner request, 2026-10-07: move KYC Sentinel's evals
onto the contract — which needs a release carrying `evals-dataset-shapes`.

**Built evidence:** the version is `2.2.1` in `pyproject.toml`, `install-ai-stack.sh` and
`docs/DESIGN.md`'s header; `scripts/test/test_version_consistency.py` passes over all three and the
new `CHANGELOG.md` section, whose one heading is the Fixed entry for the dataset schemas.

## Pass 1 — findings: 1

- `docs-match-behaviour` — **finding:** the 2.2.x row and the backlog said 2.2.0 was the release
  that unblocked C6's tenant steps; it was not, for any tenant with retrieved documents. The row now
  says to adopt the evals contract at 2.2.1, and why; the backlog and the DESIGN mirror say the same.

## Pass 2 — findings: 0

The 2.2.1 section against the fix's commit (one Fixed heading, nothing else since v2.2.0); a patch
adds no compatibility row; the archive entry names the fix's design; no portal file changed since
`v2.2.0`.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — version strings only; one test holds the three declarations together.
Group 2 · Quality / safety — [x] checked — `test_version_consistency.py` over the installer, the package, the design header and the new CHANGELOG section; the fix it carries is reviewed in `.agent-rfc/reviews/evals-dataset-shapes.md`.
Group 3 · Architecture / hygiene — [x] n/a — no code changes in this commit.
Group 4 · Process — [x] checked — design before the version moved; backlog current-state line and archive entry; the release goes through a pull request and CI, then a tag on the merged commit.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — the 2.2.x row names 2.2.1 as the release to adopt the evals contract at, and why.
Group 7 · Auth & session integrity — [x] n/a — the release workflow's signing secrets are unchanged and read by name.

Tests added: none — the existing version pin covers the release.
Mutation-checked: n/a — no logic changed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` — this design's node.
Gates run: full `pytest` on the staged tree (2303 passed, 10 skipped); the self-test's knowledge-graph gate; KYC Sentinel's suite (135 passed), F-scenarios, telemetry conformance (10/10) and strict security harness (24 pass, 1 declared gap) against this tree; `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `declared-vs-enforced`, `docs-match-behaviour`.

KG query: kg:7cea3f32232e
