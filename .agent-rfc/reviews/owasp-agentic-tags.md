# Review: owasp-agentic-tags

Gap 1 of `docs/PRODUCT_BACKLOG.md`, after the owner's instruction of 2026-11-09 to fix the gaps.

## Pass 1 — findings: 2

Against `docs/review-levers.md`, with five hand mutants.

1. **`result.schema.json` embeds the same framework tags,** so it drifted from the model as soon as the field was added, and the contract's own conformance run failed. Regenerated from the model.
2. **A filter line on the new page did nothing,** because only tagged controls appear there with or without it. A surviving mutant showed this. Removed; the page lists all ten whatever the filter, and says why.

## Pass 2 — findings: 0

- The tags were generated from `docs/security-framework-map.md`, and `test_the_agentic_tags_are_the_maps_and_only_where_it_claims_coverage` holds them there in both directions. A control is tagged only where the map's row is at least partial.
- The evidence pack's `owasp_agentic_top10.md` lists all ten entries, and ASI03, ASI04, ASI05 and ASI07 as "not covered by any control".
- Security registry, evidence-pack, contract and first-run suites: 87 passed.
- Four hand mutants, all caught: a not-covered entry tagged; a covered entry untagged; uncovered entries left out of the page; the loader dropping the tag.

## Sign-off

Group 1 · DRY & shared code — [x] checked — the map is the one source; the registry follows it under test.
Group 2 · Quality / safety — [x] checked — additive in the model and both published schemas; a registry without the field loads.
Group 3 · Architecture / hygiene — [x] checked — one more page beside the four the pack writes.
Group 4 · Process — [x] checked — design first; map, CHANGELOG and backlog updated.
Group 5 · Intuitive UI — [x] n/a — no screen changes; the pack is Markdown.
Group 6 · Signal integrity — [x] checked — no tag where the map says not covered, and an uncovered entry is printed rather than omitted.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: two in `scripts/test/test_security_registry.py`, two in `scripts/test/test_security_evidence_pack.py`.
Mutation-checked: yes, by hand; five mutants, four killed and one that showed dead code, removed.
Fixtures re-pinned: `fixtures/security/control_registry.json`, `contract/security/v1/registry.schema.json`, `contract/security/v1/result.schema.json`, `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the security suites; ruff; mypy; the process gate against the commit.

Levers reviewed: `single-source-of-truth`, `declared-vs-enforced`, `failure-is-not-a-result`.

KG query: kg:29a34a6a6e03
