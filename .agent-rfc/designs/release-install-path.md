---
status: done
scope:
  - install-ai-stack.sh
  - scripts/build_release_assets.sh
  - scripts/check_release_install.sh
  - scripts/test/test_release_install.py
  - scripts/test/test_release_artifact_contract.py
  - scripts/test/test_installer_templates.py
  - scripts/test/test_framework_python_env.py
  - scripts/mutation_check.py
  - .github/workflows/release.yml
  - .github/workflows/self-test.yml
  - docs/validation-checklist.md
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Installing from a release takes the path a checkout takes

## Problem

Run on 2026-11-03 exactly as the README says, with a throwaway `HOME` and no checkout of AgentSmith:
`curl … install-ai-stack.sh | bash`, then `tenant init` or `tenant adopt`, then the commit they print.

- **The first commit is refused**, on both paths: "`## Levers` cites no lever from the gate provider's
  docs/review-levers.md". The installer warned that it had not installed the docs.
- **`process-gate security check` crashes** with `FileNotFoundError`: no `fixtures/security/`.
- **Re-running `curl | bash` never upgrades.** Each step's "already present" branch keeps the old
  `scripts/`, hooks and templates.

The installer has two paths. A checkout copies every directory it needs. Everything else downloads
four of them piecemeal, warns about the rest and carries on, exit 0: "until this machine clones the
repo and re-runs". The README's Quick Start is the second path, and no CI job runs it. The Scratch
tenants workflow installs from a checkout, and `test_release_artifact_contract.py` holds only that the
assets the installer names are built. The backlog's "the release install works for anyone" rested on
a 200 from the URL and a checksum.

## Approach

- **One path.** The release publishes `agentsmith-source.tar.gz`, the tagged tree by `git archive`,
  with its checksum. Outside a checkout, the installer downloads the archive of **its own version**,
  verifies it, unpacks it to a temporary directory and sets `INSTALLER_DIR` there. Every later step is
  the one a checkout runs, which the scratch tenants exercise on every change.
- **A failed or corrupt download stops the install**, exit 1, naming the URL, before anything is
  written. A half-install reported as success is what this fixes.
- **The fallbacks go:** the piecemeal downloads, the warnings, the "already present" branches, the
  heredoc copies of the base fixtures, and the `scripts`, `githooks`, `workflow-templates`, `templates`
  and `requirements.lock` assets. So a re-run upgrades.
- **Installer and payload cannot disagree.** They come from one tag, at the version the installer
  declares, including when someone pins an older release's URL.
- **`scripts/build_release_assets.sh`** builds the assets, for the release and for the check below, so
  what is tested is what ships.
- **`scripts/check_release_install.sh <release-url>`** is the stranger's path, end to end: fetch the
  installer into an empty directory, verify it, install into a throwaway `HOME`, `tenant init` and its
  printed commit, `tenant adopt` and its printed commit, then ask each port for an answer. It runs:
  - in Self-Test, inside the required Python job, against assets built from the commit under test;
  - in `release.yml`, after publishing, against the real URL, so a broken release shows red at once.
- **Mirrors and CI** set `AI_STACK_RELEASE_BASE`, beside the existing `AI_STACK_FRAMEWORK_REPO`.

**Deliberately not here:** the first-run experience of a red security job, a separate change.

## Pillars

- P1 applies — `.agent-rfc/designs/release-install-path.md` records the reproduction before the change.
- P2 applies — `scripts/build_release_assets.sh` is the one place assets are built, and `install-ai-stack.sh` loses a whole second install path; no dependency is added.
- P3 n/a — an installer and CI scripts; no traced service path.
- P4 applies — `scripts/check_release_install.sh` drives the real path in CI, and `scripts/test/test_release_install.py` holds the failed download and the bad checksum against the real installer.
- P7 n/a — shell and YAML; no stack-specific rule applies.
- P8 n/a — no telemetry.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 applies — `install-ai-stack.sh` verifies the archive's checksum before unpacking what it downloaded, and fails closed on a mismatch.
- P12 n/a — no secret is read; the archive is `git archive` of tracked files, so no `.env` can enter it.
- P13 applies — `.github/workflows/self-test.yml` runs the check inside the required Python job, so it gates a merge with no branch-protection change.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated for the new files.
- P15 applies — `install-ai-stack.sh` no longer exits 0 on an install that cannot work; a missing download is an error, not a warning.
- P16 applies — a failed download writes nothing and names the URL and the alternative (a checkout, or `AI_STACK_RELEASE_BASE`); a broken published release can be re-cut, because `release.yml`'s verify job shows it at once.

## Deviations

none

## Dependencies

none

## Levers

- `when-the-fallback-fails` — the fallback path was the one users take, and nothing ran it.
- `guards-must-be-able-to-fail` — the old contract test held asset names; the new check fails when a stranger's first commit does.
- `environment-parity` — the path CI tests is the path a release takes.
- `failure-mode-visibility` — a half-install no longer reports success.
