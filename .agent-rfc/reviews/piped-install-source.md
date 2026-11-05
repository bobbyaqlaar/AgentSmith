# Review — a piped install installs the release it announces

Design: `.agent-rfc/designs/piped-install-source.md`. Found when the owner ran the README's install line in a 3.0.0 checkout, 2026-11-05.

**Built evidence:**
- Reproduced with the published v4.0.0 installer in empty homes. Inside the checkout: `agentsmith_runtime-3.0.0` from
  `file://…/AgenticFramework`, and "v4.0.0 installed successfully". Outside: 4.0.0 from the verified archive.
- The changed `scripts/check_release_install.sh` fails against the published v4.0.0 installer, at Step 3 on the decoy's missing lock. So
  it catches the defect, and the real release is what it caught it on.

## Pass 1 — findings: 2

1. `test-the-contract` — **`test_a_piped_install_run_inside_a_tenant…` could not fail on this defect:** its directory has no installer
   or gate launcher, so the marker check blanks it either way. **Fix:** `scripts/test/test_release_install.py` pipes inside a directory
   that has both, and a mutation restoring the `$0` fallback is caught.
2. `when-the-fallback-fails` — **A failed Step 9 printed a warning banner and exited 0,** so `check_release_install.sh`'s
   `|| fail` could never see it. Found reading the end of the script. **Fix:** exit 1, tested with a stub command reporting another version.

## Pass 2 — findings: 0

- **Run as a file, a checkout is still a checkout:** tested, and `test_framework_python_env.py`'s older cases still pass.
- **A `+src` version passes,** because `agentsmith/version.py` can report build metadata for a checkout. Tested.
- **macOS's bash 3.2** gives an empty `BASH_SOURCE[0]` when piped, the same as newer bash, so the default applies under `set -u`.
- **The exit comes last,** after the next steps print, so a failed install still shows the errors above it.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — one installer path; nothing duplicated.
Group 2 · Quality / safety — [x] checked — the installer verifies the version it installed and reports failure in its exit status.
Group 3 · Architecture / hygiene — [x] n/a — no dependency or structural change.
Group 4 · Process — [x] checked — design before the fix; CHANGELOG entry; three mutations.
Group 5 · Intuitive UI — [x] checked — the error names both versions and what to do.
Group 6 · Signal integrity — [x] checked — "installed successfully" now means the announced version is what runs.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: `scripts/test/test_release_install.py`.
Mutation-checked: `scripts/mutation_check.py installed_machine`, 11 of 11 caught, including the three new ones.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: `scripts/test/test_release_install.py`, `test_framework_python_env.py`, `test_cli_install.py`, `test_installer_templates.py` (50 passed); ruff; artifacts; `agentsmith gates run` for py_compile, repo-tree, Commit guardrails, check-kg, the release install and bash -n. Portal and widget gates were not run here, as no path of theirs changed; Self-Test runs them, the other mutation suites and the full suite on this commit.

Levers reviewed: `declared-vs-enforced`, `environment-parity`, `when-the-fallback-fails`, `test-the-contract`.

KG query: kg:3674fbf63989
