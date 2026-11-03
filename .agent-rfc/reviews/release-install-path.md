# Review — installing from a release takes the path a checkout takes

Design: `.agent-rfc/designs/release-install-path.md`. Found 2026-11-03 running the README's Quick Start
for the launch; the owner asked for the fix the same day.

**Built evidence:**
- **`install-ai-stack.sh`:** outside a checkout it fetches `agentsmith-source.tar.gz` of its own version,
  verifies it, unpacks it and sets `INSTALLER_DIR`. Fifteen fallback branches are gone.
- **`scripts/build_release_assets.sh`** builds the assets for `release.yml` and for the check.
- **`scripts/check_release_install.sh`** runs the Quick Start in an empty `HOME`: 45 seconds on built assets.
- **`self-test.yml`** runs it in the required Python job; **`release.yml`** runs it on the published URL.

## Pass 1 — findings: 2

1. `guards-must-be-able-to-fail` — **Two curated mutations survived:** a failed download that carries
   on, and a checksum mismatch that carries on. The installer's later steps fail anyway, so a test of
   "exit 1 and nothing installed" could not tell the first guard from a stumble further on, and a
   corrupt non-archive fails at unpacking regardless. **Fix:** the checksum test uses a valid archive
   behind a wrong checksum and asserts "downloaded and verified" never prints; the download test
   asserts it stops before the checksum step. `installed_machine` 6/6.
2. `test-the-contract` — **`test_release_artifact_contract.py` read a workflow's text** (a regex over
   `tar -czf`), which is how it missed this: every asset it named existed, and the install still could
   not work. **Fix:** it runs the real build and reads the real archive, including that it holds only
   tracked files.

## Pass 2 — findings: 0

- **The new check can fail:** against the published v3.0.0 it reports "the installer reports a partial
  install", exit 1. Against assets built from this tree it passes.
- **The first commits:** both `tenant init`'s and `tenant adopt`'s printed commands run as printed, and
  the gate takes them. The security port answers with its placeholder failures, not a traceback.
- **Nothing else fetches the retired assets:** `git grep` for them in `scripts/`, `runtime/`, `docs/` and
  `.github/` finds only this change's own guard and DESIGN's history.
- **Compatibility:** a 3.0.0 installer script fetches `latest`, finds the old assets gone and reports it.
  The CHANGELOG says so, and the documented one-liner fetches the current installer.
- **No secret can ship:** `git archive` takes tracked files; a test holds it.

## Pass 3 — findings: 2

1. `environment-parity` — **The full suite failed `test_design_tree_drift.py`:** the two new scripts were not in
   `docs/DESIGN.md`'s tree. **Fix:** listed. 11 passed.
2. `environment-parity` — **ruff failed on two lines in the mutation catalogue**, longer than the limit. **Fix:** the
   anchor starts at `exit 1`, which is still unique in the installer; `installed_machine` re-run in the full pass.

## Pass 4 — findings: 0

- **The final scripts re-read:** `install-ai-stack.sh`'s only `trap` is the fetch block's, so the temporary source
  outlives every later step and is removed on every exit. `scripts/check_release_install.sh` fails on each step it names.
- **All 255 mutations caught,** one of them on a second run: `hook_payload`'s "EOF is not noticed" read as a survivor
  because I ran `mutation_check.py --list` during the run, and `--list` recovers the journal, restoring the file under
  mutation. Run alone, the suite is 5/5. The runner's defect is in the backlog.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one install path and one build script, each previously two.
Group 2 · Quality / safety — [x] checked — `test_release_install.py`, the rewritten contract test, `check_release_install.sh` end to end; `installed_machine` mutations 6/6.
Group 3 · Architecture / hygiene — [x] checked — no dependency added; about a hundred lines of fallback removed from the installer.
Group 4 · Process — [x] checked — design before code; CHANGELOG Unreleased; the generated gates table; a separate worktree from `origin/main`.
Group 5 · Intuitive UI — [x] checked — a failed install says what failed, names the URL, says nothing was installed, and offers the alternative.
Group 6 · Signal integrity — [x] checked — an install that cannot work now exits 1 instead of 0; a broken published release shows red.
Group 7 · Auth & session integrity — [x] n/a — no credential handling; the archive is verified before it is unpacked.

Tests added: `scripts/test/test_release_install.py`; `scripts/test/test_release_artifact_contract.py` rewritten over a real build.
Mutation-checked: `mutation_check.py --changed-since origin/main`: 255 mutations, all caught (`installed_machine` 6/6).
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: full suite 2470 passed, 1 failed then fixed (Pass 3); `agentsmith gates run` for py_compile, repo-tree, Redaction, Commit guardrails, check-kg, On-prem, evidence pack, bash -n; ruff, mypy; `check_release_install.sh` on assets built from this commit. Portal and widget gates not run: no path of theirs changed.

Levers reviewed: `when-the-fallback-fails`, `guards-must-be-able-to-fail`, `environment-parity`, `failure-mode-visibility`, `test-the-contract`.

KG query: kg:693e4d51faac
