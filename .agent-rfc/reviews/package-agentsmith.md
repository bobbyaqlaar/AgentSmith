# Review — the package imports as `agentsmith`

Design: `.agent-rfc/designs/package-agentsmith.md`. Owner decision, 2026-11-03: rename it before the launch.

**Built evidence:**
- `runtime/` is `agentsmith/`, 119 files moved by `git mv`, with history kept. About 280 tracked files follow.
- `scripts/test/test_package_name.py` holds the name over every tracked code file, and what keeps the old word.
- The full suite ran on the rename; the failures below were fixed and their suites re-run.

## Pass 1 — findings: 5

1. `when-the-fallback-fails` — **A tenant's old copy would have stopped being detected.** `framework_copies` asks whether the same
   path exists in the framework, and `runtime/llm_gateway.py` no longer does, so `verify_system --governed` would have gone quiet on
   exactly the tenants it exists for. Found by `test_vendoring_retired.py`, whose fixture the rename had also rewritten.
   **Fix:** a `runtime/` path is looked up under `agentsmith/`, the fixture holds the old name, and a curated mutation proves the test.
2. `declared-vs-enforced` — **A required check would have been renamed.** The path substitution turned the job name
   `Python scripts/runtime/examples` into a new name, and `main` requires that context by name, so every PR would have waited on a check
   that never reports. **Fix:** the label stays; changing it is a branch-protection decision for the owner.
3. `docs-match-behaviour` — **History was rewritten.** The substitution made "the installer could vendor `scripts/` and `agentsmith/`" true of
   no release, in the README, `docs/process-gates.md` and comments. **Fix:** the old name where a sentence describes the past.
4. `environment-parity` — **A stale `~/.agent-framework/runtime` would have stayed importable** after upgrading a machine, since the
   installer copies over and never removes. **Fix:** `install-ai-stack.sh` removes it.
5. `test-the-contract` — **`portal/test/tracing.test.ts` built the path from segments,** which the patterns missed. **Fix:** corrected, and a
   sweep for quoted `runtime` followed by a separator found no other in live code.

## Pass 2 — findings: 0

- **What keeps the word was read, not assumed:** every remaining use outside history is English, the wire scope, the distribution
  name, the required job's label or detection of a pre-3.0.0 copy.
- **A tenant's own `agentsmith/` directory cannot shadow the provider:** the launchers run `python3 -P`, and the decoy test in
  `test_telemetry_contract.py` holds it under the new name.
- **KYC Sentinel keeps working until it moves:** it pins `@v3.0.0`, and nothing here changes a released tag.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one name; no shim keeps a second.
Group 2 · Quality / safety — [x] checked — `scripts/test/test_package_name.py`; `framework_copies` under a curated mutation.
Group 3 · Architecture / hygiene — [x] checked — `git mv`, so history follows; no dependency added.
Group 4 · Process — [x] checked — design before the move; CHANGELOG Unreleased; DESIGN's tree; graph regenerated.
Group 5 · Intuitive UI — [x] n/a — no screen changes; the portal's edits are comments and one test path.
Group 6 · Signal integrity — [x] checked — a stale import fails with `ModuleNotFoundError`, and old copies are still reported.
Group 7 · Auth & session integrity — [x] n/a — no credential or session path changes.

Tests added: `scripts/test/test_package_name.py`.
Mutation-checked: `scripts/mutation_check.py` gains "the governed check stops finding a pre-3.0.0 copy of the package"; held by Self-Test's mutation shards.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: full suite on the rename (2475 passed), then the failed suites re-run after their fixes, and the release contract tests on the commit; ruff; mypy; `agentsmith gates run` for py_compile, repo-tree, Redaction, Commit guardrails, check-kg, On-prem, evidence pack, bash -n and the release install; artifacts; portal `tsc`, `npm test`, `npm run build`. Curated mutations locally only for the suite holding the new one: this change triggers every suite, and Self-Test's shards run them all.

Levers reviewed: `declared-vs-enforced`, `docs-match-behaviour`, `two-owners-two-cadences`, `environment-parity`, `when-the-fallback-fails`, `test-the-contract`.

KG query: kg:e2fdf9774b45
