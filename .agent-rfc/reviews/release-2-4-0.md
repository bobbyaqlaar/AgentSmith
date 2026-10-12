# Review — release 2.4.0

Design: `.agent-rfc/designs/release-2-4-0.md`. Owner request, 2026-10-12: cut the release, after C8 (#52) merged.

**Built evidence:**
- The version is `2.4.0` in `pyproject.toml`, `install-ai-stack.sh` and `docs/DESIGN.md`'s header.
- `scripts/test/test_version_consistency.py` passes over all three and the new `CHANGELOG.md` section.
- That section's headings are C8's: Added, Security, Deprecated and Removed.

## Pass 1 — findings: 2

Each claim in the 2.4.x row was checked in code.

- `docs-match-behaviour` — **finding:** the row said a sync refreshes the CD templates a tenant has not edited, which would
  drop their history and Phoenix-feedback steps. It does not: `runtime/sync.py` refreshes only the gates and sync
  workflows, and the vendored upgrade copies `templates/`, never a tenant's `.github/workflows/`. **Fix:** the row now says
  a tenant's CD files are its own. The steps leave the templates new tenants get, and an existing tenant drops them when it
  moves. The design says the same.
- `failure-mode-visibility` — **finding:** the row did not say that a replay webhook which answers with a redirect no longer
  gets the replay (C8's Security fix). A tenant whose `http` URL is sent on to `https` would see replays fail.
  **Fix:** the row and DESIGN's mirror name it and say what to do.

Confirmed and kept:
- A 2.3.x replay webhook reads only `taskId` and `payload` and already checks `X-Replay-Signature-V2`, so the request's new
  `schema` field changes nothing for it.
- The history route ignores, not refuses, the old script's replay fields.
- `upsertTenant` keeps a stored replay URL (`COALESCE`).
- A worker on the shared token says once that its route is deprecated (`legacy-run-status`).

Made while building, before this pass: the Wire Contract table's Ops ingest row is dated 2.4.0 (it said "Unreleased"),
and a stray blank line that split C8's Security list is gone.

## Pass 2 — findings: 0

Checked the corrected row and the 2.4.0 section against what merged since `v2.3.0`: #52 (the Ops contract, in two commits,
the contract and its mypy fix) and `9cb0646` (backlog only).

The row's "nothing stops working" was checked in code, not assumed:
- A vendored tenant keeps its `scripts/sync-portal-history.py`. The upgrade merges trees (`_copy_tree_merge`) and deletes none.
- The four `_shared.py` helpers that script imports are all still defined.
- OTS and oil-price-demo run it in CD, and the route it posts to stays served while the portal keeps
  `OPS_PORTAL_SYNC_TOKEN`.
- No tenant workflow calls `--check-history-sync`.
- The migration only adds the `scope` column, so a replay URL and key already stored survive it.

DESIGN's mirror shows the current row only, as before. The backlog, the archive and the C8 design's `done` status agree.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — version strings and records only; one test holds the three declarations together.
Group 2 · Quality / safety — [x] checked — `test_version_consistency.py` over the installer, the package, the design header and the new CHANGELOG section; the contract it carries is reviewed in `.agent-rfc/reviews/ops-contract.md`.
Group 3 · Architecture / hygiene — [x] n/a — no code changes in this commit.
Group 4 · Process — [x] checked — design before the version moved; backlog current state dated and C8 marked released; the C8 design marked done; archive entry; the release goes through a pull request merged by rebase and CI, then a tag on the merged commit.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — the 2.4.x row names what a tenant on the shared token and the portal's operator will notice, and the migration.
Group 7 · Auth & session integrity — [x] checked — the row tells an operator the replay key is issued in the portal and never read from `tenant.yaml`, and when to unset the shared token; the release workflow's signing secrets are unchanged and read by name.

Tests added: none — the existing version pin covers the release.
Mutation-checked: n/a — no logic changed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` — this design's node.
Gates run: full `pytest` on the staged tree (2410 passed, 10 skipped), and the KG and version tests again on the final graph fixture (40); every gate of the self-test's Python job that runs here — the repo-tree check, `ruff`, `mypy` (1.14.1, Python 3.11 with `requirements.lock`), py_compile, redaction for both profiles, `--check-hooks`, `--check-kg`, the delivery evidence pack — and `bash -n install-ai-stack.sh`; portal not run — no portal file changed since #52, whose CI built and tested it.

Levers reviewed: `declared-vs-enforced`, `docs-match-behaviour`, `two-owners-two-cadences`, `failure-mode-visibility`, `run-the-gates-ci-lists`.

KG query: kg:5298c0de9652
