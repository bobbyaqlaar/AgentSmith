# Review — fail-closed-has-a-reader

Design: `.agent-rfc/designs/fail-closed-has-a-reader.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 2

1. **I edited a generated file instead of its source.** `templates/governance.json`
   carries `"Generated from templates/agent-rules.yaml … Do not edit"` in its own
   `_about` field, and I changed `fail_closed` in it directly.
   `test_the_committed_registry_is_what_agent_rules_compiles_to` caught it —
   "governance.json has drifted — run generate-ide-config.py --registry". Fixed at
   the source: `templates/agent-rules.yaml`, then regenerated.

   Worth recording beyond the slip: **the source made the contradiction plainer
   than the generated file did.** In `agent-rules.yaml`, `fail_closed: false` sits
   directly above a note reading "The configured command falls back to printing a
   deny when the launcher cannot run." The field and the prose describing it
   disagreed, three lines apart, and had since 2026-09-17.

2. **`test-that-cannot-fail` — my own first attempt at the fifth test could not
   run.** It checked the other direction (an adapter declaring `false` while
   emitting a `failClosed` key) and its own guard fired: "none of
   `['antigravity','copilot','gemini','codex']` has a generated config — this test
   checked nothing." All four fail-open adapters have no verified config schema,
   so `render_config` refuses to generate one and there is nothing to inspect.
   That direction is unenforceable today. Replaced with a source rule —
   `render_config` may not hardcode `failClosed` — which is enforceable now and
   guards the exact regression this slice fixes. The unenforceable direction is
   stated in the test's docstring rather than dropped silently.

## Pass 2 — findings: 1

1. **The same mistake once more, in the design's scope.** Having found in Pass 1
   that I had edited a generated file, I corrected the change to
   `templates/agent-rules.yaml` — and left the design's scope naming only
   `templates/governance.json`. The stop gate caught it: "templates/agent-rules.yaml:
   no complete active design note covers it." One root cause, two symptoms: I
   wrote the design against the artefact I first reached for rather than the file
   that owns the value. Scope widened, and the design now says which file owns it.

## Pass 3 — findings: 0

Fresh sweep, nothing new.

- Both halves proven by breaking them, not by reasoning: restoring the hardcoded
  `"failClosed": True` fails `test_the_generator_never_hardcodes_fail_closed`;
  reverting `claude` to `false` fails **two** tests — the registry-agreement one
  and the mechanism one — which is the defect this slice exists for.
- 70 tests across the four suites that pin this area pass together.
- `neutral` is absent from `governance.json`'s `ides` by design (it is a contract
  profile, not an IDE, and the code says so); the registry-agreement test only
  compares the adapters the registry lists, so it neither ignores a real drift nor
  fails on a deliberate absence.
- The change is a value and a field read: `.cursor/hooks.json` renders identically
  (cursor was and is `true`), and Claude's config never carried the key, so no
  generated tenant file moves.
- `ruff check` and `ruff format --check` clean; `B905` (`zip()` without `strict=`)
  was raised and fixed rather than suppressed.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the hardcoded literal and the registry field
                                          were two statements of one fact; there is now one, and
                                          the generator reads it
Group 2 · Quality / safety            [x] checked — no behaviour changes: Claude already denied
                                          via the launcher, and Cursor's rendered config is
                                          byte-identical. What changes is what the registry says
Group 3 · Architecture / hygiene      [x] checked — no abstraction invented to unify three
                                          genuinely different mechanisms; the test reads each one
Group 4 · Process                     [x] checked — two passes; Pass 1 caught me editing a
                                          generated file, and caught my own test being unable to run
Group 5 · Intuitive UI                [x] n/a — no screen. The reader-facing surface is
                                          docs/process-gates.md, which stated one blanket rule and
                                          now names which four IDEs fail open
Group 6 · Signal integrity            [x] checked — this is the slice: one boolean carried two
                                          questions, and for DEFAULT_IDE it answered the wrong one
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; no credential read

Tests added/updated:      5 in scripts/test/test_fail_closed_declared.py — the registry and the
                          adapters agree; Cursor's key follows the registry; Claude's mechanism is
                          the launcher's deny fallback; the neutral profile's is the contract's
                          fall-through; and the generator never hardcodes the value. Three of the
                          five were proven to fail against the pre-fix tree.
Mutation-checked:          not added to the catalogue. The two proofs above are the equivalent and
                          are the mutations that matter here: the hardcoded literal, and the wrong
                          declared value. A catalogue entry would re-run the same two.
Fixtures re-pinned:        templates/governance.json regenerated from agent-rules.yaml with
                          generate-ide-config.py --registry; .agent-rfc/fixtures/knowledge_graph.json
                          via map_codebase.run_map(force=True)
KG query:                 kg:4ca7f09d0ed5
Gates run locally:         full suite, the four IDE/contract suites together (70 passed), ruff check
                          + ruff format --check, artifacts, pillars, KG drift
Declared gaps:             (1) an adapter declaring fail_closed=False while emitting a failClosed
                              key cannot be caught until one of those four IDEs gets a verified
                              config schema — stated in the test; (2) the test reads
                              .githooks/process-gate and the contract as TEXT, so a deny fallback
                              that stops working while the string stays would still pass; proving it
                              behaviourally needs a real IDE, which is the same limit the scratch
                              tenants have for the commit gate.
```
