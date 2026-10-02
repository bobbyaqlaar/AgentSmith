---
status: done
scope:
  - runtime/sync.py
  - runtime/cli.py
  - runtime/architectures.py
  - scripts/process_gate.py
  - scripts/test/test_framework_sync.py
  - scripts/test/test_process_gate.py
  - scripts/test/test_scaffold_review.py
  - scripts/mutation_check.py
---
# `sync` gives a tenant the gate hooks it is missing, in a commit its gate accepts

## Problem

On 2026-10-02 `agentsmith sync` ran in KYC Sentinel to bring it the gate fix for
binary files. KYC armed the gates on 2026-09-14, before `pre-commit`, `pre-push`
and `chain` existed: its `.githooks/` holds `commit-msg` and `process-gate`. It
gates `.agenticframework/**`, as OTS does (both were adopted by hand, before
`tenant adopt` existed; a tenant `init` or `adopt` writes gates only
`.agenticframework/process-gates.json`). Two failures:

1. **Hooks armed but never committed.** `install_gate_hooks(force=True)` writes every
   hook in `GATE_HOOKS`, so the three missing ones landed in `.githooks/` — and
   `core.hooksPath` is `.githooks`, so `pre-commit` and `pre-push` were live in that
   checkout at once. But `plan_sync` lists only hooks the tenant already has as
   stale, so the three were in neither the manifest nor the printed commit. A clone
   never gets them; `git add -A` later sweeps them into a commit the gate refuses.
2. **The printed commit is refused by the tenant's own gate:**
   `Design: .agent-rfc/designs/adoption.md scope does not cover .agenticframework/scaffold.json`
   and `scaffold.json is not part of what agentsmith sync wrote`. The manifest is
   gated there; it cannot list its own hash; and the arming design's scope is the
   files the command wrote, which never include the manifest.

OTS has the same two hooks and the same gating. Neither tenant can be synced.

**Owner decision (2026-10-02): a sync gives a tenant the gate hooks it is missing.**
`sync`'s rule that it "adds nothing new to a repository that did not ask for it"
was written for files a tenant did not ask for; a tenant that adopted the gates
asked for the gate's hooks, and one that adopted before G3 has no other way to get
the bypass sweep.

## Approach

- **Missing gate hooks are planned as additions.** `plan_sync` lists every hook in
  `GATE_HOOKS` the tenant lacks in a new `Plan.added`; `describe` prints them as
  `add     .githooks/pre-push`, beside `stale`, and a note when `pre-commit` or
  `pre-push` is among them: from now on the bypass sweep runs on commit and on push,
  and a push is refused while a commit that skipped the gate is outstanding
  (`agentsmith gates repair`). Only `GATE_HOOKS` — nothing else is added.
- **What sync writes is what it commits.** `sync` puts `added` into `written`
  alongside `stale`, so the manifest records the new hooks' hashes and the printed
  commit carries them. `chain` is safe to add: it does nothing until
  `agentsmith.chainHooksPath` is set.
- **The manifest does not have to vouch for itself.** `manifest_problems` skips
  `.agenticframework/scaffold.json`: it is the check's own input — parsed, and its
  `generated_by` named in the note — and a file cannot carry its own hash. A tenant
  `init` or `adopt` writes does not gate it at all, so this gives KYC and OTS the
  posture every other tenant already has, not a weaker one.
- **The sync's design covers what the sync commits.** A sync keeps the arming
  design rather than rewriting it (so a sync never reads as a new design), but
  `write_scaffold_records` now adds to its `scope:` every path the sync commit
  carries that it does not list — scope lines only, prose untouched, idempotent.
  A design the sync writes because none existed (KYC had none) lists the manifest
  from the start; so does every scaffold design `init` and `adopt` write.

**Deliberately not done:** no change to which paths a tenant gates; no sync for the
other files a tenant may lack (IDE configs for IDEs it never chose); the
`upgrade` exit-code row stays open.

## Pillars

- P1 applies — `docs/PRODUCT_BACKLOG.md` row "`agentsmith sync` cannot bring KYC
  Sentinel or OTS current", opened with the owner's decision recorded in it.
- P2 applies — `runtime/cli.py`'s `install_gate_hooks` and `GATE_HOOKS` already write
  the hooks; the change is that `runtime/sync.py` plans and commits what they write.
  The scope edit lives in `runtime/architectures.py` beside `render_scaffold_design`,
  which writes that block — `runtime/` cannot import `scripts/process_gate.py`, which
  needs the framework environment and is absent where `runtime/` is vendored. It
  edits only the `scope:` list lines it finds and leaves everything else as written.
  No dependencies.
- P3 n/a — no new command, route or job; `sync` prints one more kind of line.
- P4 applies — `scripts/test/test_framework_sync.py`: a tenant shaped like KYC (two
  hooks, `.agenticframework/**` gated, an arming design that omits the manifest) is
  synced; the three hooks are in the plan, the manifest and the commit, and the commit
  as printed passes that tenant's own gate; a second sync writes nothing; the scope
  edit is idempotent and leaves the prose. `scripts/test/test_scaffold_review.py`: the
  manifest is not asked to vouch for itself, and every other unvouched file still is.
  Mutations in `framework_sync` for each of the three changes.
- P7 n/a — no model, handler, async code or TypeScript; `Plan` is an existing dataclass
  gaining one list.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 n/a — reads the tenant's own design and manifest, as `sync` and the gate already do.
- P12 n/a — no credentials.
- P13 applies — `scripts/process_gate.py`'s `manifest_problems` stops asking the manifest
  to vouch for itself. Nothing else loosens: every other gated file in a sync commit
  must still match its recorded hash, and the design must still cover it. The
  documented limit is unchanged — the manifest is not signed, so rewriting a file and
  its hash defeats it — and in a tenant that gates the manifest it was never stronger
  than that.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` rebuilt; the scaffold design a
  fresh `init` writes gains one scope line, and any test pinning that design's text is
  updated with it.
- P15 applies — `runtime/sync.py`'s output says `add` for a hook it is adding, not
  `stale`, and says what the sweep will now do — a refused push after a sync reads as
  the sweep, not as a broken hook.
- P16 applies — `runtime/sync.py`: a tenant that does not want the sweep yet commits
  only the files it chooses; a sync re-run on a tenant with all five hooks adds nothing.

## Deviations

none

## Dependencies

none

## Levers

- `implemented-not-invoked` — the hooks were written and armed but never committed:
  present in one checkout, absent from every clone.
- `declared-vs-enforced` — `sync` declared "adds nothing new" while `install_gate_hooks`
  wrote three new files; the plan now says what the write does.
- `gate-integrity` — the manifest exemption is argued above; a mutation proves every
  other unvouched file is still refused.
- `test-the-contract` — the test commits exactly what `sync` printed, through the
  tenant's own gate, rather than asserting the list.
- `out-of-order-and-repeated` — a second sync, and a sync over a design whose scope
  already covers everything, change nothing.
- `failure-is-not-a-result` / `ambiguous-signals` — `add` and `stale` read differently;
  the sweep's arrival is announced.
- `docs-match-behaviour` — `docs/process-gates.md`'s sync section and the user manual's
  `sync` row say it adds missing gate hooks.
