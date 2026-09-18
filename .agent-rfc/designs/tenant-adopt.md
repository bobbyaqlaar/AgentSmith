---
status: done
scope:
  - runtime/adopt.py
  - runtime/cli.py
  - runtime/architectures.py
  - scripts/process_gate.py
  - .githooks/chain
  - .githooks/commit-msg
  - .githooks/pre-commit
  - .githooks/pre-push
  - hooks/post-checkout
  - workflow-templates/agentsmith-gates.yml
  - scripts/test/test_tenant_adopt.py
  - scripts/test/test_hook_chain.py
  - scripts/test/test_scaffold_review.py
  - scripts/test/test_installed_runtime_tenant.py
  - scripts/test/test_process_gate.py
  - scripts/mutation_check.py
  - runtime/test/test_architectures.py
  - .agent-rfc/fixtures/knowledge_graph.json
---
# An existing repository comes under the gates without losing what it has

## Problem

`agentsmith tenant init` is built for an empty repository. Run on one that has history, code and
tooling of its own (checked in a scratch copy of such a repository, 2026-09-18), it:

1. prints a first commit the gate then refuses — `Review: n/a: generated scaffold` is accepted
   only on a root commit;
2. gates nothing of the existing code — the globs are the scaffold layout's (`app/**`, …);
3. leaves an existing `.claude/settings.json` untouched, so the edit gate never reaches the agent;
4. leaves an existing `CLAUDE.md` / `AGENTS.md` untouched, so the rules never reach the agent;
5. points `core.hooksPath` at `.githooks` unconditionally, silently disarming whatever hooks the
   repository already ran (husky, pre-commit, lefthook, or the machine's own);
6. writes `ci-<stack>.yml` and six more workflows beside the repository's own CI;
7. records no architecture, because `docs/DESIGN.md` is left alone.

Point 5 is also the cause of a bug `tenant init` has had since G7: the machine's hooks live in
`.git/hooks`, `.githooks` has no `post-checkout`, so vendoring never runs, the generated CI's
`scripts/*.py` steps fail, and the "run `git checkout`" hint the command prints does nothing. The
review that found it: `.agent-rfc/reviews/tenant-architecture.md` › Pass 2.

## Approach

### `agentsmith tenant adopt ID`

A separate command, because the questions differ: `init` decides a layout; `adopt` has to find
one. Options: `--stack`, `--architecture`, `--agentic`, `--gate GLOB` (repeatable; replaces what
detection found), `--framework-ref`, `--root`, `--yes`.

**Detect first, write nothing, report.** It refuses a repository with no commit (that is `init`),
one that already carries `.agenticframework/process-gates.json`, and the framework's own checkout.
Otherwise it prints what it found and what it would do:

- **stack** — from `package.json`, `go.mod`, `pyproject.toml` / `requirements*.txt` / `Pipfile`;
- **gated globs** — from `git ls-files`: every top-level directory holding a tracked source file
  of that stack becomes `<dir>/**`, a source file at the root becomes `*.<ext>`, plus the
  framework's always-gated paths;
- **prior hooks** — `core.hooksPath` if set to anything but `.githooks`, else `.git/hooks` if it
  holds anything but samples;
- **existing** rule files, IDE hook configs, workflows and `docs/DESIGN.md`, each with what will
  happen to it (created, merged, left alone);
- warnings it cannot fix: a `prepare` script that re-points `core.hooksPath` (husky), an
  uncommitted working tree.

Then it asks. Without a terminal it needs `--yes`, and without one it exits 2 having written
nothing.

**Merge, never skip, never overwrite.**

- IDE hook configs through `gate_ides.render_config(ide, existing)`, which keeps what the file
  holds besides hooks. A Cursor config the repository already has is left alone and reported.
- Rule files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`,
  `.github/copilot-instructions.md`) are generated into a temporary directory; one the repository
  lacks is copied in, one it has gets the generated rules appended between
  `<!-- agentsmith:rules:begin -->` and `<!-- agentsmith:rules:end -->` — replaced, not appended
  again, on a re-run.
- `docs/DESIGN.md`: written if absent; if present, `## Architecture (target)` is appended when it
  has none — the chosen style as the direction the code moves in, since existing code may not
  follow it yet. Its paths start at the repository's one source directory when detection found
  exactly one, else at the stack's default.
- `.agenticframework/tenant.yaml` if absent, and `process-gates.json` with the detected globs and
  the three extra modes `off`, as `init` does.

**Their CI is left alone.** Adopt writes one workflow, `.github/workflows/agentsmith-gates.yml`:
the process gate over the pushed range and the record to the portal. The repository has no
vendored `scripts/`, so the workflow checks out AgentSmith at `--framework-ref` (default
`v<installed version>`) with the `AGENTSMITH_READ_TOKEN` secret and runs the gate from there. An
adopted repository is never vendored into: `hooks/post-checkout` treats a manifest written by
`tenant adopt` as installed mode.

**The adoption commit.** Adopt writes `.agent-rfc/designs/adoption.md` (status `done`, scope
exactly the files it wrote or changed, every design pillar answered) and
`.agenticframework/scaffold.json` (a SHA-256 of each, `generated_by: agentsmith tenant adopt`).
It prints the commit, staging those files by name — never `git add -A`, which would sweep in
unrelated work.

### The gate: the commit that arms the gates

`Review: n/a: generated scaffold` is accepted only on the commit **that arms the gates** — the
one whose parent does not carry `.agenticframework/process-gates.json`. A root commit has no
parent, so `tenant init`'s first commit still qualifies; an adoption commit now does too. The
other two conditions are unchanged: the manifest is in the commit, and every gated file in it
matches. Its messages name whichever command the manifest says wrote it.

Removing `process-gates.json` to reopen that door is itself a change to a gated file, and needs
a design and a review.

### Hooks: chained, not replaced

A new `.githooks/chain HOOK [ARGS]` runs the same-named hook from the directory in
`git config agentsmith.chainHooksPath` — with the same arguments and stdin — and exits with its
status. It does nothing when the setting is unset, the directory is `.githooks` itself, or the
hook is not there. It is local configuration, opted into by `init` or `adopt`, never by default.

- `commit-msg`, `pre-commit` and `pre-push` run the gate first; if it passes, they `exec chain`.
  In a repository with no setting — AgentSmith itself — nothing changes.
- For every other hook the prior directory has (`post-checkout`, `post-commit`, …), a one-line
  stub in `.githooks/` runs `chain`.
- Both `init` and `adopt` set it when they find prior hooks. When a `post-commit` is chained and
  `agentsmith.autopush` is unset, they set it to `false`. The machine's post-commit tags and
  pushes on its own, and a repository that has not been pushing on commit must not start. Both
  commands print that they did.
- `adopt` does not chain the machine's own **provisioning** hooks — AgentSmith's `post-checkout`
  and `post-commit`, which `git init` copies into `.git/hooks` on an installed machine. They sat
  inert until the repository opted in, and adopt's `tenant.yaml` opts it in: chained, they
  vendor framework code, write CI workflows and re-map the graph after every commit, none of
  which an adopted repository wants. The plan says they are left out. Its other hooks, the
  machine's guardrails among them, run behind the gates. (Found running adopt on a scratch
  repository: a `git checkout -- <file>` vendored 44 scripts and seven workflows into it.)

