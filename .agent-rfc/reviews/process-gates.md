# Review — process gates

Design: `.agent-rfc/designs/process-gates.md`. Each pass worked
`docs/review-levers.md` over the whole change (script, hooks, settings, CI job,
tests, docs), and every finding below was reproduced before it was fixed.

Built evidence before review: 18 mutations of the gates and their callers all
caught; the edit gate denied a live edit to `runtime/cli.py` in the session that
built it; every hook command pipe-tested under the system Python 3.9.

## Pass 1 — findings: 2

- `environment-parity` — `git commit --amend` on a gated commit passed the local
  commit gate with no trailers: the staged diff is taken against the commit being
  replaced, so a message-only amend looked like no change. Reproduced in a scratch
  repo (`amend without trailers rc=0`). Fixed: `.githooks/commit-msg` detects
  `--amend` from the parent git process and `commit-msg --amend` diffs from
  `HEAD^`. Test: `test_amending_a_gated_commit_is_checked_like_the_commit_it_replaces`
  (fails with detection removed).
- `grep-for-siblings` — `scratch-tenants.yml` still commits with
  `core.hooksPath=/dev/null`, justified only by post-commit's push, which now has
  an opt-out. Kept the bypass (the commit is machine-built tenant output, checked
  by the tenant's own CI) and rewrote the comment to give that reason.

## Pass 2 — findings: 3

- `docs-match-behaviour` — `docs/process-gates.md` said the commit gate runs on
  "every commit"; rebase picks and cherry-picks run no `commit-msg`. Reworded, with
  CI named as the check that sees them.
- `test-that-cannot-fail` — the CI summary's listing of `n/a` escapes was
  documented and untested. Added `test_ci_lists_every_na_escape_in_its_summary`
  (fails when the listing is removed).
- `guards-must-be-able-to-fail` — the edit gate failed OPEN when the gate could
  not run at all: with `python3` missing or the script dying before it answers,
  the hook command exits non-zero and Claude Code lets the edit through. The
  command now falls back to a deny. Test:
  `test_the_edit_gate_fails_closed_when_the_gate_cannot_run` (fails without the
  fallback).

## Pass 3 — findings: 1

- `docs-match-behaviour` — the docs implied every agent hook fails closed; only
  the edit gate does. The stop hook deliberately does not (a fallback that blocks
  without reading `stop_hook_active` could loop forever). Stated under "Limits".

## Pass 4 — findings: 0

Full suite (1214 passed), `ruff check .`, `bash -n` and shellcheck on the hooks,
YAML parse of both workflows, SPECS tree drift check, Knowledge Graph check and
`verify_system.py --check-hooks` — the Self-Test gate list, run on the final tree.
Re-read the docs, CHANGELOG, design note and session-start text against the code:
no further findings.

On commit, the commit gate itself blocked this change: the design's `scope` did not
cover `.github/workflows/scratch-tenants.yml`, whose comment pass 1 rewrote. Added to
the scope; it belongs to this work.
