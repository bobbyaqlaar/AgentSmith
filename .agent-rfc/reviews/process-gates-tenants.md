# Review — process gates for tenants (framework side)

Design: `.agent-rfc/designs/process-gates-tenants.md`. Covers the AgentSmith
changes: per-repo config, `@framework/` docs, the `.githooks/process-gate`
launcher, the installer's `review-levers.md` copy. Each tenant's rollout has
its own design and review in that tenant's repo.

Built evidence before review: 13 mutations of the new behaviour (config removed
in CI, config not self-gating, `@framework/` resolved wrong, pre-adoption commits
failed, root commit unchecked, broken config letting edits through, repo levers
ignored, a changelog rule without a declared changelog, session-start speaking
where not adopted, launcher order, launcher fail-open at commit, installer copy)
— 12 caught on the first run.

## Pass 1 — findings: 2

- `test-that-cannot-fail` — the 13th mutation survived: the launcher printing its
  deny but exiting 1 for `pre-edit`. Claude Code ignores a non-zero hook's
  output, so the edit would go through, and the settings fallback would append a
  second JSON document. `test_the_launcher_fails_safe_when_it_finds_no_gate`
  checked the JSON, not the exit code. Now asserts both; the mutation is caught.
- `provenance-and-precedence` — the launcher located the repo from
  `$CLAUDE_PROJECT_DIR` before git. That variable names the Claude Code session's
  project, so a session in AgentSmith committing in OTS would run AgentSmith's
  gate instead of OTS's vendored copy — the opposite of the stated lookup order.
  Now git's toplevel first, `$CLAUDE_PROJECT_DIR` only as a fallback;
  `test_the_launcher_prefers_the_repos_own_copy` sets a decoy project dir and
  fails against the old order. Doc updated to say which repository is meant.

## Pass 2 — findings: 0

Full suite (1240 passed), `ruff check .`, `bash -n` on the hooks and
installer (plus `zsh -n` on the installer), shellcheck on `.githooks/`, SPECS
tree drift, Knowledge Graph and `verify_system.py --check-hooks`. `ci` against
the committed HEAD (which has no config yet) fails with "the gates were
removed" — the intended rule, seen for real. Re-read `docs/process-gates.md`,
CHANGELOG and the backlog entry against the code.
