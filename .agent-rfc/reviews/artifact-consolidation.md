# Review — one artifact per type (G5b, AgentSmith's half, commit 1 of 2)

Design: `.agent-rfc/designs/artifact-consolidation.md`, written after the owner's rule of
2026-09-18: cross-references minimised and never by number, documentation for humans with the
machine logic in the graph and the code, history in the archive and the logs only.

**Built evidence (2026-09-18):**

- **Every move is whole-document and `git mv`**, so each file's history follows it: the backlog,
  the archive, the manual and the design moved; the three dated review files and the observability
  audit became `docs/REVIEW_LOG.md`; the session handoffs and the `docs/superpowers` plans and
  specs became a section of `docs/PRODUCT_ARCHIVE.md`; `OPERATIONS.md` became Part II of the
  manual, with its headings renamed from numbers to names.
- **One thing was deleted rather than moved:** `OPERATIONS.md`'s Appendix C, a table mapping areas
  to `SPECS.md §23`-style numbers and to implementation files. It existed only to cross-reference, <!-- xref: example -->
  and the owner's rule puts that logic in the knowledge graph.
- **Measured before rewriting.** 170 section-number pointers across 91 files; 165 named a real
  section, and **5 were dead** — `§699` and `§695` were *line numbers* where the OTLP-endpoint
  convention once sat, twenty lines above where it sits now.
- **The rewrite turns a number into a name**, as a breadcrumb — `docs/DESIGN.md › Installation
  Procedure` — which needs no quotes or brackets, so it is safe inside a string, a comment or a
  JSON value. A reference to the same document names the heading instead. `.agent-rfc/**` records,
  test fixtures, the registry's stray-detecting patterns and lines marked `xref: example` were left
  exactly as written.
- **Verified by what would refuse it:** 0 relative Markdown links broken across the eight moved or
  merged documents; 0 numbered pointers left outside the deliberate examples; the commit gate's own
  cross-reference rule run over all 6,229 added lines, 0 refusals; every changed Python, shell,
  JSON and YAML file parses; `npx tsc --noEmit` clean in `portal/`.
- **Result:** `process_gate.py artifacts` — one file per type, no strays — and `artifacts` is
  `enforce` from this commit.

## Pass 1 — findings: 6

The first five are defects the bulk rewrite introduced, found by reading its output rather than
its counts. The sixth is a defect in G7 that this migration exposed.

- `test-that-cannot-fail` — **finding:** my "no numbered pointers left" check used `git grep -E`,
  which is POSIX: `\s` matches nothing there, so the check could not have found anything and
  reported zero. Re-run with PCRE, it found **17**.
- `docs-match-behaviour` — **finding:** relative links inside a moved file were written for its
  OLD location. `[…](./OPERATIONS.md)` in the design was relative to the root, and the design now
  lives in `docs/`. Every link in a moved file is re-based now — and two merged files came from
  more than one directory, so each link is resolved against every old base until one names a file
  that existed.
- `single-source-of-truth` — **finding:** the prose pass ran after the link pass and rewrote
  `](UserManual.md)` inside `docs/` into `](docs/UserManual.md)`, a path to `docs/docs/`. Link
  targets are held out of the prose pass now.
- `docs-match-behaviour` — **finding:** the number-to-name rule mangled forms it did not know:
  a range (`§0–1` → "Install & Start**–1**"), sub-sections (`§5.4` → "Component Inventory**.4**"),
  slash pairs (`§9/§24` → "Evaluation Framework**/§24**"), an appendix that never existed
  (`§D.5b`), and a stub whose content lives in the archive ("Deliverables Checklist **(moved)**
  Phase 5"). Each of the 18 was fixed by hand — named, joined, re-pointed at the archive, or
  dropped where a CI file header did not need a pointer at all.
- `gate-integrity` — **finding:** two explanations **of the cross-reference rule itself** lost
  their meaning. They showed the refused form as an example without the example marker, so the
  rewrite "corrected" it — and `process_gate.py` then said a pointer into numbering looks like
  `docs/DESIGN.md › Tenancy Model`, which is the allowed form. The bad examples are restored and
  marked.
- `ambiguous-signals` — **finding, in G7:** `verify_system.py --governed` said "Governed" on the
  strength of an `agentsmith gates run --only repo-tree` — **one gate** recorded as if it were the
  list. A filtered run is recorded as filtered now, and `--governed` says so rather than passing,
  with a test.

## Pass 2 — findings: 1

- `fixture-truth` — **finding:** nine tests failed once `artifacts` went to `enforce`: the fixture
  repo copies AgentSmith's own config and has none of the six documents, so every stop and sweep
  in it blocked on a rule those tests are not about — the same shape as the knowledge-graph mode in
  G4. The fixture keeps `report`, with the reason written where it is built; the artifact rule's
  own tests set the mode each one needs.

## Pass 3 — findings: 2

Found by committing this change: the commit gate accepted it, and CI's recomputation of the same
commit refused it. Both are defects in the gates, predating this migration — renaming four
documents was simply the first change to exercise them.

- `one-verdict`, `environment-parity` — **finding (G4):** the `KG query:` hash differed between
  the two gates for one commit. The commit gate lists files with `git diff`, which detects renames
  and names only the new path; CI uses `git diff-tree`, which does not, and names the old path too
  — 244 files against 247. The scope is now defined once: the files the change *leaves*, since a
  deleted path is nothing a reviewer can read. A test commits a rename and runs both gates on it.
- `gate-integrity` — **finding (since the gates were built):** the same difference meant a
  rename's OLD path never reached the commit gate's design-scope check, so moving a gated file out
  from under its design passed locally and was caught only by CI after the push. The commit gate
  lists files with `--no-renames` now, as CI does. Both fixes were mutation-checked: reverting
  either fails its test.

## Pass 4 — findings: 0

Commit 1 verified: every move, both gate fixes, CI green on GitHub after the push.

---

# Commit 2 of 2 — the distillation (2026-09-18)

The owner's rule applied to what is left in the documents: the design, the manual and the README
carry the current system and its reasons; the story of how it got that way lives in the archive
and the review log.

**Built evidence:**

- **Measured first.** After the moves, history was thinner than expected — 13 of 264 prose
  paragraphs in the design, 15 of 451 in the manual. What the documents carried everywhere was the
  *structure* that invites numbered pointing: 48 numbered headings and 137 bare `§N`
  self-references. Those went first, mechanically and origin-aware: in the manual, Part II's
  `§0`–`§10` meant the old operations guide and its `§29`/`§30` meant the design.
- **The editorial pattern was one pattern.** Nearly every history-bearing paragraph was a current
  rule followed by the story of how it became the rule ("used to…", "until 2026-08-25…"). The rule
  and its reason stay; the dated story moves, word for word, to a new archive section that says
  where each entry came from — 14 clauses. Nothing was deleted outright.
- **Kept on purpose:** the design's decision table (it is current decisions with their reasons,
  not a dated log), the GCP-promotion-suspended notice and the live-verification record (current
  status a reader acts on), and archive entry IDs such as `P2a` in code comments — an entry ID is
  a stable name, the minimal way to cite history, unlike a position such as `5.10`.
