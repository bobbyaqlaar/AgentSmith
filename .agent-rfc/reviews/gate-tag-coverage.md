# Review — `agentsmith gates run`'s green was not CI's green

Design: `.agent-rfc/designs/gate-tag-coverage.md`. Owner, 2026-09-26: "Run sweeping pass and
full-suite alternatively, twice."

Four steps, as asked: sweep, suite, sweep, suite. **3 findings**, both sweeps productive, and **both
suite runs clean** — the first time in this sequence that a full run after a sweep has added nothing,
which is the signal the alternation was for.

## Pass 1 — findings: 1

**Sweep A — blocking CI steps against the `# agentsmith:gate` tags.** `.github/workflows/self-test.yml`
has 34 `run:` steps and carried 19 tags. Excluding setup — installs, `db:migrate`, starting the portal
— four blocking **checks** had no tag, so `agentsmith gates run` could not run them and the generated
checklist table did not list them.

1. `declared-vs-enforced` / `ambiguous-signals` — **`agentsmith gates run` reporting "0 failed" did
   not mean CI would pass.** Untagged and blocking: `npx tsc --noEmit` (the portal's type check),
   `npm run build`, `verify_system.py --check-history-sync`, and `npm test` in the widget job — the
   widget's entire suite. The portal job tags **both** its `npm test` steps and neither `tsc --noEmit`
   nor `npm run build`, so the pattern was understood and applied unevenly; the widget job tagged
   nothing. A developer could run the local gates, read zero failures, and fail CI on a type error.

   Tagged all four, with names so `gates list` shows them. One qualifier per tag is all
   `gate_steps.Step.needs` holds, so `tsc --noEmit` took `no-services` — the useful one, since a type
   check wants no database and now actually runs locally — and the others report honestly as needing
   services or npm. Adding the tags immediately failed `test_the_checklist_holds_the_generated_table`,
   because that table is generated from the same tags: `one-catalog` doing its job, not a regression.
   Regenerated with `generate-ide-config.py --gates`.

   **Guarded, not just fixed.** `test_every_blocking_check_in_this_repos_ci_carries_the_tag` fails on
   any blocking `run:` step that is neither tagged nor named in `_SETUP_STEPS`. The setup list is
   explicit rather than pattern-matched, so a new step forces a decision and a real check cannot
   arrive untagged by looking like an install.

## Pass 2 — findings: 0

**Full suite after Sweep A.** ruff, mypy in a clean environment, **1942 passed, 10 skipped**. Nothing
new — the first clean interleaved run.

## Pass 3 — findings: 2

**Sweep B — cross-language catalogues with no test that parses the other side.** Six pairs. Span
attributes (`test_otlp_endpoint.py`), the control registry (`test_security_registry.py`, 15
references) and the dev record (`portal/test/wireContract.test.ts`) are properly pinned. Two were not.

1. `pin-unremovable-duplicates` — **the decision half of the contract test compared a catalogue
   against a copy of itself.** `test_the_published_schemas_match_the_models_they_describe` reads
   `gm.GateEvent.model_fields` for the event half and then asserts the decision half equals
   `{"decision", "text"}` and `{"allow", "deny", "block", "context"}` **written out in the test**,
   under a docstring reading "generated from the Pydantic models, not written twice". This repository's
   own lever notes say it in those words: *a test that hardcodes the second copy is just a third copy.*
   `Decision` could have gained a field or a fifth verdict and `contract/gate/v1/decision.schema.json`
   — the schema a third party implements against — could have gone stale with this green. Both sides
   are now read, the verdicts via `typing.get_args` on the `Literal`, with a guard for the day it
   stops being one.
2. `declared-vs-enforced` — **`contract/gate/v1/providers.schema.json` was referenced by no test.**
   Published so another platform can write a conforming declaration, and `agentsmith tenant adopt`
   writes one, with nothing checking they agree: a field renamed on either side would have shipped a
   schema that rejects the framework's own output. Now `providers_declaration()` is validated against
   it, as is the `"gate": "none"` form, and a second test asserts the schema **rejects** three
   declarations the launcher could not read — a schema that accepts anything pins nothing.

## Pass 4 — findings: 0

**Full suite after Sweep B.** ruff, mypy, **1944 passed, 10 skipped**. Clean.

Every new assertion was run against a reverted fix and each failed: an untagged widget `npm test`; a
field added to `Decision`; a fifth verdict added to its `Literal`; and `command` renamed to `cmd` in
`providers_declaration`. The first attempt at the `Decision` field proof passed — the injected field
had landed outside the class — which is worth recording, because a proof that does not prove is the
same defect as a test that cannot fail.

## Stated limits

- **One qualifier per gate tag.** `gate_steps.Step.needs` is a single value, so a step that needs a
  tool *and* no services cannot say both. `tsc --noEmit` takes `no-services` and its `npx` dependency
  is undeclared; the failure mode is a clear error, not a wrong verdict. Widening the grammar is a
  change to the runner, not to this sweep.
- **`_SETUP_STEPS` is a literal list of seven.** It will need an entry whenever CI gains a setup step,
  and the test says so in its message. That is deliberate: the alternative is a pattern that lets a
  check pass as setup.
- **The tag coverage test reads only `self-test.yml`.** `scratch-tenants.yml` and the release workflow
  are unexamined, and `workflow-templates/` is out of scope by design — those are a tenant's CI.
- **`jsonschema.validate` checks structure, not meaning.** A declaration can satisfy the schema and
  still name a provider that does not exist; `agentsmith conformance` is the check for that, and no
  third party has run it.
- **Sweep B examined six pairs, chosen by hand.** It is not an enumeration of every cross-language
  catalogue in the repository.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the checklist table stayed generated from the tags
                                          rather than edited, which is how it caught the new ones
Group 2 · Quality / safety            [x] checked — four blocking checks became runnable or honestly
                                          skippable locally; none was weakened
Group 3 · Architecture / hygiene      [x] checked — the published contract schemas are now pinned to
                                          the models on both halves
Group 4 · Process                     [x] checked — sweep, suite, sweep, suite, as asked; both suites
                                          clean and recorded as passes
Group 5 · Intuitive UI                [x] checked — `gates list` now names the four, so a developer
                                          can see what the local runner will and will not attempt
Group 6 · Signal integrity            [x] checked — this is the slice: "0 failed" locally stopped
                                          implying CI will pass
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_gate_steps.py (+1), scripts/test/test_gate_contract.py
                          (+2, and one existing test's decision half rewritten to read the model)
Mutation-checked:          four reverted fixes, each failing its test; one proof that initially did
                          not prove, corrected and recorded
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json, and
                          docs/validation-checklist.md regenerated from the tags
KG query:                 kg:d17d4a145b23
Gates run locally:         ruff, mypy in a clean environment, `agentsmith gates list`, and the full
                          suite twice (1942 then 1944 passed)
Declared gaps:             (1) one qualifier per tag; (2) _SETUP_STEPS is a literal list;
                              (3) only self-test.yml is swept for tags; (4) schema validation checks
                              structure, not that a named provider exists; (5) Sweep B's six pairs
                              were chosen by hand
```
