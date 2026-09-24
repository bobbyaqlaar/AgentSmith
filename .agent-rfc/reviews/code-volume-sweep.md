# Review — code volume sweep

Design: `.agent-rfc/designs/code-volume-sweep.md`. Owner, 2026-09-24: "Thorough review of the
current code base, documentation based on the review levers — multiple passes up to 4 times unless a
pass comes back with zero findings", plus one new lever aimed at code volume.

**The measurement first, because it changes the verdict.** 63k lines of Python at 24% prose,
27k lines of Markdown. Four cross-file duplicate regions of eight lines or more across the whole
non-test tree; no module-level function without a caller; no test that cannot fail. Sampling the
densest files (`runtime/judging.py` at 49% prose) found reasoning, not padding. This repository is
not bloated in the way the question implies, and saying so is part of the answer. What it carries is
**residue from its own fixes** — which the new lever is named for.

## Pass 1 — findings: 8

1. `every-line-earns-its-place` / `no-redundant-artifacts` — **`docs/review-lever-notes.md` carried
   every group heading from 2 to 6 twice**, each stray copy followed by a blank line and a
   separator. Fifteen lines saying nothing in the document that teaches this repo to review itself,
   and `test_lever_notes.py` could not see it: it parses `###` slugs and never looks at `##`. This
   is the evidence the new lever was entered with, so it dropped `(unevidenced)` the day it arrived.
2. `every-line-earns-its-place` / `one-catalog` — **three byte-identical 12-line `_repo_root`
   shims** in `runtime/{tracing,llm_gateway,moderation}.py`: a two-line body calling
   `runtime.config.repo_root` under a nine-line docstring recounting the incident that unified them.
   All three modules can import `runtime.config` directly. The duplication was removed from the
   logic and preserved, three times over, in the prose about the logic.
3. `implemented-not-invoked` / P11 — **the two reference stacks exported unredacted spans.**
   `configure_tracing`'s own docstring says it exists because assembling a provider by hand is three
   steps that get half-done; `scripts/local_agent_stack.py` and `scripts/multi_agent_system.py`
   assembled it by hand and omitted `AgentIdentityProcessor` and `TraceRedactor`. `README.md` offers
   both as "a shape to copy". This is the finding that is not about volume.
4. `merge-the-right-copy` — **`AgentLogger.resolve_hitl` had zero callers**, while
   `promote-learning.py::_mark_log_resolved` — a near-verbatim copy — was the only one that ran. The
   rule for "an unresolved MAJOR/CRITICAL entry" lived in two places and the live one was the copy.
5. `declared-vs-enforced` — **an `IMPLEMENTS` edge documented in `docs/DESIGN.md` and in
   `local_knowledge_graph.py`'s header, created only by `link_file_to_guardrail`, which nothing
   called.** No committed graph has ever held one. `as_json` was dead beside it.
6. `one-catalog` — **the four compliance frameworks written out five times**: `FrameworkTags`'
   fields, the registry loader, `_filter_controls`, the JSON projection, and argparse `choices`.
   `_filter_controls` was the one that failed by returning nothing rather than by failing.
7. `no-redundant-artifacts` — `AgentWorkflowInput`, a dataclass nothing constructs.
8. `no-redundant-artifacts` — `### CD Golden Dataset Commits` twice in `docs/DESIGN.md`, 650 lines
   apart, each carrying a sentence the other did not.

Fixed: all eight. The rule files' own contract is now pinned harder than before —
`test_one_root_finder_and_a_tenant_beats_its_parent_repo` used to call the three shims and pass;
it now asserts that no module under `runtime/` defines a root finder at all, and reintroducing one
was run to confirm it fails.

## Pass 2 — findings: 5

1. `when-the-fallback-fails` / `merge-the-right-copy` — **the merged `NoopTracer` was broken in
   exactly the path it exists for.** It returned this module's `_NoopSpan`, which had no
   `__enter__`: it had only ever been yielded from `agent_span`'s own contextmanager, while every
   caller in the two scripts writes `with tracer.start_as_current_span(...) as span`. One deleted
   copy also had `set_status` and the survivor did not. This is the lever's second half — the merged
   version faces inputs no copy saw alone — landing on the merge made in Pass 1. Fixed, and
   `test_the_noop_tracer_survives_the_way_callers_use_it` was run without `__enter__` to confirm it
   fires.
2. `no-copy-paste` — `portal/lib/devRead.ts` restated all fourteen fields of `DevCommit` to add one.
   `extends DevCommit` instead; a field added upstream was previously invisible here. The file next
   door already uses the idiom (`HeadDesign = DevDesign & { path: string }`).
3. `parameterize-dont-clone` — the `ts-react` and `ts-react-pnpm` scratch-tenant fixtures are
   byte-identical except `package.json`, the lockfile and one `scripts/` directory: about twenty
   duplicated files to vary one thing. **Recorded, not fixed** — see stated limits.
4. `search-before-writing` — `.github/actions/install-python-deps` exists and is provisioned into
   tenants, while five workflow templates hand-roll `pip install`. **Recorded, not fixed.**
