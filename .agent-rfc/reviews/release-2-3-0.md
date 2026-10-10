# Review — release 2.3.0

Design: `.agent-rfc/designs/release-2-3-0.md`. Owner request, 2026-10-10: cut the release once #49
(the repair of C7's squash-merged commit) merges.

**Built evidence:** the version is `2.3.0` in `pyproject.toml`, `install-ai-stack.sh` and
`docs/DESIGN.md`'s header; `scripts/test/test_version_consistency.py` passes over all three and the
new `CHANGELOG.md` section, whose one heading is the security contract's Added entry.

## Pass 1 — findings: 1

- `docs-match-behaviour` — **finding:** `docs/PRODUCT_BACKLOG.md`'s "Current state" heading was
  still dated 2026-10-07 under a paragraph naming releases through 2026-10-10. Dated today.

## Pass 2 — findings: 0

The 2.3.0 section against what merged since `v2.2.3` — #48 (the security contract, one Added
heading) and #47 (backlog only), with #49 (a review record) to land before the release commit; the
2.3.x row names the launcher and setup-step pins `process-gate security` needs, what a sync adds, and
the two harness behaviours that change for a tenant running it by path at a 2.3.0 checkout; DESIGN's
mirror shows the current row only, as before; the backlog and the archive say the same; no portal
file changed since `v2.2.3`.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — version strings and records only; one test holds the three declarations together.
Group 2 · Quality / safety — [x] checked — `test_version_consistency.py` over the installer, the package, the design header and the new CHANGELOG section; the contract it carries is reviewed in `.agent-rfc/reviews/security-contract.md`.
Group 3 · Architecture / hygiene — [x] n/a — no code changes in this commit.
Group 4 · Process — [x] checked — design before the version moved; backlog current state dated and C7 marked released; the C7 and release designs marked done; archive entry; the release goes through a pull request merged by rebase and CI, then a tag on the merged commit.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — the 2.3.x row names the pins `process-gate security` needs and the harness behaviours that change for a tenant running it by path.
Group 7 · Auth & session integrity — [x] n/a — the release workflow's signing secrets are unchanged and read by name.

Tests added: none — the existing version pin covers the release.
Mutation-checked: n/a — no logic changed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` — this design's node.
Gates run: full `pytest` on the staged tree (2388 passed, 10 skipped); every gate of the self-test's Python job that runs here — the repo-tree check, `ruff`, py_compile, redaction for both profiles, `--check-hooks`, `--check-kg`, the delivery evidence pack — and `bash -n install-ai-stack.sh`; portal not run — no portal file changed since `v2.2.3`.

Levers reviewed: `declared-vs-enforced`, `docs-match-behaviour`, `two-owners-two-cadences`, `run-the-gates-ci-lists`.

KG query: kg:b9213d40aa46
