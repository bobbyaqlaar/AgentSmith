---
status: done
scope:
  - install-ai-stack.sh
  - scripts/test/test_installer_templates.py
  - .agent-rfc/fixtures/knowledge_graph.json
---
# The installer says how to apply AgentSmith to a repository

## Problem

Found re-running the 3.0.0 installer on the owner's machine, 2026-10-15. Its closing "Next steps" says:

    3. Apply to a project:
       cd /path/to/your-project && git init

Since 3.0.0 (`vendoring-retired`) no hook is armed outside a repository, so `git init` provisions
nothing. A user who follows the installer's last instruction gets a plain repository and no sign that
anything is missing.

The User Manual carries the same pre-3.0.0 model in four places, read on `main` at `b237499`:
- "To apply the framework to any existing repository: `cd /path/to/repo && git init`";
- "New repos opt in on the first `git checkout` … pre-existing/cloned repos opt in explicitly
  (`touch .agenticframework/enabled`, then any checkout) — see README 'Opt-in model'". Nothing reads
  that marker any more, and README has no such section;
- "one hook, one generator, so both onboarding paths get them: a fresh `git init` and an explicit
  opt-in … run the identical `generate-ide-config.py` call";
- `git init -b main   # hooks fire automatically`.

Two more lines in the same table are wrong too:
- the "per-repo opt-out before `git init`/`agentsmith tenant init`" names a command that does nothing;
- the table says `runtime/` is "accessed via `$AGENTSMITH_DIR/runtime` at run time", where a tenant
  whose code imports it pins the `agentsmith-runtime` package (as KYC Sentinel does).

`docs/DESIGN.md` says the framework's base eval cases "are copied once on first checkout". Since
3.0.0, `tenant init` seeds no eval dataset.

## Approach

- **The installer names the two commands that apply AgentSmith:**
  - `agentsmith tenant init <id> --stack <stack>`, for a new repository;
  - `agentsmith tenant adopt <id>`, for an existing one, which prints its plan until `--yes`.

  This is the phrasing README and the User Manual already use.
- **A test holds it.** `test_installer_templates.py` reads the installer's next-steps block: it names
  `agentsmith tenant init` and `agentsmith tenant adopt`, and never offers `git init` as a way to
  apply AgentSmith.
- **The User Manual says the same in each place:**
  - a new repository is scaffolded by `tenant init` and an existing one adopted by `tenant adopt`;
  - no hook runs on `git init` or `git checkout`;
  - the rule files are rendered by the rules provider for both;
  - a tenant whose code imports the runtime pins `agentsmith-runtime`.

  The `git init -b main` before `tenant init` stays, because it creates the repository.
- **`docs/DESIGN.md`** says where the base eval cases are, and what a new tenant starts with.
- **CHANGELOG Unreleased:** `install-ai-stack.sh` is a path a tenant receives.

## Pillars

- P1 applies — `.agent-rfc/designs/installer-next-steps.md` records the stale instruction and every place the manual repeats it before the change.
- P2 n/a — no dependency or architecture change; one block of `echo` lines and prose.
- P3 n/a — no traced code changes.
- P4 applies — `scripts/test/test_installer_templates.py` holds the next steps to the two commands and fails on `git init` offered as the way to apply AgentSmith.
- P7 n/a — no stack-specific rule changes.
- P8 n/a — no telemetry.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 n/a — no untrusted input.
- P12 n/a — no secret is read or printed.
- P13 n/a — no gate changes.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned for this design's node.
- P15 applies — `install-ai-stack.sh` stops giving an instruction that succeeds and does nothing; the manual stops describing a marker nothing reads.
- P16 n/a — text only; reverting the commit restores it.

## Deviations

none

## Dependencies

none

## Levers

- `docs-match-behaviour` — the installer and the manual say what 3.0.0 does.
- `grep-for-siblings` — the manual's four copies of the same stale model are fixed with the installer's.
- `test-that-pins-a-defect` — the new test fails on the line that shipped in 3.0.0.
