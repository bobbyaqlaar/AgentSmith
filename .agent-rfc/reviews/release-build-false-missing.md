# Review — the release build reports a file missing only when it is

Design: `.agent-rfc/designs/release-build-false-missing.md`. Found tagging `v3.0.1`: run 41775217052's first attempt failed at the
build step. Its second attempt, on the same commit, published the release.

**Built evidence:**
- `scripts/build_release_assets.sh` reads the listing from a here-string.
- `scripts/test/test_release_artifact_contract.py` builds with a stub `tar`, in both directions: a long listing whose names come
  first, and a listing with one name absent.
- `installed_machine` gains two mutations, and is 8/8.

## Pass 1 — findings: 1

1. `environment-parity` — **ruff refused `subprocess.run` with no `check`.** **Fix:** `check=False`, since the test reads the code.

## Pass 2 — findings: 0

- **The new test can fail:** the mutation restoring the pipe is caught on every run, because the listing is longer than a pipe
  buffer. The test does not depend on the timing the release hit.
- **The published assets are sound:** the old check could only fail falsely. A pass still meant every name was in the archive, so
  re-running on the tag was safe, and `verify-published-release` then passed on the real URL.
- **No other script shares the shape:** the other `pipefail` scripts piping into `grep -q` or `head` pipe a line or two, in one write.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — a one-line correction.
Group 2 · Quality / safety — [x] checked — `scripts/test/test_release_artifact_contract.py` holds both directions, and two mutations prove it.
Group 3 · Architecture / hygiene — [x] n/a — no dependency or structural change.
Group 4 · Process — [x] checked — design before the fix; CHANGELOG Unreleased; backlog step ticked now the published release has passed.
Group 5 · Intuitive UI — [x] checked — the message names a missing file only when one is missing.
Group 6 · Signal integrity — [x] checked — a broken pipe no longer becomes a claim about the archive.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: `test_a_name_found_early_in_a_long_listing_is_not_reported_missing`, `test_a_name_really_absent_from_the_listing_is_still_reported`.
Mutation-checked: `installed_machine` 8/8.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: ruff, `installed_machine`, the release and tree tests, and the gates below on the staged tree; `check_release_install.sh` on the published v3.0.1 URL from a Mac.

Levers reviewed: `guards-must-be-able-to-fail`, `failure-mode-visibility`, `environment-parity`.

KG query: kg:3dbe29f52930
