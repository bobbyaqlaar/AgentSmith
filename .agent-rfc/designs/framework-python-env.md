---
status: done
scope:
  - install-ai-stack.sh
  - requirements.txt
  - requirements.lock
  - .python-version
  - hooks/post-commit
  - hooks/post-checkout
  - scripts/generate-ide-config.py
  - .github/workflows/self-test.yml
  - .github/workflows/release.yml
  - .agenticframework/process-gates.json
  - scripts/test/test_framework_python_env.py
  - scripts/test/test_process_gate.py
---
# A Python environment AgentSmith owns (slice A)

## Problem

`install-ai-stack.sh` Step 3 runs `python3 -m pip install` against whatever
`python3` is first on PATH. Verified on this Mac, 2026-09-14:

1. **It installs into an interpreter it does not own.** `python3` is Homebrew's
   3.14, which is externally managed (PEP 668), so the install only succeeds on
   the `--break-system-packages` retry. The next `brew upgrade python` moves to a
   new site-packages and the framework's dependencies are gone.
2. **Three dependency catalogs, drifted.** Step 3 has its own `PACKAGES` list;
   CI installs `requirements.txt`; `pyproject.toml` declares the runtime. Step 3
   still installs `prophet` (removed from `requirements.txt` on 2026-07-11) and
   misses `jsonschema` (the security harness needs it). `requirements.txt` caps
   `arize-phoenix<5`; Step 3 is uncapped and this Mac has 17.9.0.
3. **No reproducibility.** `~/.agent-framework/requirements.lock` is a
   `pip freeze` of the whole system interpreter — 202 lines, most of them other
   software's — written after the fact, read by nothing.
4. **Interpreter version differs from CI.** CI runs 3.11 (five `setup-python`
   steps); machines run whatever is installed (3.14 here, where mypy already
   disagreed with CI).
5. **Hooks use bare `python3`.** `hooks/post-commit` and `hooks/post-checkout`
   run `map_codebase.py` (needs `networkx`) and `generate-ide-config.py` (needs
   `pyyaml`) with whatever `python3` the calling process sees — a GUI git client
   or Claude Code's desktop app may see a different one than the terminal. The
   KG refresh is `|| true`, so a missing `networkx` fails silently.
6. **Unused dependencies.** Nothing imports `arize-phoenix` (it is a server,
   launched as a process), the three `openinference-instrumentation-*` packages,
   or `langchain-community`. Phoenix alone pulls a large tree into every CI run.
7. **The standalone Phoenix fallback is already broken.** `ai-dashboard-start`
   runs `python3 -m phoenix.server.main launch`; the Phoenix Step 3 actually
   installs (17.9.0) has only `serve` and `db` subcommands, and `launch` exits
   with a usage error — in the background, where nobody sees it.

## Approach

One catalog, one lock, one interpreter version, one environment the framework
owns.

- **Catalog.** `requirements.txt` stays the single list of what the framework's
  scripts and tests import (it is what CI installs). Drop `arize-phoenix`,
  `openinference-instrumentation-*` and `langchain-community`. Step 3's
  `PACKAGES` array is deleted.
- **Interpreter version.** New root `.python-version` = `3.11`, the version CI
  tests. uv reads it natively; Self-Test's `setup-python` steps read it through
  `python-version-file`, so the number exists once.
- **Lock.** New root `requirements.lock`, compiled by
  `uv pip compile requirements.txt --universal --python-version 3.11
  --generate-hashes -o requirements.lock` (the command is recorded in the
  file's header). Pinned and hashed, installable by both uv and pip. CI's two
  `pip install -r requirements.txt` steps install the lock instead, so CI and
  every machine get the same versions. A test checks every direct requirement in
  `requirements.txt` is pinned in the lock within its range — stable, unlike
  re-resolving against today's index.
- **Environment.** Step 3 builds `~/.agent-framework/.venv`:
  Which rung runs is decided by what the machine has, not by the previous rung
  failing: a failed uv build stops the install with its output, because the
  pip rung would fail on the same cause (usually the network).
  - uv on PATH: `uv venv --python <the lock's version>` (uv fetches a managed
    CPython if none matches — independent of Homebrew), then
    `uv pip sync requirements.lock`, which also removes anything not in the lock.
  - no uv, `python3` ≥ 3.11: `python3 -m venv`, then
    `pip install --require-hashes -r requirements.lock`. Same versions,
    possibly a different interpreter patch level; the installer says so.
  - neither: fail with the two ways to get uv (`brew install uv`, or astral's
    documented installer) — the installer never pipes a download into a shell.
  - The lock is copied into `~/.agent-framework/`; a piped install downloads
    it as a release asset (`release.yml` ships it). The Python version is read
    from the lock's own header (`--python-version`), so the installer needs one
    file and the lock and interpreter cannot disagree; a test pins that header
    to `.python-version`. An older install's `pip freeze` at the same path has
    no such header and is never reused.
  - System Python is never written to; nothing already installed there is
    removed (it is not ours to remove).
- **Hooks.** `post-commit` and `post-checkout` resolve
  `AF_PYTHON="$HOME/.agent-framework/.venv/bin/python"`, falling back to
  `python3` when the environment is absent (a machine installed before this
  change). Only these two need third-party packages; `pre-commit`'s
  `check_bare_except.py` and `.githooks/process-gate` are stdlib-only and keep
  `python3`. A test parses both hooks and requires the identical resolution.
- **Phoenix, standalone fallback.** The shell block's no-Docker fallback in
  `ai-dashboard-start` launches `uvx --from arize-phoenix phoenix serve`
  (isolated, same "latest" as the Docker image) instead of
  `python3 -m phoenix.server.main`; `ai-dashboard-stop` matches either process.
  Slice B replaces the shell block entirely. The block's other `python3
  scripts/…` calls keep using the system interpreter until then — slices A and
  B are pushed together.
- **Verification step.** Step 9 checks the environment imports `yaml`,
  `networkx`, `opentelemetry.sdk` and `httpx`, instead of `import phoenix` on
  the system interpreter.
- **Gate config.** `requirements*.lock` and `.python-version` become gated paths.
- **Docs.** OPERATIONS.md §0, UserManual.md install, SPECS.md tree, README
  install note, CHANGELOG [Unreleased], FIXES_AND_CLEANUP.md.

Out of scope (slice B, `.agent-rfc/designs/agentsmith-cli.md`): the shell
functions, the `agentsmith` command on PATH, mode state.

## Levers

- `one-catalog` — three dependency lists become one (`requirements.txt`) plus its lock; the installer's own array is deleted.
- `single-source-of-truth` — the interpreter version lives in `.python-version`, read by uv and by `setup-python`.
- `environment-parity` — CI and machines install the same lock at the same Python minor version.
- `minimal-host-dependency` — the environment no longer depends on Homebrew's Python surviving an upgrade; uv is preferred, a stock `python3 -m venv` is the fallback.
- `when-the-fallback-fails` — uv, else venv+pip, else a named failure; a failed build on either rung stops the install with its output, never a half-built environment reported as ready.
- `failure-mode-visibility` — the verification step imports what the hooks need from the environment the hooks use.
- `pin-unremovable-duplicates` — the interpreter resolution is duplicated across two standalone hook files; a test parses both.
- `no-redundant-artifacts` — unused dependencies and the whole-system `pip freeze` go.
- `implemented-not-invoked` — the hooks and Self-Test actually use the environment and the lock, not only the installer.
