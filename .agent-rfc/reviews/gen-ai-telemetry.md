# Review: gen-ai-telemetry

Gap 7 of `docs/PRODUCT_BACKLOG.md`, after the owner's instruction of 2026-11-09 to fix the gaps.

## Pass 1 — findings: 2

Against `docs/review-levers.md`, and against the conventions themselves, read from `open-telemetry/semantic-conventions-genai` at `e6658f14c9d9` rather than from secondary write-ups.

1. **The token counts were catalogued as conditional,** which in this contract means "present exactly when". Every existing emitter, the published fixture included, would have failed the judge: a version-1 promise broken by an addition. Made optional.
2. **Provider values had to come from the registry, not memory.** Checked against the registry's member list (`gcp.gemini`, `aws.bedrock`, `x_ai`, `mistral`, `ollama`). A provider it does not list keeps its own lowercase name, which the conventions allow.

## Pass 2 — findings: 0

- `scripts/test/test_gen_ai_telemetry.py` reads real spans from an in-memory exporter, for a gateway call and a tool call; `scripts/test/test_telemetry_contract.py` holds every emitted name to the catalogue. 52 passed.
- Six hand mutants, all caught: a provider value off the conventions; a bare id naming a provider; a token count, the tool name or the request model not written; an empty provider written.
- The whole Python suite: 2706 passed, 17 skipped, none failed.
- The CHANGELOG's wire table names each new attribute with its release, which `test_the_wire_contract_table_names_catalogued_attributes_with_their_release` checks. It also gains the rows `app.commit` and `app_commit` from the accountability chain, which that change had not added.

Left for a later version: making the GenAI names required, once upstream marks them stable. On the backlog.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one pin and one provider map in `agentsmith/telemetry_contract.py`.
Group 2 · Quality / safety — [x] checked — attribute writes stay inside the gateway's fail-open block.
Group 3 · Architecture / hygiene — [x] checked — additive; `llm.*` unchanged and still required.
Group 4 · Process — [x] checked — design first; protocol, catalogue, CHANGELOG and backlog updated.
Group 5 · Intuitive UI — [x] n/a — no screen changes.
Group 6 · Signal integrity — [x] checked — unreported usage writes no GenAI count, never a zero.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: `scripts/test/test_gen_ai_telemetry.py`.
Mutation-checked: yes, by hand; six mutants, all killed.
Fixtures re-pinned: `contract/telemetry/v1/attributes.json`, `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the telemetry suites; the whole Python suite; ruff; mypy; the process gate against the commit.

Levers reviewed: `single-source-of-truth`, `failure-is-not-a-result`, `test-that-cannot-fail`.

KG query: kg:cfeaeba9448a
