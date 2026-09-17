# Review — governance enforcement, G6b (the rest of the mechanical checks)

Design: `.agent-rfc/designs/governance-enforcement.md` § G6, with the amendment written before
this code: G6b is the remaining checks and the narrowing of `P7-pydantic`; G6c is the local
runner.

**Built evidence (2026-09-17):**

- **Failing tests first.** Eighteen tests were added to `test_gate_pillars.py` before the checks;
  eight failed on the first run and the rest passed for the wrong reason until the registry
  marked P2, P10 and P12 `mechanical`.
- **Measured before designing.** A throwaway probe ran each candidate rule over this repo first,
  because a check that flags a hundred files is a check nobody turns on. The counts decided the
  shape of two rules: `P7-use-client` is scoped to Next.js projects (it flagged two Vite scaffolds,
  where the directive would be a mistake), and `P10-gateway` matches full dotted module names
  (matching the first component flagged `google.auth`, which is not a provider SDK).
- **Fixed rather than exempted — ten things.** A new check cannot be allowlisted into existence:
  the ratchet cannot tell a new rule from a repo excusing itself, so turning these on meant fixing
  what they found. Two scaffold handlers were `def` where a tenant copying them would block the
  event loop. Five `any`s in the portal's data layer became named types: `PhoenixPage<T>` and
  `PhoenixAnnotation` at the Phoenix REST boundary, `TenantRow` for the columns
  `TENANT_COLUMNS` selects, and `TracedPool.query` now carries `Pool["query"]` itself with an
  `unknown[]` body — `npx tsc --noEmit` and all 11 portal suites are green. Seven redaction
  fixtures carry `# not-a-secret:`.
- **The narrowing shrank the allowlist from 18 entries to 2** — a removal needs no approval, which
  is the ratchet working in the direction it is meant to move.
- **Mutation checks (each reverted):** sixteen new ones, one per blocking path — the narrowed P7
  in three directions (unpacked construction, request body, and every dataclass flagged again),
  a sync handler passing, `any` unseen, comments read as code, `use client` unasked and asked
  everywhere, provider imports unseen, the gateway flagged, secrets unseen, the marker ignored,
  test files skipped, a package unseen, the design's answer ignored, and a removal counted as an
  addition. All sixteen caught. G6a's fifteen were re-run against the refactored runner and all
  still bite.

## Pass 1 — findings: 3

- `declared-vs-enforced` — **finding:** `exemption_count` was written and never called. The design
  says the `not-a-secret:` markers are counted in the `pillars` output so their number is visible;
  the function existed, the output did not print it. Wired, and both kinds of exemption are now on
  the verdict line: allowlist entries and marked lines.
- `aggregates-name-their-scope` — **finding:** the first version of that count counted *markers*,
  so this rule's own documentation counted as exemptions taken — it read 10 where 7 lines are
  actually exempt, and a `:!*gate_pillars.py` pathspec silently swallowed the test file as well.
  It now counts a line only when it carries the marker AND would otherwise be flagged, which is
  what an exemption is, and a test pins that the documentation of the marker is not one.
- `test-the-contract` — **finding:** `_code_lines` skipped lines starting with `#` as comments.
  It only ever reads TypeScript, where `#` starts a private class field: `#count = 0;` would have
  been skipped by a check meant to read it.

## Pass 2 — findings: 0

Every lever over the final diff: the `Source`/`Check` shape, the eight checks, the runner's
filtering, the narrowing, the portal fixes, the scaffolds, and the docs. Considered and declined:
`hooks/pre-commit`'s Guardrail 3 (a `cost_router` import inside `runtime/`) overlaps `P10-gateway`
in intent, but that hook family runs only where `core.hooksPath` is NOT set to `.githooks`, so
removing it would drop coverage for repos that have not adopted the gates. The overlap is
recorded here rather than resolved by deleting one of them.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_pillars.py (48 total, 18 new); two claims the narrowing
                          retired were deleted rather than left asserting a rule that
                          no longer exists
Mutation-checked:          yes — sixteen new, each reverted, all caught; G6a's fifteen re-run
                          against the refactored runner
Fixtures re-pinned:        yes — templates/governance.json (P2, P10, P12 marked mechanical)
                          and .agent-rfc/fixtures/knowledge_graph.json
Gates run locally:         ruff, both Python suites, mutation_check.py, npx tsc --noEmit and
                          npm test in portal/, --check-kg, --check-redaction, SPECS drift,
                          and `process_gate.py pillars` and `artifacts`
Declared gaps:             (1) `runtime/llm_gateway.py` rebuilds `CompletionResult(**cached)`
                              from the idempotency store — a real boundary the narrowed rule
                              is right to flag. It is tenant-facing (a Pydantic model makes
                              construction keyword-only), so it is the owner's call: fix or
                              approve. `pillars` reports it and the next change to that file
                              is refused. Logged in the backlog;
                          (2) `P7-ts-any` reads lines, not a parse — text inside a string
                              counts;
                          (3) `P12-secrets` matches shapes, not issuers;
                          (4) `P7-pydantic` cannot see a dataclass filled field by field from
                              a parsed payload;
                          (5) the four `hooks/pre-commit` guardrails do not run in a repo that
                              has armed `.githooks` — pre-existing, not introduced here, and
                              not this slice's to fix.
```
