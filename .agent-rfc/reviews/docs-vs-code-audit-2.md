# Review — two more rounds of the documentation against the code

Design: `.agent-rfc/designs/docs-vs-code-audit-2.md`. Owner, 2026-09-26: "Since each pass found
something, let's repeat the three pass exercise twice."

**Four classes were examined across two rounds; numbered below as this repository's gate
requires — `## Pass N — findings: K`, sequential — with the round and class named under each.** The stopping rule — a pass finding nothing before the third ends the
round — fired in both rounds. Each pass took a class not tried in
`.agent-rfc/reviews/docs-vs-code-audit.md`, because repeating those three would have found nothing
by construction. **2 findings**, both in Round 3 Pass 2, and both the kind a stranger meets first.

## Pass 1 — findings: 0

**Round 2, environment variables.**

163 variables read by code, 69 in a canonical table. Zero findings, for three reasons worth stating
rather than leaving as silence:

- **both directions are already tested.** `test_env_var_documentation.py` (a variable the code reads
  must appear in some tracked `.md`) and `test_documented_env_vars_exist.py` (a variable the docs
  name must be read by something) already cover it.
- **"absent from the canonical table" is not falsifiable.** Neither `docs/DESIGN.md § Environment
  Variables` nor `docs/UserManual.md § Runtime Flags` claims to be exhaustive, and the existing test
  is deliberately loose about where — a variable documented in a design note passes on purpose.
- **the documented effects hold.** `AGENTSMITH_SWEEP_BATCH` defaults to 200
  (`scripts/process_gate.py:1728`), `AGENTSMITH_IDE` unset reads as `"unknown"` and not as a guess
  (`:1903`), and `SEMVER_LOOP_GUARD` is still read (`hooks/post-commit:20`).

My first extraction reported 65 variables "documented nowhere". All were bash **local** variables —
`BOLD`, `VENV_DIR`, `TARBALL`, `PY_MAJOR` — because a `${VAR}` pattern cannot tell an environment
input from a local expansion. Recorded because a detector that cannot make that distinction produces
a finding count that looks like work and is not (`check-that-fires-on-everything`).

Round 2 ended here under the owner's rule.

## Pass 2 — findings: 0

**Round 3, runnable examples.**

Every fenced block claiming a parseable language, parsed: **13 JSON, 16 YAML, 147 bash** (`bash -n`),
17 Python. Zero failures in JSON, YAML and bash — which matters most for bash, since those are the
blocks a reader copy-pastes. The six Python failures are `await` and `return` shown outside their
enclosing function, the normal way to quote a fragment, and are not defects.

## Pass 3 — findings: 2

**Round 3, cross-document consistency.**

Facts stated in more than one place, checked against each other and against the registry. The
compatibility matrix is consistent — `CHANGELOG.md` is canonical and `docs/DESIGN.md:2219` carries an
abridged 2.0.x row with matching minimums and a pointer for the full text. The pillars were not.

1. `docs-match-behaviour` — **the pillar section was titled "Ten Operational Pillars" and documented
   fourteen.** `docs/DESIGN.md:224` said Ten; `### Pillar 1` through `### Pillar 14` followed it, and
   prose at two more places still said "the Ten Pillars". `README.md` called them "The Fourteen
   Pillars" and pointed at `docs/DESIGN.md › Ten Operational Pillars` — a cross-reference naming a
   title by a count that had been wrong for four pillars. The heading is now count-free, so it cannot
   go stale the same way again.
2. `declared-vs-enforced` — **P15 and P16 are answered in every design and were specified nowhere a
   reader looks.** `templates/governance.json` defines 16 pillars; a design must answer the 14 whose
   `check` contains `design` (`scripts/gate_models.py:384`), which is P1–P4 and P7–P16. `README.md`
   listed fourteen — but a *different* fourteen: it included P5 and P6, which are `check: [review]`
   and never asked of a design, and omitted **Ambiguous Signals** and **Recovery Paths**, which are.
   So a contributor could read both canonical documents, write a design answering everything they
   describe, and have the gate reject it for two pillars they had never seen. Going public makes that
   a stranger's first experience.

   Fixed by specifying both in `docs/DESIGN.md` to the same shape as the other fourteen, listing them
   in `README.md`, and stating the 16/14 split with where the authority is. `docs/PRODUCT_BACKLOG.md`'s
   article plan said "Ten Pillars" and is corrected too — it is a plan for a public article.

