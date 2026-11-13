# Review: pass3-root-causes

Each blocker was the third appearance of one defect, so each fix replaces the mechanism, not the spelling reported, and
each is tested through the entry point that failed: P3-R1 by evaluating `if:` conditions
(`scripts/test/test_gha_expression.py`, the parametrized bypass and keep-out lists in
`scripts/test/test_agent_workflow_injection.py`, three contract cases); P3-R3 through `process_gate.py ci` on a
`--no-verify` commit in both artifacts modes (`scripts/test/test_declaration_ratchet.py`); P3-R6 through real
`Authorization` headers in both account modes (`portal/test/signInPolicy.test.ts`); P3-R17 by the committed graph's
importer counts and a re-parse on a parser-version change (`scripts/test/test_knowledge_graph.py`).

## Pass 1 — findings: 4

Against `docs/review-levers.md`, by hand mutants (sixteen) and a read of the diff against GitHub's expression rules.

1. **Unknown under `!` and `&&` was untested.** Two mutants survived: `unknown && x` read as `x`, and `!unknown` read
   as false. Either turns `!(github.event.issue.pull_request && true)` into a guard that keeps outsiders out. Fixed:
   tests that unknown survives every operator under a negation, and resolves only when the other side decides.
2. **The proxy's sign-in wiring was untested.** `proxy.ts` imports Next, so no test loads it; a mutant counting every
   name survived. Fixed at the cause: the whole HTTP Basic decision moved to `basicSignIn()` in
   `portal/lib/signInPolicy.ts`, which the proxy only answers from; tests drive it with real headers.
3. **String coercion and hex literals were not GitHub's.** `str()` gave `'None'`, `'True'` and `'1.0'` where GitHub
   gives `''`, `'true'` and `'1'`, and `0x1F` never matched as hex. Neither made the guard check unsafe (the hex case
   was unparsed, so "may be true"). Fixed, with tests.
4. **The new `isBasicAccount` test did not run.** It was appended after the file's `process.exit`. Moved; every other
   portal test file was checked for tests after its exit: none.

## Pass 2 — findings: 0

- The mutants again, aimed where the logic now lives: unknown under `&&`, `||` and `!`; multi-user and single-user
  counting every name; single-user ignoring the password; a locked account granted. All killed. With pass 1's sixteen,
  twenty-three mutants, every one killed: the evaluator (eight), the untrusted roles, CI's route without the parent, the
  parser version ignored, the lockout counting unknown names, a locked account let in, the lock never reported,
  `isBasicAccount` true for any name.
- Siblings: no other portal code decodes Basic credentials or keeps state per caller-chosen name (the other maps are
  local to one call); only the runner reads `author_association`.
- `scripts/test` and `agentsmith/test`: 3,075 passed, 10 skipped; the eleven `test_compliance_runtime.py` cases that found the throwaway Postgres stopped were run again with it up: 86 passed. Portal `npm test`: exit 0. `tsc`: clean. ruff: clean. mypy
  (CI's scope): clean.

## Sign-off

Group 1 · DRY & shared code — [x] checked — imports resolved once, in the knowledge graph, and read by the trace graph; one HTTP Basic decision, in `basicSignIn()`.
Group 2 · Quality / safety — [x] checked — unknown is a third value, never read as true or false; an unparsed condition may be true.
Group 3 · Architecture / hygiene — [x] checked — the proxy answers; the library decides; `MAX_TRACKED`, the pruner and the spelling lists are gone.
Group 4 · Process — [x] checked — design first; CHANGELOG, manual and backlog updated; the profile labelled a preview with its known limits.
Group 5 · Intuitive UI — [x] checked — n/a beyond the sign-in answer, which is the same 401 for a locked account and a wrong password.
Group 6 · Signal integrity — [x] checked — `kg impact` names Python dependents; a guard counts only when it is false for every outsider.
Group 7 · Auth & session integrity — [x] checked — invented names are never counted; a locked account is refused, its lock audited once, and not revealed.

Tests added: `scripts/test/test_gha_expression.py` (new), `scripts/test/test_trace_graph.py` (new), bypass and keep-out lists in `scripts/test/test_agent_workflow_injection.py`, three contract cases, the CI-route test, knowledge-graph tests, header-level sign-in tests, an `isBasicAccount` test.
Mutation-checked: yes, by hand; twenty-three mutants, all killed (three after pass 1's fixes).
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` (every `KG query:` hash changes once); `.agent-rfc/fixtures/trace_graph.json` (new); `contract/security/v1/cases.json`.
Gates run: the suites above; `npm test`; `tsc`; ruff; mypy; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `guards-must-be-able-to-fail`, `consistent-auth-gates`, `retry-bounds`, `implemented-not-invoked`, `single-source-of-truth`, `test-that-cannot-fail`, `grep-for-siblings`

KG query: kg:61ba21945dd0