### `tenant init` vendors before its first commit

Chaining alone would make `git checkout` vendor again, but the vendored `scripts/` and
`runtime/` sit under gated globs, so committing them would need a design and a review of
framework code. Instead, when the repository has the machine's `post-checkout` in its prior hooks
directory, `init` runs it once before writing the manifest. The vendored files then join the
scaffold, the manifest vouches for them by hash, and the first commit's CI can run its
`scripts/*.py` steps. Vendoring stays in one implementation, the hook. Without that hook,
`init` prints what it prints today.

A vendored copy of the gate must still find the framework's documents. `@framework/<path>` was
read only beside the running script, which in a vendored tenant is the tenant's own `scripts/`,
with no `templates/governance.json` — so the first commit of a vendored, gated tenant was refused
for a registry that "does not exist". It is now read beside the script, then from
`$AGENTSMITH_DIR`, then from `~/.agent-framework`. Latent since G7, because no tenant had been
both vendored and gated.

## Pillars

- P1 applies — this design precedes the code; what `init` does to an existing repository was verified in a scratch copy first, and the finding is recorded in `.agent-rfc/reviews/tenant-architecture.md`.
- P2 applies — no dependency added; `runtime/adopt.py` uses the standard library, `pyyaml` and the gate's own modules.
- P3 n/a — `tenant adopt` is a local command with no service path; the gate's spans are unchanged.
- P4 applies — tests first: `scripts/test/test_tenant_adopt.py` adopts a real repository with history and commits through the real hooks; `scripts/test/test_hook_chain.py` runs prior hooks through the chain.
- P7 applies — the adoption plan is a typed dataclass in `runtime/adopt.py`; the manifest shape is the one `scripts/process_gate.py` already validates.
- P8 n/a — no telemetry wiring.
- P9 n/a — adopt writes no agent; `--agentic` only records the agent layer in `docs/DESIGN.md`, through `runtime/architectures.py`.
- P10 n/a — no model call.
- P11 applies — the repository being adopted is read as data: detection parses manifests and lists files, and runs nothing from the repository except the hooks it already ran (`.githooks/chain`).
- P12 applies — the gates workflow names `AGENTSMITH_READ_TOKEN` and the portal secrets by name only, in `workflow-templates/agentsmith-gates.yml`; nothing is written that holds a value.
- P13 applies — the review escape widens from "root commit" to "the commit that arms the gates", still hash-verified and still a note (`scaffold_problems` in `scripts/process_gate.py`); chaining runs only after the gate passes, so a prior hook cannot bypass it.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned with this change, and the manifest pins every file adopt wrote (`test_a_forced_rerun_still_vouches_for_what_the_first_run_wrote`).
- P15 applies — the plan says per file whether it is created, merged, regenerated or left alone (`describe` in `runtime/adopt.py`, `test_the_plan_finds_the_repository_as_it_is`).
- P16 applies — adopt writes nothing until confirmed, refuses before writing anything it cannot finish, and tells an unfinished adoption how to clear it (`test_a_repository_adopt_is_not_for_is_refused_before_anything_is_written`).

## Deviations

none

## Dependencies

None added.

## Levers

- `design-before-code` — the adopted repository's direction is written as a target architecture before its first governed change.
- `declared-vs-enforced` — the adoption commit is accepted on hashes, not on its message; the prior hooks keep running rather than being declared kept.
- `gate-integrity` — the escape is bound to the one commit that arms the gates; chained hooks run after the gate, never instead of it.
- `implemented-not-invoked` — the machine's `post-checkout` runs again in `init` repositories, and vendoring happens before the first commit instead of never.
- `one-catalog` — styles still come only from `templates/architectures.yaml`; IDE hook configs only from `gate_ides.render_config`; vendoring only from `hooks/post-checkout`.
- `test-the-contract` — tests adopt a real repository with history and hooks, and commit through the real hooks.
- `failure-mode-visibility` — every file's fate is in the plan; autopush being switched off is printed.
