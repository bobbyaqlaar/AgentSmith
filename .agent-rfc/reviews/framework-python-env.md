# Review — a Python environment AgentSmith owns (slice A)

Design: `.agent-rfc/designs/framework-python-env.md`. Reviewed against
`docs/review-levers.md`, scoped by what the branch ships: the installer's
Steps 1, 3, 7 (Phoenix fallback) and 9, both hooks, Self-Test, release.yml, the
catalog, the lock and `.python-version`.

Built evidence before review:
- the real installer on this Mac: `uv venv` fetched CPython 3.11.15 and
  `uv pip sync --require-hashes` installed the lock; Step 9 imported
  yaml/networkx/httpx/opentelemetry from `~/.agent-framework/.venv`; the
  environment also imports `jsonschema` and `langgraph`;
- the pip rung for real: `python3 -m venv` on Homebrew 3.14 +
  `pip install --require-hashes -r requirements.lock` succeeded, so the
  universal lock installs on an interpreter other than the one it was compiled
  for;
- full suite 1259 passed, `ruff check .`, `bash -n`/`zsh -n`, SPECS tree
  drift, `verify_system.py --check-hooks` and `--check-kg`;
- 6 mutations of the new behaviour (unhashed sync, no rebuild on a version
  change, reusing any file as the lock, verifying with the system python,
  inverted hook fallback, a failed pip rung continuing) — 5 caught.

## Pass 1 — findings: 5

- `test-that-cannot-fail` — the 6th mutation survived: removing the pip rung's
  `exit 1` let a failed fallback build report "Framework environment ready"
  and continue. No test drove a failing pip. Added
  `test_a_failed_pip_fallback_stops_the_install`; the mutation is caught.
- `grep-for-siblings` / `validate-on-the-receiving-side` — moving
  `INSTALLER_DIR` up exposed that, piped (`curl … | bash`), it resolves to the
  CURRENT directory (`$0` is `bash`; reproduced from inside KYC Sentinel:
  `dir=/…/KYC_Sentinel`). Every `[ -d "$INSTALLER_DIR/scripts" ]` sibling then
  copies the tenant's own `scripts/` over the framework's; the new lock step
  would have installed a tenant's `requirements.lock`. Pre-existing for
  `scripts/`, `runtime/`, `fixtures/`, hooks. Now a checkout is recognised only
  by its own `install-ai-stack.sh` and `hooks/post-checkout`; the lock's
  `--python-version` header is also required after it is sourced. Two tests
  (piped from a tenant → empty; run as a file in the checkout → the checkout);
  mutating the guard away fails the first.
- `environment-parity` — Self-Test's `security` job still installs
  `requirements.txt` through the tenant-facing `eval-security.yml` /
  `install-python-deps`. Not changed — that action is a tenant contract and a
  tenant has no lock — recorded in FIXES_AND_CLEANUP.md with a trigger.
- `minimal-host-dependency` — the installer header claims Windows via Git
  Bash; a native Windows venv puts the interpreter at `Scripts/python.exe`,
  which neither the installer nor the hooks look for. No Windows runner to
  verify a fix against, so recorded in FIXES_AND_CLEANUP.md rather than adding
  an untested branch.
- `docs-match-behaviour` — the design called uv → pip → failure a fallback
  ladder; the installer picks the rung by what is installed, and a failed uv
  build stops rather than trying pip (which would fail on the same cause). The
  design now says so. CHANGELOG also gained the `INSTALLER_DIR` fix.

## Pass 2 — findings: 2

Re-ran ShellCheck (warning severity, as Self-Test) on the installer and both
hooks — 0, same as HEAD — and confirmed the installed `~/.git_templates/hooks`
carry the `AF_PYTHON` resolution.

- `test-the-contract` — `test_run_from_a_checkout_the_checkout_is_the_installer_dir`
  wrote a probe script into the repository under test and deleted it in a
  `finally`: an interrupted run leaves a stray file for SPECS drift and the
  process gates to trip over, and it only ever proved the positive case. It now
  builds a fake checkout in `tmp_path` and checks both a directory with the
  installer and `hooks/post-checkout` (recognised) and one without (not).
- `docs-match-behaviour` — FIXES_AND_CLEANUP.md's "Local gates do not match
  Self-Test" still read as if nothing pinned the interpreter. It now says the
  checkout carries `.python-version` and the lock, and how to build a matching
  local environment from them.

## Pass 3 — findings: 0

Full suite (1263 passed), `ruff check .`, SPECS tree drift, `bash -n`/`zsh -n`,
`verify_system.py --check-hooks` and `--check-kg`. Re-read the diff of both
hooks, Self-Test, release.yml and the gate config against the design; re-read
CHANGELOG, OPERATIONS.md §0, UserManual.md §1, SPECS.md's tree and the two new
FIXES_AND_CLEANUP.md entries against the installer as built.
