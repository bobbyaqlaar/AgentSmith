---
status: done
scope:
  - runtime/sync.py
  - runtime/machine/upgrade.py
  - scripts/test/test_framework_sync.py
  - scripts/mutation_check.py
---
# `sync` and `upgrade` refuse the framework's own checkout

## Problem

On 2026-10-01 the owner ran `agentsmith sync` in this repository after
reinstalling. It said "nothing stale in what this framework owns", asked, and on
`y` wrote a tenant scaffold into the framework itself:

- `.agent-rfc/001-scaffold.md` (the empty RFC template), `.agent-rfc/designs/adoption.md`,
  `.agenticframework/providers.json`, `.agenticframework/scaffold.json`;
- every `.githooks/` file re-copied from `~/.agent-framework` and set to 755 by
  `install_gate_hooks` — `chain` is tracked as 644, so the stop gate refused the turn
  over a file nobody had meant to touch;
- a printed commit, `Review: n/a: framework sync`, that would have recorded this
  repository as a tenant of itself.

`tenant init` and `tenant adopt` refuse here (`looks_like_framework`, `runtime/cli.py`).
`plan_sync` asks only for `.agenticframework/process-gates.json`, which this
repository carries like any governed one.

What stopped it being worse was luck. `sync` calls `upgrade`, which copies the
installed `scripts/` and `runtime/` over the repository's and deletes `runtime/test`,
restoring only the suites a tenant gets. It quit because this repository has no
`.agenticframework/tenant.yaml` — a file `tenant init --allow-framework-root` would
create. `upgrade` run directly is protected by that same accident.

Correction to what the owner was told: the installer does not flip `chain`'s mode
here. It writes only `~/.agent-framework/.githooks/`. The flip was `sync`'s.

## Approach

- **`plan_sync` refuses first**, before it reads anything else: if
  `looks_like_framework(root)` names markers, raise `SyncError` —
  "`<root>` is AgentSmith's own checkout (`<markers>`): it is what `sync` copies FROM,
  not a tenant. Run it in a tenant repository, or pass `--root`." The CLI already
  prints a `SyncError` and exits 2, writing nothing.
- **`upgrade` refuses the same way**, before its `tenant.yaml` check, so the guard
  that protects `scripts/` and `runtime/` is a deliberate one rather than a missing
  file. It returns 1 with the same explanation, as its other refusals do.
- **No override flag on either.** `tenant init` has `--allow-framework-root` because a
  framework developer may want a scratch tenant in place. There is nothing to sync or
  upgrade the framework FROM except itself, so the flag would only re-open the hole.
- **`.githooks/chain` stays 644.** With `sync` refusing here, nothing in this
  repository's workflow rewrites its mode; in tenants it is written 755 and committed
  that way. Changing the tracked mode would fix a symptom of the bug this removes.

**Deliberately not done:** `sync` still ignores `upgrade`'s exit code and prints the
"vendored … refreshed too" note regardless — a separate backlog row, because it
changes what tenants see and is not needed to close this hole.

## Pillars

- P1 applies — `docs/PRODUCT_BACKLOG.md` row "`agentsmith sync` writes a tenant scaffold
  into the framework's own checkout", opened before this design, at the owner's request.
- P2 applies — `runtime/cli.py`'s `looks_like_framework` is reused, not reimplemented:
  `tenant init`, `tenant adopt` and `scripts/security/runners/_shared.py` already use it,
  with its two-marker rule. No dependencies.
- P3 n/a — no new command, route or job; a refusal at the top of two existing commands,
  which print it and exit non-zero like their other refusals.
- P4 applies — `scripts/test/test_framework_sync.py`: `sync` and `upgrade` against a
  repository carrying the framework's markers refuse and leave its tree byte-for-byte
  unchanged; the real checkout is recognised (so a marker that drifts fails a test
  rather than silently disarming the guard); a tenant still syncs. Two mutations in the
  `framework_sync` suite of `scripts/mutation_check.py`, one per guard.
- P7 n/a — a guard clause in two existing functions; no model, handler, async code or
  TypeScript.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 n/a — reads the repository's own `pyproject.toml` for a fixed substring, as
  `tenant init` already does; nothing is executed or rendered.
- P12 n/a — no credentials.
- P13 applies — `runtime/sync.py` and `runtime/machine/upgrade.py` each gain a refusal;
  nothing gets weaker, and no override flag is added (see Approach).
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is regenerated if the new
  import edges move it; no golden or contract fixture changes.
- P15 applies — `runtime/sync.py`'s refusal names the markers it found and says this is
  the framework, which reads differently from "not under the gates"; exit 2 with nothing
  written, never a "Nothing to do." that would read as success.
- P16 applies — `runtime/sync.py` refuses in `plan_sync`, before the prompt and before
  any write, so there is no partial state to recover from; a framework developer who
  hits it runs the command in the tenant or passes `--root`, as the message says.

## Deviations

none

## Dependencies

none

## Levers

- `grep-for-siblings` — `init` and `adopt` had the guard and `sync` did not; every
  command that writes into a repository root was checked, and `upgrade`, the most
  destructive, was protected only by a missing file. Both are fixed.
- `guards-must-be-able-to-fail` — a test runs each command against the real checkout's
  markers and a mutation removes each guard.
- `failure-is-not-a-result` — a refusal is exit 2 / 1 with its reason, never "Nothing to do."
- `declared-vs-enforced` — `upgrade`'s protection was an accident of a missing
  `tenant.yaml`; it becomes a stated check.
- `docs-match-behaviour` — `docs/UserManual.md`'s `sync` and `upgrade` rows say they refuse here.
- `backlog-discipline` — the row is opened now and moved to the archive when this ships;
  the exit-code issue keeps its own row.
