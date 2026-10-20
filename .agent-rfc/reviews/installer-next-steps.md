# Review — the installer says how to apply AgentSmith to a repository

Design: `.agent-rfc/designs/installer-next-steps.md`. Found re-running the 3.0.0 installer on the
owner's machine, 2026-10-15, and spun off then. The owner asked after it on 2026-10-20.

**Built evidence:**
- **The installer's step 3** names `agentsmith tenant init <id> --stack <stack>` for a new repository
  and `agentsmith tenant adopt <id>` for an existing one, and says no hook runs on its own.
- **`test_the_installer_says_how_to_apply_agentsmith_to_a_repository`** failed on the line that
  shipped, which names neither command. It passes now.
- **The User Manual's onboarding passages** say the same. The marker and README section they pointed
  to, neither of which exists any more, are gone from them.
- **`docs/DESIGN.md`** says the base eval cases stay with the evals provider.

## Pass 1 — findings: 2

1. `docs-match-behaviour` — **The new step 3 dropped where to run the commands.** Read as bash
   prints it, the block named `tenant init` and `tenant adopt` but no directory. Both act on the
   working directory unless given `--root`, and the old line at least began with
   `cd /path/to/your-project`. **Fix:** step 3 begins with that `cd`.
2. `grep-for-siblings` — **A sweep of every Markdown file for the hook-era onboarding found one more
   outside the manual:** `docs/DESIGN.md` said the framework's base eval cases "are copied once on
   first checkout". Since 3.0.0 `tenant init` seeds no eval dataset. **Fix:** DESIGN says the base
   cases stay with the evals provider, and that a new tenant's judged suites warn until it has cases
   of its own. The design records it.

## Pass 2 — findings: 0

- **The installer:** `bash -n` passes, and the next-steps block, run by bash, prints the `cd` and both
  commands, with `tenant adopt`'s plan-then-`--yes`, the phrasing README uses.
- **The manual and README** no longer mention `.agenticframework/enabled`, "hooks fire automatically",
  the "Opt-in model" section or the runtime "accessed via `$AGENTSMITH_DIR/runtime`". No code reads
  that marker (searched `runtime/`, `scripts/`, `.githooks/` and the installer).
- **Kept on purpose:** the `git init -b main` before `tenant init` in the manual's quick start and
  README, because it creates the repository.
- **Nothing else stale:** the sweep for "first checkout", "opt in", `touch .agenticframework` and
  "on git init/clone" across the docs, CHANGELOG and archive excepted, finds only the
  `no-shared-infra` opt-out, which `agentsmith dashboard start` still reads.

## Sign-off

Group 1 · DRY & shared code — [x] n/a — prose and one block of `echo` lines; the phrasing matches README's and the manual's.
Group 2 · Quality / safety — [x] checked — the new test failed on the shipped line and passes on the fix; `bash -n` on the installer.
Group 3 · Architecture / hygiene — [x] n/a — no code path changes.
Group 4 · Process — [x] checked — design before the change; CHANGELOG Unreleased; worked in a separate worktree from `origin/main`, leaving the main checkout's unpushed commits and untracked file untouched.
Group 5 · Intuitive UI — [x] checked — the installer's last screen tells a user what to run and where, in the order they need it.
Group 6 · Signal integrity — [x] checked — the installer no longer gives an instruction that succeeds and does nothing.
Group 7 · Auth & session integrity — [x] n/a — no credential handling.

Tests added: `scripts/test/test_installer_templates.py::test_the_installer_says_how_to_apply_agentsmith_to_a_repository`.
Mutation-checked: by hand — the shipped `git init` line restored fails the new test.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` — this design's node.
Gates run: `agentsmith gates run` in this worktree — 11 passed: the process gate, ruff, py_compile, the repo-tree check, redaction for both profiles, `--check-hooks`, `--check-kg`, the on-prem templates, the evidence pack, the delivery-model unit tests, `bash -n`/`zsh -n`. Not passed here, each for a reason that is not this change: the mutation step refused uncommitted files, by design, and run again with `--allow-dirty` against `origin/main` it ran `installed_machine` 4/4 caught, the other 31 suites skipped as untouched; the portal's `tsc`, its `npm test` and the widget's `npm test` failed for want of `node_modules` in a fresh worktree, and no portal or widget file changed; mypy skipped, not installed here and scoped to `runtime/`, where nothing changed; nine needed CI's services or context. The gates run's evidence pack wrote a gitignored file that the graph check then mapped as a node; the file was removed and the staged graph restored (spun off as its own fix).

Levers reviewed: `docs-match-behaviour`, `grep-for-siblings`, `test-that-pins-a-defect`.

KG query: kg:4fd2a0048520
