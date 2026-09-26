---
status: done
scope:
  - .github/workflows/self-test.yml
  - scripts/test/**
  - docs/validation-checklist.md
  - CHANGELOG.md
  - .agent-rfc/fixtures/knowledge_graph.json
---
# `agentsmith gates run`'s green was not CI's green

Owner, 2026-09-26: "Run sweeping pass and full-suite alternatively, twice." Two sweeps of untried
classes, each followed by the whole suite — the alternation because the suite has twice caught what a
sweep did not.

## Problem

**Sweep A — every blocking CI step against the `# agentsmith:gate` tags.** `agentsmith gates run`
says it runs "this repo's CI gates here", and the checklist's table is generated from the same tags,
so a step without one is invisible to both. `.github/workflows/self-test.yml` has 34 `run:` steps and
19 tags; stripping setup (installs, migrations, starting a server) left **four blocking checks with
no tag**:

- `npx tsc --noEmit` — the portal's type check;
- `npm run build` — the portal's build;
- `verify_system.py --check-history-sync`;
- `npm test` in the widget job — its whole suite.

The portal job tags **both** its `npm test` steps and neither `tsc --noEmit` nor `npm run build`, so
the pattern was known and applied inconsistently. A developer could run `agentsmith gates run`, read
"0 failed", and fail CI on a type error.

**Sweep B — cross-language catalogues with no test that parses the other side.** Six pairs checked.
Span attributes, the control registry and the dev record are pinned. Two were not:

1. `test_the_published_schemas_match_the_models_they_describe` reads `gm.GateEvent.model_fields` for
   the event half and then compares the decision half against `{"decision", "text"}` and
   `{"allow", "deny", "block", "context"}` **written out in the test** — a third copy of the
   catalogue, under a docstring that says "not written twice". `pin-unremovable-duplicates` names this
   exactly: *a test that hardcodes the second copy is just a third copy.* `Decision` could have gained
   a field or a fifth verdict and the schema a third party implements against could have gone stale
   with the test green.
2. `contract/gate/v1/providers.schema.json` is referenced by **no test at all**. It is published so
   another platform can write a conforming declaration, and `agentsmith tenant adopt` writes one, with
   nothing checking the two agree.

## Approach

- **Tag the four**, with names so `gates list` can show them, and one qualifier each. `tsc --noEmit`
  takes `no-services` so it actually runs locally; the rest are honestly reported as needing services
  or npm. The checklist's generated table is regenerated from the tags, which the existing
  `test_the_checklist_holds_the_generated_table` demanded as soon as the tags changed — the catalogue
  working as designed.
- **Guard the class.** `test_every_blocking_check_in_this_repos_ci_carries_the_tag` fails on any
  blocking `run:` step that is neither tagged nor on an explicit `_SETUP_STEPS` list. Listed rather
  than pattern-matched, so a new step forces a decision and a genuine check cannot arrive untagged by
  resembling setup.
- **Read both sides of the decision schema** — `gm.Decision.model_fields`, and the verdicts from the
  `Literal` via `typing.get_args`, with a guard for the day it stops being a `Literal`.
- **Validate what adopt writes against the published schema**, and assert the schema rejects three
  declarations the launcher could not read, because a schema that accepts anything pins nothing.

## Pillars

- P1 applies — this design precedes the code; the sweeps and both suite runs are recorded in `.agent-rfc/reviews/gate-tag-coverage.md`.
- P2 applies — no dependency added; `jsonschema` is already in `requirements.lock` and used by the security harness.
- P3 n/a — no execution path added.
- P4 applies — three tests, each run against a reverted fix: `test_every_blocking_check_in_this_repos_ci_carries_the_tag`, `test_the_published_schemas_match_the_models_they_describe` (both halves), and `test_what_adopt_writes_validates_against_the_published_providers_schema`.
- P7 n/a — no new typed boundary; the schema tests read existing Pydantic models.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the tests read this repository's own workflow and schemas as data; `jsonschema.validate` is given the framework's own output, never tenant input (`scripts/test/test_gate_contract.py`).
- P12 applies — no credential is read; the newly tagged steps name `AUDIT_LOG_HMAC_KEY` only as the CI job already did, by variable name in `.github/workflows/self-test.yml`.
- P13 applies — this is the pillar: four blocking checks become visible to `agentsmith gates run` rather than staying outside it, and two pins stop comparing a catalogue against a copy of itself. Nothing is weakened; `_SETUP_STEPS` is an explicit list whose growth is a reviewable decision.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned, and `docs/validation-checklist.md`'s generated table is regenerated from the tags rather than edited.
- P15 applies — `gates run`'s "0 failed" stopped meaning two different things (all CI checks passed / all tagged checks passed) by making the tags cover the checks.
- P16 n/a — no fallback path added.

## Deviations

none

## Dependencies

None added — `jsonschema` is already installed and locked.

## Levers

- `declared-vs-enforced` — a local runner claiming to run CI's gates, with four of them untagged.
- `pin-unremovable-duplicates` — the decision schema compared against a hardcoded third copy, and a published schema with no test at all.
- `ambiguous-signals` — "0 failed" from `gates run` read as "CI will pass".
- `one-catalog` — the checklist table is generated from the tags, which is why adding four tags broke it immediately.
- `grep-for-siblings` — the portal job tagged two steps of four; the widget job tagged none.
