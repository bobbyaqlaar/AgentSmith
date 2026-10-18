# Review — the agentic 42001 coverage page is declared reference documentation

Design: `.agent-rfc/designs/declare-agentic-coverage-doc.md`. Raised by the artifacts gate against
`65ecccc`, which added `docs/agentic-42001-coverage.md` without declaring it.

**Built evidence (2026-10-18):**

- **The gate's own words**, before the change: *"docs/agentic-42001-coverage.md is neither an
  artifact nor declared reference documentation — fold it into the artifact that owns it, or
  declare it in `extends.artifacts.reference`"*. CI enforces the same check, so `65ecccc` could not
  have been pushed as it stood.
- **The edit:** one path added to `extends.artifacts.reference` in
  `.agenticframework/process-gates.json`, beside the nine contract protocols. `git diff --stat`
  shows **1 file, 2 insertions, 1 deletion** (the deletion is the comma on the line above). The
  file still parses, 10 reference entries, and `gated` (27), `not_gated` (3) and
  `pillars.mode: enforce` are unchanged — read back from the parsed JSON rather than from the diff.
- **Repo-local, not tenant-facing:** `templates/governance.json` is the registry tenants receive,
  and the three ISO/UAE maps are there because a tenant inherits them. This page is about
  AgentSmith's own coverage of a third-party briefing, so it goes in this repository's own list.

## Pass 1 — findings: 0

- `declared-vs-enforced` — the page is owned by the registry the gate reads; the check passes
  because the document was declared, not because anything was relaxed.
- `test-that-cannot-fail` — the proof is the gate's verdict flipping on this one line: it reported
  the problem before and does not after. Nothing else in the config moved, which the parsed-value
  read above is the control for.
- `two-owners-two-cadences` — the tenant registry and the repo's own list ship separately; putting
  a path tenants do not have into the shipped file would have told every tenant about a document
  they cannot open.
- Considered and declined: folding the 200 lines into `docs/iso-42001-control-map.md`. That file is
  this repository's thematic self-map; the new page answers someone else's briefing. Two questions,
  two owners, kept apart as `uae-regulatory.md` and `security-framework-map.md` already are.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] n/a — one line of configuration
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked — the gate's verdict is the test
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      none — the rule is `scripts/gate_artifacts.py`'s, already covered by
                          scripts/test/test_gate_artifacts.py; this is its configuration
Mutation-checked:          n/a — configuration, no branch to mutate
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:f519fd2ef58a
Gates run locally:         the process gate itself, re-run after the edit
Declared gaps:             none
```
