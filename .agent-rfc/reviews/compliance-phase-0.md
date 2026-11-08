# Review — compliance-phase-0

Scope: the registry, the OWASP and status rows in the documents, the UAE page, the new test, the local demo script, and the
umbrella plan. Worked against `docs/review-levers.md`; files from `gate kg impact --staged`.

## Pass 1 — findings: 5

1. `grep-for-siblings` — **The demo script's citation table still showed 2023 tags and `Partial→Met`.** Six rows, read aloud in
   Ch 6. **Fix:** tags and statuses match the registry.
2. `docs-match-behaviour` — **The umbrella plan said audit events are dropped when the portal is down.** `agentsmith/machine/policy.py`
   falls back to `local-audit-fallback.log`. Only run status, in `agentsmith/ops_contract.py`, is lost. **Fix:** the plan states all three paths.
3. `docs-match-behaviour` — **The plan said `SEC-AUDIT-002` needs to start running in CI.** `self-test.yml` already verifies the triggers;
   only the harness row is unbound. **Fix:** PH3 reworded.
4. `declared-vs-enforced` — **An evidence pack printed tags with no edition,** so an auditor could not tell which list `LLM06` meant.
   **Fix:** `scripts/security/report.py` titles it "OWASP LLM Top 10 (2025)", asserted in `test_security_evidence_pack.py`.
5. `docs-match-behaviour` — **The gap roadmap in the framework map omitted the two new gaps.** **Fix:** both listed.

## Pass 2 — findings: 2

1. `grep-for-siblings` — **README's feature table still said "PDPL pre-call scrub"** after the mandate row was corrected. **Fix:** "pre-call PII scrub".
2. `docs-match-behaviour` — **The CHANGELOG did not mention the report's new title,** which Pass 1 added. **Fix:** stated.

## Pass 3 — findings: 1

1. `no-redundant-artifacts` — **The public backlog stated the owner's certification goal,** which nobody asked to publish and which adds nothing to
   the item. **Fix:** removed; the design records it as a later independent assessment.

## Pass 4 — findings: 0

- **The new test bites.** Five hand mutants, each killed: a registry tag back to its 2023 number, a table row renamed, a control dropped from the
  OWASP table, a unified-table tag drifted, a unified row removed.
- **A tenant's verdict cannot move.** `scripts/security_port.py` answers `not_applicable` for a provider-subject row in a tenant before it reads
  status; `test_security_contract.py` passes with both rows in `PROVIDER_ROWS`.
- **The docstring is true.** No `hitl_approved` sender exists in `portal/` or in the replay webhook path.
- **No stale claim is left.** `Partial→Met`, "2025-oriented", "Stay compliant" and "mandatory HITL" remain only in design text describing the problem, and in
  `docs/testbed-tenant-spec.md`, where "mandatory HITL" states what a test tenant must exercise.
- **The strict harness result is unchanged in kind:** `pass=22 skip=1 warn=3` with `MODERATION_HOOK=optional`, as CI sets it; the three warnings are the three declared gaps.
- **No private name:** `test_private_names.py` passes.

## Sign-off

Group 1 · DRY & shared code — [x] checked — the registry is the source and `test_the_owasp_table_matches_the_registry` and `test_the_unified_table_matches_the_registry` hold the map to it.
Group 2 · Quality / safety — [x] checked — relabel by a stated crosswalk, with three named exceptions in the design.
Group 3 · Architecture / hygiene — [x] n/a — no structural change or dependency.
Group 4 · Process — [x] checked — design first; CHANGELOG and backlog updated; no release in this slice.
Group 5 · Intuitive UI — [x] n/a — no screen changes.
Group 6 · Signal integrity — [x] checked — two controls split so each name says what its runner proves; new rows are declared gaps, not passes.
Group 7 · Auth & session integrity — [x] n/a — documents state portal gaps; no auth code changed.

Tests added: `test_owasp_tags_use_the_2025_numbering`, `test_the_owasp_table_matches_the_registry`, `test_the_unified_table_matches_the_registry`.
Mutation-checked: yes, by hand; five mutants of the registry and the map, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: ruff; mypy (3.11 venv, locked); py_compile; the repo-tree check; check-hooks; `process_gate.py artifacts`; strict security harness; `scripts/test/test_security_*.py`, `test_sovereign_residency.py`, `test_hitl_gate.py`, `test_private_names.py`; then the whole of `scripts/test` and `agentsmith/test`: 2507 passed, 10 skipped. check-kg on the staged tree. Portal unchanged, so its suites were not run.

Levers reviewed: `declared-vs-enforced`, `single-source-of-truth`, `grep-for-siblings`, `test-that-cannot-fail`, `docs-match-behaviour`, `no-redundant-artifacts`.

KG query: kg:d38f96b079b0
