---
status: active
scope:
  - runtime/sync.py
  - runtime/adopt.py
  - scripts/test/test_framework_sync.py
  - scripts/mutation_check.py
  - docs/process-gates.md
  - CHANGELOG.md
  - .agent-rfc/fixtures/knowledge_graph.json
---
# A sync refreshes what it owns, and never clobbers what it does not

Fourth slice of `.agent-rfc/designs/governance-providers.md`. `agentsmith sync` refreshes the gate
hooks and the provider declaration; the files it shares with the tenant — the IDE hook configs, the
rule files' managed block, the gates workflow — were left out on purpose, because getting a merge
wrong there is worse than leaving a block stale.

## Problem

Those are exactly the files that carry the framework's instructions to agents. A tenant adopted
before the rules changed keeps the old block in `CLAUDE.md` for ever; its `.claude/settings.json`
keeps the hook wiring of whatever version adopted it; and its gates workflow keeps pointing at the
release it was adopted from, so a tenant that upgrades still runs the old provider in CI. Each is a
file a person also edits, which is why `sync` did not touch them yet.

## Approach

### The manifest decides ownership

`.agenticframework/scaffold.json` records every file this framework wrote and its hash at the time.
That makes three states, and `sync` treats them differently:

| State | Meaning | What `sync` does |
|---|---|---|
| in the manifest, bytes still match | the framework wrote it and nobody has touched it | refresh it |
| in the manifest, bytes differ | the tenant edited it afterwards | **leave it, and say so** |
| not in the manifest | the tenant's own file | leave it, silently — it was never ours |

So a sync can never surprise someone: the only files it rewrites are ones it can prove it wrote and
that nobody has since changed. A file the tenant edited is named in the plan with what to do about
it (re-run after reverting, or take the change deliberately).

**The one exception is the managed block.** In a rule file the tenant owns — their `CLAUDE.md` with
our rules appended between `agentsmith:rules` markers — the *block* is ours and the rest is theirs.
`sync` replaces the block and leaves every other byte, which `merge_rules_block` already does; the
file itself is never judged by its hash, because the tenant is expected to edit around the block.

### What gets refreshed

- **The IDE hook configs** (`.claude/settings.json`, `.cursor/hooks.json`) — re-rendered through
  `gate_ides.render_config(ide, existing)`, which replaces the hooks and keeps everything else the
  file holds, so a tenant's `permissions` survive.
- **The rule files** — the managed block, re-rendered from the framework's current
  `agent-rules.yaml`; a file the framework generated whole and nobody has edited is regenerated
  whole.
- **The gates workflow** — including its `ref:`, which is how a tenant that upgrades starts running
  the new provider in CI rather than the release it was adopted from.

### One place that renders

`runtime/adopt.py` grows `generated_rules(root, framework, stack)`, which renders the rule files
into a temporary directory and returns them as text. `adopt` writes them; `sync` compares them.
One renderer, so the two can never disagree about what the rules say.

## Pillars

- P1 applies — this design precedes the code and continues `.agent-rfc/designs/framework-sync.md`, whose review recorded these files as the next step.
- P2 applies — no dependency added; the renderer is the existing `scripts/generate-ide-config.py`.
- P3 n/a — a local command with no service path.
- P4 applies — tests first in `scripts/test/test_framework_sync.py`: a stale block is refreshed, a tenant's prose and permissions survive, an edited file is left alone and named, and the workflow's ref moves.
- P7 applies — the IDE configs are rendered by `gate_ides.render_config`, the one typed renderer, in `runtime/sync.py`.
- P8 n/a — no telemetry wiring.
- P9 n/a — no agent code; the rules it refreshes are instructions to agents, rendered from `templates/agent-rules.yaml`.
- P10 n/a — no model call.
- P11 applies — everything written is rendered from the framework's own templates, never from content the tenant repository supplies (`runtime/sync.py`).
- P12 applies — the refreshed workflow names secrets only, in `workflow-templates/agentsmith-gates.yml`.
- P13 applies — the sync commit stays hash-verified: every file `sync` writes goes into the manifest it rewrites, so the gate's `framework sync` rule still checks it (`manifest_problems` in `scripts/process_gate.py`).
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned with this change.
- P15 applies — "left alone because you edited it" is printed, never silence; "not ours" is silent, because it never was (`describe` in `runtime/sync.py`).
- P16 applies — a tenant that wants the framework's version back reverts the file and re-runs, which the plan says; a file the framework wrote and the tenant deleted is written back (`ownership` in `runtime/sync.py`).

## Deviations

none

## Dependencies

None added.

## Levers

- `merge-the-right-copy` — the manifest, not a guess, decides whose file it is.
- `denied-vs-missing` — "edited by you, left alone" and "never ours" are different answers.
- `one-catalog` — one renderer for the rule files, shared by `adopt` and `sync`.
- `declared-vs-enforced` — every refreshed file lands in the manifest, so the commit stays checkable.
- `test-the-contract` — the tests sync a real tenant whose files a person has edited.