- **One pointer became a statement.** The manual sent readers to the archive's P11 entry for the
  secrets a staging deploy *requires*. A prerequisite belongs with the procedure, so the three
  secret names are stated where the deploy is.
- **The README is the map, once.** Its preamble and the design's no longer list the other
  documents; the README's table says which document answers which question.

## Pass 5 — findings: 4

- `declared-vs-enforced` — **finding, in commit 1's claim:** I reported "zero numbered pointers
  left" after searching only for `§`. 68 more cited archive and backlog items by number without
  one (`docs/PRODUCT_ARCHIVE.md 5.10`) — a form the gate's own rule cannot see either. Of those, 63
  name an entry that exists and stay as stable IDs; 5 named nothing — three hooks pointed at a
  backlog item (`P1a`) that had closed and moved to the archive, and two cited items that exist
  nowhere. Those comments already carried their reasoning, so the dead pointer went and the
  explanation stayed.
- `docs-match-behaviour` — **finding, same gap:** commit 1's rewrite skipped any old path
  preceded by `/` or `.`, so three survived: the design pointing at `§D.6/OPERATIONS.md`, the
  archive at `AgenticFramework/TestbedFeedback-2026-07-21.md`, and the installer's closing message
  telling every user the spec is at `./SPECS.md`. That message was wrong twice over: `./` is
  wherever the user ran the installer from, and its `./Readme.md` never existed on a
  case-sensitive filesystem. It prints paths into the checkout now, or the repository when piped.
- `docs-match-behaviour` — **finding, same gap:** commit 1 re-based only links to Markdown files
  inside moved documents, so the manual's links to `./docker-compose.yml` pointed into `docs/`.
- `ambiguous-signals` — **finding:** "see Appendix A" survived in the installer and the manual
  after the appendices became named sections.

## Pass 6 — findings: 0

Every document over its final text: links and anchors resolve (0 broken), no numbered heading or
`§` reference remains in the design, the manual or the README, the cross-reference rule refuses
nothing among the added lines, `artifacts` is clean in `enforce`, every changed shell and YAML
file parses, and the full suite passes.

Every lever over the final tree: the moves, the merges and what each merged file's history note
says, the link bases, the name forms, the exclusions, the tree in `docs/DESIGN.md`, the CI step
that reads it, the `artifacts` mode and the G7 fix. Considered and declined: rewriting the old
per-change records under `.agent-rfc/` so their paths resolve. They are the evidence the gate
checked when each change landed, and they say what was true then.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_governed_tenant.py (+1: a filtered gates run is not proof);
                          test_gate_kg.py (+2: one scope for a renaming commit in both
                          gates; a renamed gated file needs a design at commit time);
                          test_env_var_documentation.py and the drift and wiring tests
                          follow the moved paths
Mutation-checked:          n/a for the moves — a document move has no blocking path of its
                          own; the G7 fix's one blocking path is covered by its new test
Fixtures re-pinned:        yes — docs/DESIGN.md's repository tree, the gates table (a step
                          name changed), .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:2ebec8f194aa
Gates run locally:         ruff, the full pytest suite, `process_gate.py artifacts` (enforce,
                          clean), the cross-reference rule over every added line, tsc in
                          portal/, the repo-tree drift gate, --governed
Declared gaps:             (1) the reliability pack's threshold rationale is still in the
                              archive's design note rather than distilled into the design;
                          (2) the cross-reference rule sees `X.md §N` and `X.md#L120`, not <!-- xref: example -->
                              `X.md 5.10` — found in pass 5, and a rule change, so recorded in
                              the backlog rather than made here;
                          (3) `records: single` is not part of this change, by design.
```
