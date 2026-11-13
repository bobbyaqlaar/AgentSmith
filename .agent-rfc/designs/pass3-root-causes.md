---
status: active
scope:
  - scripts/map_codebase.py
  - scripts/test/test_knowledge_graph.py
  - scripts/trace_graph.py
  - scripts/test/test_trace_graph.py
  - scripts/security/gha_expression.py
  - scripts/security/runners/agent_workflow.py
  - scripts/test/test_agent_workflow_injection.py
  - scripts/test/test_gha_expression.py
  - contract/security/v1/cases.json
  - scripts/test/test_security_contract.py
  - scripts/process_gate.py
  - scripts/test/test_declaration_ratchet.py
  - portal/lib/signInPolicy.ts
  - portal/lib/authz.ts
  - portal/proxy.ts
  - portal/test/signInPolicy.test.ts
  - portal/test/authz.test.ts
  - agentsmith/cli.py
  - CHANGELOG.md
  - docs/PRODUCT_BACKLOG.md
  - docs/UserManual.md
  - .agent-rfc/fixtures/trace_graph.json
---
# The causes behind the third pass's blockers, and a code graph that can be trusted

From the 4.1.0 review's third pass (`.git/agentsmith/review-4.1.0-pass3.md`, local to the owner's checkout), at the
owner's request (2026-11-14): fix the knowledge graph, bring the reviewer's traceability graph into the repository,
and fix the three release blockers at their cause, not the instance reported, "given that the same defects have
surfaced the third time".

## Problem

Each blocker is the third appearance of one defect, patched twice at the spelling reported:

| Finding | Earlier patches | The cause |
|---|---|---|
| P3-R1: SEC-CIAGENT-001 accepts `(… == 'OWNER' && x) == false` | R9 refused `\|\|` and `!`; P2-R5 matched "a term that is exactly a trusted test" | the check reads a condition's spelling, so every rewrite is a new bypass |
| P3-R3: CI does not refuse a commit that weakens the declaration | P2-R12 put the rule in `check_change` and tested `check_change` | CI's `check_commits` reaches `check_change` by another route: it skips some ungated commits and never passes the parent |
| P3-R6: a flood of invented names makes every user get 429 | R17 evicted unlocked entries; P2-R18 refused names the full map could not hold | the lockout keeps state for names the attacker chooses, so any bound is a flood target |

And the reviews kept missing the file one step to the side because the code graph `kg impact` reads is wrong
(P3-R17): `scripts/map_codebase.py` keeps the first component of a Python import (`agentsmith`), so 0 edges reach
`agentsmith/compliance.py` (22 importers) or `agentsmith/llm_gateway.py` (37); and it drops every TypeScript import
through the portal's `@/` alias.

## Approach

- **Knowledge graph (P3-R17).** Python imports keep their full module path; `from a.b import c` yields `a.b.c`
  and `a.b`; relative imports resolve from the importing file's package; a bare module resolves against the repository
  root, the importing file's own directory, and `scripts/` (where the scripts put themselves on `sys.path`).
  TypeScript resolves the `paths` aliases of the nearest `tsconfig.json`, and reads `export … from` and `import()`.
  The graph is rebuilt; every `KG query:` changes once, and `kg impact` names Python dependents for the first time.
- **Traceability graph.** The reviewer's builder becomes `scripts/trace_graph.py`, reading imports from the knowledge
  graph instead of resolving them a second time, building at `HEAD`, and writing
  `.agent-rfc/fixtures/trace_graph.json` with the commit it was built from. Every link carries `observed`,
  `declared`, `derived` or `inferred`. It is the report-only phase 0 the review recommended for
  `.agent-rfc/designs/traceability-graph.md`; it decides nothing and no gate reads it.
