---
status: done
scope:
  - hooks/post-checkout
  - .github/scratch-tenants/build.sh
  - scripts/mutation_check.py
  - scripts/test/**
---
# Tenant visibility override

<!-- Closed 2026-09-29: shipped in 2819294; AGENTSMITH_TENANT_VISIBILITY is in the hook, the docs and the tests, and the scratch tenants went green on it. -->

## Problem

The five scratch tenants were flipped public on 2026-09-27 so their CI would run
without metered private-repo minutes. That silently changed what they test.

`hooks/post-checkout` asks GitHub for the repository's visibility and, when the
answer is not private, appends an IDE-config block to `.gitignore` so
`CLAUDE.md`, `.cursorrules`, `AGENTS.md`, `GEMINI.md`,
`.github/copilot-instructions.md`, `.agents/` and `.agent-history.log` are not
published (docs/DESIGN.md › IDE Config Security). Correct behaviour for a public
repository. But it means a public scratch tenant no longer *tracks* those files,
so the pushed fixture stops matching a real tenant — which is private and tracks
them — and `scripts/process_gate.py` warns about exactly that state ("This clone
has no generated agent files"). The scratch tenants exist to catch onboarding
bugs invisible from inside this repo; a fixture on the other branch of the
visibility decision cannot catch the bugs of the branch real tenants use.

Evidence, run 36270770691 (all five jobs, step 7, nothing pushed):

    ℹ️  Could not confirm this repo is private — added IDE config files to .gitignore
    ##[error]the hook changed .gitignore — it treated this repo as public. Is gh authenticated (GH_TOKEN)?

Two further defects are visible in those two lines:

- The hook prints "Could not confirm this repo is private" in the case where it
  *did* confirm — as public. One sentence for two states that need different
  responses: fix your `gh` auth, versus your repo really is public.
- `.github/scratch-tenants/build.sh:92` asserts `.gitignore` never changes and
  blames `gh` authentication when it does. `gh` was authenticated and answered
  correctly. The guard encodes "these fixtures are private" as an assumption
  about the environment instead of stating it as an intent.

## Approach

State the intent instead of inferring it. A new environment variable,
`AGENTSMITH_TENANT_VISIBILITY`, declares what the caller knows the repository to
be; unset keeps today's detection exactly as it is, so nothing changes for any
existing caller.

- `private` (or `internal`, which `gh repo view` returns for org-internal
  repositories and the existing detection already treats as private) — IDE
  configs stay tracked, no `.gitignore` change.
- `public` — treat as public: append the block (non-interactive) or prompt (TTY).
- unset — ask `gh`, then fall back to "any github.com remote is potentially
  public", as now.
- anything else — print a `⚠️` line and fall back to detection. Not silent, and
  not fatal: `build.sh:86` already fails the build on any `⚠️`, so a typo in CI
  is caught there rather than quietly changing which branch the fixture tests.

The override is read once, at the single site that decides visibility
(`hooks/post-checkout:482`) — there is only one, confirmed by grep across `.py`,
`.sh`, `.yml` and the hook. It wins over the `gh` lookup, because an explicit
declaration by the caller beats an inference about the caller.

`build.sh` exports `AGENTSMITH_TENANT_VISIBILITY=private` before running the
installed hook, so the scratch tenants exercise the tracked-IDE-config path a
real tenant uses, on public fixture repos. The existing guard is kept at full
strength and becomes the proof the override took effect — with an error message
that names that cause instead of guessing at `gh`.

The declaration announces itself where the decision is made, and the one
append message becomes three — so what decided is separable from what was done:

| printed | when |
|---|---|
| `ℹ️  Visibility declared <value> by AGENTSMITH_TENANT_VISIBILITY` | at the decision, whenever the override is honoured, in either direction |
| `ℹ️  Added IDE config files to .gitignore` | appending, because the caller declared public |
| `ℹ️  This repo is public (confirmed via gh) — added IDE config files to .gitignore` | appending, because `gh` answered PUBLIC |
| `ℹ️  Could not confirm this repo is private — added IDE config files to .gitignore` | appending, because `gh` could not answer — the only case that is about gh |
| `⚠️  AGENTSMITH_TENANT_VISIBILITY='<value>' is not one of private, internal, public — detecting instead` | an unrecognised value, before falling back |

The third keeps its exact present wording: `test_hook_gitignore_idempotent.py`
pins that sentence for the gh-cannot-answer case, and that case is unchanged.

What this costs: visibility detection stops being covered as a side effect of
where the fixtures happen to live. That coverage was accidental — it tested
whichever branch the fixtures' own visibility selected, and it broke the moment
that changed. It is replaced by three direct tests of the decision itself, which
is the better trade regardless of where the fixtures live.

## Pillars

- P1 applies — this design, written before the edit, with `hooks/post-checkout`, `.github/scratch-tenants/build.sh`, `scripts/mutation_check.py` and `scripts/test/**` in scope; reviewed in `.agent-rfc/reviews/tenant-visibility-override.md` and described in `docs/DESIGN.md` › IDE Config Security and `docs/UserManual.md` › Runtime Flags.
- P2 applies — one decision site (`hooks/post-checkout:482`, grep-confirmed sole owner of `IS_PUBLIC`), so the override lands in one place and no new indirection is added; `agentsmith tenant adopt` does not decide visibility and is untouched. `local_knowledge_graph.py --context hooks/post-checkout` returns an empty node set — the mapper does not cover shell hooks, so the KG offers no impact edges here; recorded as a known limit, not worked around. No dependencies added.
- P3 n/a — a shell provisioning hook on the checkout path; it emits no spans today and this change adds no execution path that should.
- P4 applies — five tests: override `private` suppresses the append against a `gh` shim reporting PUBLIC (fails before this change); override `public` appends against a shim reporting PRIVATE (proves both directions, so the flag cannot be a no-op); an unrecognised value warns and falls back; the existing idempotency test pins the gh-cannot-answer sentence; and a static check that `build.sh` still declares the intent, so a future edit that drops the export is caught. Mutation target on the override branch — deleting it must fail a test.
- P7 applies — POSIX shell, `set -uo pipefail` semantics of the existing hook; no bashisms added beyond those already in the file; the variable is quoted at every use.
- P8 n/a — no telemetry in this path; nothing to resolve through runtime/otlp.py.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 applies — the value is untrusted input to a shell script: it is compared against a closed set of literals in a `case`, never interpolated into a command, a path or a redirect, so an arbitrary string cannot execute or write anywhere.
- P12 n/a — no credential is read or written. The change reduces credential-adjacent risk slightly by removing the misleading suggestion that `GH_TOKEN` is at fault.
- P13 applies — no check gets weaker. The `build.sh` guard keeps both directions and its exit 1; only its explanatory text changes. The unrecognised-value path deliberately does not exempt itself: it warns, and the `⚠️` fails the build.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned with `map_codebase.run_map(force=True)` and checked by `scripts/test/test_kg_drift_gate.py`; no other baseline or golden changes. The scratch tenant fixtures become *more* faithful — they return to the tracked-IDE-config state a real tenant has, pinned by `test_the_build_keeps_ide_configs_tracked_on_a_public_fixture` in `scripts/test/test_scratch_tenants.py`. The five repos stay public; only what the hook is told changes.
- P15 applies — the conflated sentence in `hooks/post-checkout` is the reason this design exists: three states get three sentences, pinned by `test_confirmed_public_does_not_blame_gh` and by `test_repeated_checkouts_add_the_ide_block_once` in `scripts/test/test_hook_gitignore_idempotent.py`, which holds the can't-answer wording. The unrecognised value is neither silently private nor silently public — `test_unrecognised_value_warns_and_falls_back_to_detection`.
- P16 applies — when the override is absent or unrecognised, control falls to the existing `gh` lookup; when that fails, to the existing conservative "potentially public" default. Each rung receives the same `IS_PUBLIC` contract, and the most conservative rung is still last. When the override fails to reach the hook, `build.sh`'s guard stops the build before any tenant is pushed — which is what happened in run 36270770691, correctly.

## Deviations

none

## Dependencies

none

## Levers

- `provenance-and-precedence` — the value now has three possible sources (override, `gh`, remote-URL inference); the design fixes the order and says why explicit beats inferred.
- `ambiguous-signals` — one sentence currently means both "could not determine" and "determined public"; split into three.
- `environment-parity` — the fixtures' behaviour stops depending on their own repository visibility, so a local run, CI and a real tenant take the same branch.
- `guards-must-be-able-to-fail` — the `build.sh` guard keeps its ability to fail and gains an accurate reason; the unrecognised-value path is routed into it rather than around it.
- `fixture-truth` — restores the fixture to the state it is supposed to represent instead of accepting whichever state its own hosting produced.
- `declared-vs-enforced` — the declared intent is enforced by the guard that reads its effect, not merely exported and hoped for.
- `every-line-earns-its-place` — a `case` at the existing decision site, not a helper; no wrapper, no new file.
