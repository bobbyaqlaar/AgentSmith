---
status: done
scope:
  - runtime/sync.py
  - runtime/cli.py
  - runtime/adopt.py
  - runtime/machine/upgrade.py
  - scripts/process_gate.py
  - scripts/test/test_framework_sync.py
  - scripts/test/test_scaffold_review.py
  - scripts/test/test_ai_stack_upgrade.py
  - scripts/mutation_check.py
  - docs/process-gates.md
  - docs/UserManual.md
  - CHANGELOG.md
  - .agent-rfc/fixtures/knowledge_graph.json
---
# One command keeps a tenant current, and its own gates accept it

Third slice of `.agent-rfc/designs/governance-providers.md`. The contract and provider resolution
removed the coupling for the gate; what a tenant still *holds* as copies drifts, and refreshing
them is refused by the tenant's own gates.

## Problem

Measured on 2026-09-23: a tenant holds the gate hooks, the CI workflows, the IDE hook configs, the
generated rule files and (vendored tenants) `scripts/`, `runtime/`, `templates/` and `fixtures/`.
`agentsmith upgrade` refreshes the last group and the version pin. **Nothing refreshes the rest** —
the gate hooks changed six times in 90 days and the workflow templates 33 times, and no tenant saw
any of it. A tenant adopted last week has no `.githooks/chain`, and never will.

Worse, the refresh that does exist cannot be committed: `upgrade` writes
`chore(framework): upgrade AgentSmith to vX` with no `Design:`/`Review:` trailers, over
`scripts/**` and `runtime/**`, which a governed tenant gates. So upgrading means writing a design
and a review for framework code the tenant did not write — the cost the owner asked to remove.

And `upgrade` in an **adopted** repository would vendor `scripts/` and `runtime/` into it: it
checks for a package pin but not for the adoption manifest, so it would undo exactly what adoption
promised.

## Approach

### `agentsmith sync`

One command refreshes everything this framework owns in the repository it is run in, and nothing
else:

- the gate hooks (`.githooks/*`, `chain` included) and the arming, through the same
  `install_gate_hooks` that `init` and `adopt` use;
- `.agenticframework/providers.json`, where the repository has none yet;
- for a **vendored** tenant only, the vendored trees and the version pin — delegated to
  `runtime/machine/upgrade.py`, which keeps one implementation of vendoring.

**Not in this slice:** the IDE hook configs, the rule files' managed block and the gates workflow.
Each is merged into a file the tenant also edits, and a wrong merge there is worse than a stale
block; the hooks and the declaration are what the gates themselves depend on. They are the next
step, not a half-done part of this one.

It prints a plan first, as `adopt` does — created, replaced, left alone — writes nothing without a
yes (`--yes` off a terminal), rewrites `.agenticframework/scaffold.json` with a hash of every file
it wrote and the framework version, and prints the commit. Run twice, the second run writes
nothing: a sync that has nothing to do says so.

**An adopted repository is never vendored into.** `sync` and `upgrade` both read the manifest's
`generated_by`, so the adoption promise holds on both paths.

### The gate accepts a verified sync

`Review: n/a: framework sync <version>` is accepted when **every gated file in the commit** matches
the manifest that names this framework as its author — the same hash rule the generated scaffold
already uses, without the arming-commit condition, because a sync happens whenever a tenant
upgrades. Accepted, it is a **note**: the commit's verdict is `passed_with_notes`, CI lists it and
the portal shows it.

A file the tenant edited by hand is not in the manifest, or no longer matches it, and falls back to
the normal rule with the file named. The stated limit is the scaffold's: the manifest is not
signed, so rewriting a file *and* its hash defeats it — deliberately, and visibly.

### What this does not do

It does not touch the repository's own code, its CI beyond the gates workflow, or its documents. A
major release of the provider still needs no tenant change at all while the contract holds; `sync`
is for what a tenant genuinely holds a copy of.

## Pillars

- P1 applies — this design precedes the code and answers the friction measured in `.agent-rfc/designs/governance-providers.md`.
- P2 applies — no dependency added; `runtime/sync.py` reuses `runtime/adopt.py`'s writers and `runtime/machine/upgrade.py`'s vendoring.
- P3 n/a — a local command with no service path.
- P4 applies — tests first in `scripts/test/test_framework_sync.py`: a drifted hook is refreshed, the sync commit passes its own gates, a hand-edited gated file is not vouched for, an adopted repository is not vendored into, and a second run writes nothing.
- P7 applies — the manifest keeps the shape `scripts/process_gate.py` already validates, in `runtime/sync.py`.
- P8 n/a — no telemetry wiring.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 applies — `sync` writes only files this framework owns, from the framework's own copies, never from anything the repository under sync supplies (`runtime/sync.py`).
- P12 applies — nothing written holds a credential; the gates workflow reads secrets by name only, in `workflow-templates/agentsmith-gates.yml`.
- P13 applies — the new review escape is hash-verified against the manifest and is a visible note, and a file that does not match falls back to the normal rule (`manifest_problems` in `scripts/process_gate.py`).
- P14 applies — the manifest is rewritten with each sync, and `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned with this change.
- P15 applies — "nothing to do" and "refused" are different answers, and the plan says which files were left alone and why (`runtime/sync.py`).
- P16 applies — a sync that cannot arm the gates refuses before writing, as `tenant adopt` does (`missing_gate_hooks` in `runtime/cli.py`).

## Deviations

none

## Dependencies

None added.

## Levers

- `one-catalog` — one implementation of each write: hooks from `install_gate_hooks`, vendoring from `upgrade`, rules from `adopt`'s merge.
- `declared-vs-enforced` — the sync escape is checked against hashes, not taken from the message.
- `denied-vs-missing` — a file the tenant edited is named, not silently replaced or silently accepted.
- `implemented-not-invoked` — the hooks a tenant holds stop being a copy nobody refreshes.
- `test-the-contract` — the tests sync a real tenant and commit through the real hooks.