- **P3-R1: evaluate the condition, not its spelling.** `scripts/security/gha_expression.py` parses GitHub's
  expression grammar (literals, contexts with `.` and `[…]`, calls, `!`, comparisons, `&&`, `||`, brackets) and
  evaluates it in three values (true, false, unknown) with GitHub's coercions. A guard restricts a field when, for every
  author association that is not OWNER, MEMBER or COLLABORATOR (and for one value GitHub has not defined), the job's
  and the step's conditions together are definitely false. Any other context reads as unknown, so a guard that relies
  on it does not count. No spelling list is left to extend.
- **P3-R3: one route.** `check_commits` builds the parent's reader for every commit and hands every commit to
  `check_change` with it, gated or not, so CI judges exactly what the hook judges. A test runs the scenario through
  `process_gate.py ci`, in both artifacts modes.
- **P3-R6: only real accounts are counted.** A failed sign-in counts only for a name the portal has an account for
  (`OPS_PORTAL_USER` or `OPS_PORTAL_USERS`). The map is bounded by the number of accounts, so `MAX_TRACKED`, the pruner
  and the "refuse what cannot be counted" rule go. A locked account is answered exactly as a wrong password is (the
  same 401), so the lockout cannot be used to learn which names exist, which the portal already guards against.
  The whole HTTP Basic decision moves to `basicSignIn()` in `portal/lib/signInPolicy.ts`, which a test can drive
  with real headers; `portal/proxy.ts` imports Next, so no test can load it, and it only answers from the decision.
- **The profile ships as a preview.** The CHANGELOG, the manual and the backlog say so, with the open minors listed
  as known limits.

## Pillars

- P1 applies — the third review's P3-R1, P3-R3, P3-R6 and P3-R17, and the owner's instruction, are the requirement; `.agent-rfc/designs/pass3-root-causes.md` is the plan.
- P2 applies — `scripts/security/gha_expression.py` and `scripts/trace_graph.py` are new; `scripts/map_codebase.py`, `scripts/process_gate.py` and `portal/lib/signInPolicy.ts` change in place.
- P3 applies — `scripts/trace_graph.py` writes `.agent-rfc/fixtures/trace_graph.json`, linking requirements, designs, commits, files and tests, each link typed.
- P4 applies — `scripts/test/test_gha_expression.py`, `scripts/test/test_knowledge_graph.py`, `scripts/test/test_trace_graph.py`, `scripts/test/test_declaration_ratchet.py` (through `process_gate.py ci`) and `portal/test/signInPolicy.test.ts`; hand mutants after.
- P7 applies — `scripts/map_codebase.py` reads Python and TypeScript imports as each language resolves them.
- P8 n/a — no telemetry changes.
- P9 n/a — no orchestration.
- P10 n/a — no routing.
- P11 applies — `scripts/security/runners/agent_workflow.py`: a guard counts only if it keeps every outsider's event text away from the agent, whatever its spelling.
- P12 applies — `portal/proxy.ts`: a locked account and a wrong password are answered alike, so no name is revealed.
- P13 applies — `scripts/process_gate.py`: the commit hook and CI judge a commit by one route.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is rebuilt with the corrected edges; `.agent-rfc/fixtures/trace_graph.json` records the commit it was built from.
- P15 applies — `scripts/security/gha_expression.py`: "unknown" is a third value, never read as true or false.
- P16 applies — `CHANGELOG.md` says what newly fails (guards that only looked restrictive) and that the profile is a preview.

## Deviations

none

## Dependencies

none

## Levers

- `guards-must-be-able-to-fail` — the guard check is a semantic evaluation that fails for any spelling that lets an outsider through.
- `consistent-auth-gates` — the hook and CI take one route to one verdict.
- `retry-bounds` — the lockout's state is bounded by real accounts, so no flood fills it.
- `implemented-not-invoked` — CI now calls what the hook calls.
- `single-source-of-truth` — imports are resolved once, in the knowledge graph, and the trace graph reads them.
- `test-that-cannot-fail` — hand mutants, and tests through the entry points CI runs.