5. `one-catalog` (naming) — `write_evidence_pack` exists in `scripts/security/report.py` and in
   `scripts/delivery_evidence.py` with different signatures and unrelated meanings. Noted; renaming
   a published function is out of proportion to the confusion.

## Pass 3 — findings: 4

All four are on the work of passes 1 and 2, which is what a re-review is for.

1. `no-redundant-artifacts` — routing `promote-learning` through `resolve_hitl` left `_log_path()`
   with no callers. Neither ruff nor my own Pass 1 sweep caught it: the sweep counts bare
   identifiers, and `self._log_path` in `agent_logger` kept the count above one. A detector's blind
   spot is a finding. Deleted.
2. `matches-the-existing-component-language` — the `AgentLogger` import went in function-local while
   this file imports its sibling scripts at module level. Moved, and the block it was in went with
   it.
3. `denied-vs-missing` — my comment on `_filter_controls` described the old defect and not the new
   behaviour, so a reader could not tell what an unknown framework name does now. Rewritten to say
   it raises, at the one place that knows the names.
4. `design-before-code` — **the new lever was incomplete and only a test knew.**
   `test_every_lever_has_a_design_phase_counterpart` requires every slug in `review-levers.md` to
   have a build-time reframe in `docs/design-review-checklist.md`; a lever without one is advice you
   can only act on after the fact. Added.

Considered and declined in this pass:

- Deleting the endpoint-trap comment's replacement too. The `…/v1/traces` double-append reasoning
  now lives in `runtime/otlp.py` beside the function and in `test_otlp_endpoint.py`; a third
  retelling at a call site that reads `span_exporter()` is the duplication this sweep removes.
- Collapsing the ~12 lines the two reference stacks still share into a
  `configure_single_run_tracing` helper. They exist to be read and copied; hiding `configure_tracing`
  behind another wrapper makes the shape on offer less copyable, which is the whole point of the
  files.
- Compressing the repository's explanatory prose. The lever says shorter, never denser, and the
  measurement above says this prose is load-bearing.

## Pass 4 — findings: 0

Re-ran the detectors against the result rather than re-reading the same diffs:

- cross-file duplicate regions of eight lines or more: **4 → 2**, and both survivors are the
  deliberate `_dotenv_value` / `_repo_root` mirrors across the `scripts/` ↔ `runtime/` package
  boundary, pinned by `test_dotenv_parsers_agree` and `test_shared_root_matches_runtime_root`.
  That is the correct end state, not a remaining defect;
- module-level definitions with no caller: **none**;
- ruff, mypy in a clean environment, the full Python suite, `tsc --noEmit` and the portal suite: all
  green.

**Net: −136 lines of production Python, +89 of test**, plus the documentation corrections.

## Stated limits

- **The two scratch-tenant fixtures stay duplicated.** Restructuring them touches a green CI job
  that proves adoption across five stacks, and a tenant fixture arguably *should* look like a whole
  repository. It is a slice of its own, not a line item in a review sweep.
- **Five workflow templates still hand-roll `pip install`** while a composite action exists for it.
  These are tenant-facing: changing them changes every adopted repository's CI, which is not
  something to do as a side effect of a review.
- **The tracing change gains identity stamping only where identity is bound.** Both scripts keep
  `tenant.id` on the resource, so nothing is lost, but neither wraps its pipeline in
  `agent_context`, so `AgentIdentityProcessor` has nothing else to stamp. Binding it is the fuller
  fix and a separate change.
- **`CAUSED_INCIDENT` and `ProductionIncident` remain declared and unwired** — written only by
  `inject_production_learning`, which nothing but its test calls. Unlike `IMPLEMENTS` they have a
  test and a designed purpose, so they are marked in the docs rather than deleted.
- The `every-line-earns-its-place` counterweight is not enforced by anything. Nothing stops a future
  pass from golfing a loop into an unreadable expression and calling it progress.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — this sweep is Group 1; duplicate regions 4 → 2,
                                          both survivors pinned
Group 2 · Quality / safety            [x] checked — the no-op fallback now survives the way callers
                                          use it, proven by removing __enter__
Group 3 · Architecture / hygiene      [x] checked — the KG ontology in docs/DESIGN.md now describes
                                          the graph the code builds
Group 4 · Process                     [x] checked — four passes, findings on my own work in two of
                                          them
Group 5 · Intuitive UI                [x] n/a — no screen changed; portal/lib/devRead.ts is a type
Group 6 · Signal integrity            [x] checked — an unknown compliance framework raises instead of
                                          reporting zero controls
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      runtime/test/test_tracing.py (+4), runtime/test/test_config.py (rewritten
                          to assert the property it meant to)
Mutation-checked:          the two new assertions were each run against a reintroduced defect
                          (a restored _repo_root shim; _NoopSpan without __enter__) and both failed
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:cc87117d70b3
Gates run locally:         ruff, mypy in a clean environment, the full Python suite (1917 passed),
                          tsc --noEmit, npm test in portal/
Declared gaps:             (1) scratch-tenant fixtures still duplicated; (2) five workflow templates
                              still hand-roll pip install; (3) neither reference stack binds
                              agent_context; (4) CAUSED_INCIDENT declared and unwired; (5) nothing
                              enforces the new lever's "never denser" half
```
