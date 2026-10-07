# Review — release 2.2.0

Design: `.agent-rfc/designs/release-2-2-0.md`. Owner request, 2026-10-07: cut the release.

**Built evidence:** the version is `2.2.0` in `pyproject.toml`, `install-ai-stack.sh` and
`docs/DESIGN.md`'s header, and `scripts/test/test_version_consistency.py` passes over all three and
the new `CHANGELOG.md` section. Every heading under the old Unreleased section was read to decide
the number and write the compatibility row; the row's claims were measured against the installed
2.1.0 with a scratch tenant declaring both new keys.

## Pass 1 — findings: 2

Each claim in the row checked against what a 2.1.0 install does.

- `docs-match-behaviour` — **finding:** the first draft named two things a tenant will notice (the
  synced `evals` port, and `extends.evals` refused by an older install) and missed a third: a synced
  launcher's `process-gate evals run` asked of a 2.1.0 `agentsmith` — a machine not reinstalled, or
  CI whose setup step still pins `@v2.1.0`. Measured: the old CLI exits 2 on `evals run`, and the
  launcher fails the step saying the provider is older than the evals contract. Added to the row
  and the design.
- `declared-vs-enforced` — **finding:** regenerating the knowledge graph adds this design's node,
  as every design does, and the file sat outside the design's scope — the likely reason 2.1.0's
  release commit was refused for it and shipped with the graph one node short. Scoped in, P14
  answered.

## Pass 2 — findings: 0

The 2.2.x row against each entry in the new 2.2.0 section (the evals contract's hook-interface
change, the scratch tenant and the mutation runner, both AgentSmith's own CI); `docs/DESIGN.md`'s
mirror holds the current row only and says the same; backlog and archive name v2.2.0; no span
attribute added since 2.1.0, so no Wire Contract row; no portal file changed since `v2.1.0`.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — version strings only; one test holds the three declarations together.
Group 2 · Quality / safety — [x] checked — `test_version_consistency.py` over the installer, the package, the design header and the new CHANGELOG section; the row's three claims measured against the installed 2.1.0.
Group 3 · Architecture / hygiene — [x] n/a — no code changes.
Group 4 · Process — [x] checked — design before the version moved; backlog current-state line and C6 row; archive entry; the release goes through a pull request and CI, then a tag on the merged commit.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — the 2.2.x row says what a tenant will notice and that nothing breaks; each claim measured (pass 1), and each failure it names is closed and says why.
Group 7 · Auth & session integrity — [x] n/a — the release workflow's signing secrets are unchanged and read by name.

Tests added: none — the existing version pin covers the release.
Mutation-checked: n/a — no logic changed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` — this design's node.
Gates run: full `pytest` on the staged tree (2289 passed, 10 skipped); `ruff check .`; the self-test's tree and knowledge-graph gates; portal not run — no portal file changed since `v2.1.0`; `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `declared-vs-enforced`, `docs-match-behaviour`, `run-the-gates-ci-lists`.

KG query: kg:5b58e749a021
