# Review — gate-contract-ci (C1)

Design: `.agent-rfc/designs/gate-contract-ci.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 5

1. **Contract 2 widened a hole the gate already had.** An adopted tenant's config gates
   `.agenticframework/process-gates.json` but not `providers.json`, so a commit editing the
   declaration needed no design. Before C1 that changed only the editing hooks; under contract 2
   `"gate": "none"` switches CI's check off, so one unreviewed commit could turn the gates off
   entirely. Found by this slice's own sync test, which expected an edited declaration to be refused
   and saw it committed. The design was amended first; the gate now governs both files whatever a
   config lists (`ALWAYS_GOVERNED`), `adopt` lists the declaration in the config it writes, and
   contract 2 makes it binding on every provider with a conformance case. Mutation: the rule removed
   is caught.

2. **The new-branch conformance case could not tell the two readings apart.** It asked about
   `0000…..clean`, and nothing before `clean` fails — so a provider that judged the whole branch from
   its root passed it too. The fixture gained a clean commit *after* the undesigned one, and the
   case now asks about that head: "head alone" allows, "whole branch" denies.

3. **A sync test asserted only when its own premise held.** The foreign-provider test checked the
   workflow's setup step `if` the workflow was stale — and with the substitution broken it would not
   be stale, so the assertion would be skipped. It now asserts the workflow is stale and carries the
   declared step, unconditionally (`test-that-cannot-fail`).

4. **`docs/process-gates.md`'s "Finding the script" said every caller resolves the framework's
   script.** At contract 2 `ci` goes only to the declared provider. Rewritten with the gates
   workflow named as a caller.

5. **Making the record sender importable reordered its endings.** `main` read the file before the
   URL checks, so an insecure portal address with a missing record would have warned instead of
   failing. `send` now takes an optional document and checks configuration first, as before; the
   22 existing sender tests pass unchanged.

## Pass 2 — findings: 1

1. **Governing the config always silenced the check that a config lists itself.** `problems()`
   refused a config that does not gate `process-gates.json` by asking `is_gated(CONFIG)` — which
   `ALWAYS_GOVERNED` now answers yes for every config, so the refusal could never fire. The full
   suite caught it (`test_a_broken_config_is_named`, `test_a_broken_config_blocks_every_commit`).
   The check still matters: an older copy of the gate — a vendored one, a contract-1 provider —
   does not have `ALWAYS_GOVERNED`, and a config should say what the gate does. `is_gated` is now
   `ALWAYS_GOVERNED or lists(path)`, and the check asks `lists(CONFIG)`. It deliberately does not ask
   the config to list the declaration: every config adopted before today would fail it, and this
   check blocks every commit.

## Pass 3 — findings: 0

Re-read `is_gated`/`lists`, the launcher's `declared_contract` and `ci_by_contract`, `cmd_ci_decision`,
the setup action, the template, `workflow_setup`, and the docs against the levers.

- `declared_contract`: the gate entry's value wins; the top-level value is read after cutting the
  innermost objects, so a port's `contract` is never taken for the declaration's; no declaration is 1.
- No decision in any form — exit 3, 126, 127, empty, not JSON — fails `ci` and names which; a `deny`
  carries the provider's text; the refs are checked before they are put into JSON.
- The provider's record step keeps the old step's endings: not configured or unreachable is a note,
  refused is a failure, and the token appears in neither the decision nor the report.
- Contract 1 is untouched: its directory is byte-for-byte, its five cases still pass, and a
  contract-1 declaration still runs `ci` through the framework's own script.
- What is still coupled is named, not hidden: the sync workflow (C9), the local commit and push
  gates (C2), the record's wire contract (C3).

## Pass 4 — findings: 1

1. **The v2 protocol was an undeclared document.** The CI gate's artifact rule (`enforce` here)
   refused the commit: `contract/gate/v2/protocol.md` is neither an artifact nor declared reference
   documentation. v1's protocol is declared in `.agenticframework/process-gates.json`
   (`extends.artifacts.reference`); v2's now is beside it. The config is gated — and, since this
   slice, always governed — so the design's scope was widened first. Found by running the CI gate
   locally before pushing, which is why that step is in the sign-off.

## Pass 5 — findings: 0

Re-ran `python3 scripts/process_gate.py ci --base origin/main --head HEAD` over the amended commit
and re-read the config change: one entry added to the reference list, nothing else in the file moved.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one verdict (`ci_verdict`) behind both `ci` and the contract-2 answer; the record sender imported, not run by path; v2's schemas generated from models that extend v1's; v2 carries v1's cases and fixture, pinned word for word.
Group 2 · Quality / safety — [x] checked — 17 tests in `test_gate_contract_v2.py` plus the updated adopt, sync and contract tests; 7 mutations in the new `gate_contract_v2` suite and 3 in `framework_sync`, all caught; conformance 10/10 on v2 and 5/5 on v1.
Group 3 · Architecture / hygiene — [x] checked — the tenant's workflow names no framework path; the launcher stays interpreter-free until it must read a decision; the setup action installs only what the gate needs, proved in a fresh virtualenv.
Group 4 · Process — [x] checked — the design amended before the declaration rule and the sync-workflow exclusion were built; the backlog row updated and an archive entry written; the release dependency stated in CHANGELOG.
Group 5 · Intuitive UI — [x] checked — CI prints the provider's report and annotations, and a failure without a verdict says which kind it was.
Group 6 · Signal integrity — [x] checked — "denied", "no decision" and "record refused" read differently; a check that could not run never reads as passed.
Group 7 · Auth & session integrity — [x] checked — the portal token is read by name, never enters the decision or report (asserted); refs are validated before they reach JSON; the declaration that switches CI on or off is governed in every tenant.

Tests added: `scripts/test/test_gate_contract_v2.py` (17); in `scripts/test/test_framework_sync.py` — `test_an_untouched_contract_1_declaration_moves_to_contract_2_with_its_workflow`, `test_a_declaration_naming_another_provider_is_theirs_and_its_setup_is_what_ci_runs`; updated `test_tenant_adopt.py`, `test_gate_contract.py`.
Mutation-checked: `python3 scripts/mutation_check.py gate_contract_v2` — 7 caught (run twice, after the pass-2 fix); the 3 new `framework_sync` mutations through `mutation_check.run_suite` — caught.
Fixtures re-pinned: `contract/gate/v2/` written new (v1 untouched); `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
Gates run: full `pytest` (2083 passed before the pass-2 fix, its 3 failures being that finding; then `test_process_gate.py` and `test_gate_contract_v2.py` in full, 127 passed); `ruff check .` (0.15.20); `mypy` (1.14.1); `agentsmith conformance --contract 2` and `--contract 1`; the launcher run end to end through an action-style `agentsmith` in a clean virtualenv; `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `gate-integrity`, `declared-vs-enforced`, `test-the-contract`, `test-that-cannot-fail`, `implemented-not-invoked`, `two-owners-two-cadences`, `failure-mode-visibility`, `pin-unremovable-duplicates`, `docs-match-behaviour`.

KG query: kg:f882db829bb3
