# Review — release 4.0.0

Design: `.agent-rfc/designs/release-4-0-0.md`. Owner request, 2026-11-03: rename the package, launch in two stages.

**Built evidence:**
- The version is `4.0.0` in `pyproject.toml`, `install-ai-stack.sh` and `docs/DESIGN.md`'s header, and
  `scripts/test/test_version_consistency.py` passes over all three and the new `CHANGELOG.md` section.
- Self-Test and the scratch tenants were green on `0a1637b`, the rename's merged commit.
- A throwaway repository adopted with the v3.0.1 tree and committed as the gate instructs: its sync workflow's own step
  fails against this tree with `No module named 'runtime'`, and `agentsmith sync` from this tree rewrites that line.
  A first try that edited the file by hand proved nothing, since `sync` leaves an edited file alone.

## Pass 1 — findings: 3

1. `two-owners-two-cadences` — **A 3.x `agentsmith-sync.yml` fails as soon as 4.0.0 is the latest release, and cannot repair
   itself,** because it checks out the latest tag and runs `-m runtime.cli`. The rename's review and its changelog said a
   pinned tenant "keeps working until it moves". **Fix:** the 4.0.x row and its mirror name the failure and the command, the
   sentence is corrected, and `package-agentsmith` carries the correction. No shim: KYC Sentinel and OTS do not hold this
   file, the scratch tenants hold the new line, and the repository has no forks. The missing upgrade test goes on the backlog.
2. `docs-match-behaviour` — **The rename's text rewrite left two wrong lines in live documents:** backlog step 5 read "Rename
   `agentsmith` to `agentsmith`", and `CHANGELOG.md`'s preamble named `runtime/version.py`. **Fix:** both corrected.
3. `docs-match-behaviour` — **`contract/intake/v1/record.schema.json` still named `runtime/cli.py`,** found sweeping live text
   for more of finding 2. It is a description, and nothing pins that file by hash. **Fix:** the path, and the design's scope.

## Pass 2 — findings: 0

- **The sweep over live text** finds `runtime/` only in the required job label `Python scripts/runtime/examples`, kept on
  purpose, and the README's sentence about what pre-3.0.0 installs did.
- **The row's "changes nothing but its pin"** was read against what `sync` changed on the v3.0.1 repository: rule files, one
  hook comment and the sync workflow. KYC's and OTS's workflows contain no `-m runtime` or `/runtime/` path.
- **A major is the right size:** a stale import has no shim. The backlog does not tick step 5, because the release and KYC's
  move have not happened in this commit.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — version strings and records.
Group 2 · Quality / safety — [x] checked — `scripts/test/test_version_consistency.py` holds the versions together; `verify-published-release` runs after publishing.
Group 3 · Architecture / hygiene — [x] n/a — no dependency or structural change.
Group 4 · Process — [x] checked — design before the bump; CHANGELOG section and row; archive and backlog; four shipped designs marked done.
Group 5 · Intuitive UI — [x] n/a — no screen or message changes.
Group 6 · Signal integrity — [x] checked — the backlog claims no verification that has not run, and the false changelog sentence is corrected.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: none — `scripts/test/test_version_consistency.py` already covers a release; the upgrade test is on the backlog.
Mutation-checked: n/a — no code changes.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `agentsmith gates run` for every gate that runs here on this tree: py_compile, repo-tree, Commit guardrails, check-kg, the release install, bash -n, portal tsc and tests, widget tests; ruff; artifacts; `test_version_consistency.py`, the record, package-name and release contract tests (91 passed). Skipped here and run by Self-Test: mutations, which refuse an uncommitted `install-ai-stack.sh`, and the service-backed gates. The full suite did not run on this tree; Self-Test runs it on this commit.

Levers reviewed: `two-owners-two-cadences`, `docs-match-behaviour`, `when-the-fallback-fails`.

KG query: kg:4825eb9061ea