## Pass 4 — findings: 0

**Round 3, registry catalogues in prose.**

Every catalogue the gate reads, against the canonical documents: **3 artifacts, 6 IDEs, 16 pillars** —
all named. `records`' three keys are config names, not catalogue items, and their contents are
documented: `docs/process-gates.md:656` shows a `records: single` design with `###` subsections where
the file-per-change mode uses `##`, which looks like a heading-level error against `_section`'s
`^## ` and is not — in that mode a design is a `## Active change:` section, so its parts sit one
level deeper, and the document says so ("A section is normalised into the shape the checkers already
read").

## Pass 5 — findings: 0

**Verification of the fixes above.**

- The three new tests each run against a reverted fix and each failed: a removed `### Pillar 16`
  section, a renumbered README entry, and the old "Fourteen Pillars" heading.
- `grep` for every stale spelling across the three canonical documents: none left.
- ruff, mypy, the doc suites and `test_cli_install.py`: green.

## What became a test

The pillar list is prose restating `templates/governance.json` across a boundary that cannot be
merged — `pin-unremovable-duplicates`. Three tests in
`scripts/test/test_design_and_validation_docs.py`, reading the same registry `scripts/gate_models.py`
reads, so they cannot drift from the gate:

- `test_every_pillar_the_gate_knows_has_a_section_in_the_design_doc`;
- `test_every_pillar_a_design_must_answer_is_listed_in_the_readme` — keyed on `check` containing
  `design`, not on a count, so adding a pillar to the registry fails until it is documented;
- `test_no_document_states_a_stale_pillar_count` — asserts against the **wrong** spellings rather
  than for the right one, which is what makes it survive the next pillar being added.

Round 2's and Round 3 Pass 1's extractions stay in the scratch directory: the env-var ground is
already held by two tests, and a parser for fenced blocks would flag every deliberate fragment.

## Stated limits

- **Two of the six planned passes never ran**, both stopped by the owner's rule: Round 2's config-key
  and stated-count classes. The count class was partly covered by Round 3 Pass 2 finding the pillar
  counts; config keys are untested ground.
- **Four classes are now pinned by tests and one is not.** The pillar list, the Command Reference and
  the lever documents have tests; cross-document *prose* consistency in general does not, and cannot
  be reduced to one.
- **`docs/PRODUCT_ARCHIVE.md` still says "Ten Pillars"** and is deliberately left: recording what was
  true when written is its job.
- **The new tests pin presence, not correctness.** A `### Pillar 15` section that describes the wrong
  thing passes. Nothing checks that a pillar's prose matches its `design_question` in the registry.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — the tests read the registry the gate reads, not a
                                          third copy of the pillar list
Group 2 · Quality / safety            [x] checked — no behaviour changed; two pillars gained the
                                          specification the gate already demanded
Group 3 · Architecture / hygiene      [x] checked — the heading carries no count, so the failure
                                          cannot recur in the same shape
Group 4 · Process                     [x] checked — four passes, two rounds, both stopped by the
                                          owner's rule and both reported as stopped
Group 5 · Intuitive UI                [x] n/a — no screen; README is prose
Group 6 · Signal integrity            [x] checked — each zero-finding pass records what it covered
                                          and why it found nothing, never silence
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_design_and_validation_docs.py (+3), each confirmed
                          failing against a reverted fix
Mutation-checked:          the three new tests were each run against a restored defect; no production
                          code changed, so no mutation suite applies
Fixtures re-pinned:        not required — documentation and tests only
KG query:                 kg:00196ce634e7
Gates run locally:         ruff, mypy in a clean environment, the doc suites, test_cli_install.py
Declared gaps:             (1) two planned passes never ran; (2) prose consistency in general is
                              unpinned; (3) PRODUCT_ARCHIVE deliberately keeps the old count;
                              (4) the new tests pin presence, not correctness
```
