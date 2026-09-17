# Review — governance enforcement, G6a (pillar answers that can be checked)

Design: `.agent-rfc/designs/governance-enforcement.md` § G6, with the amendment written before
this code: G6a is the policy, evidence tokens and the two checks the owner named; G6b is the rest.

**Built evidence (2026-09-17):**

- **Failing tests first.** `test_gate_pillars.py` (32) was written before `gate_pillars.py`; the
  file did not import on the first run, and the two registry/config pins failed until P3 and P7
  were marked `mechanical` and AgentSmith declared a policy.
- **Dogfooded here, at `enforce`.** AgentSmith's own design now names something resolvable in
  every `applies` answer — and the rule caught P14 naming `scripts/test/fixtures`, a directory
  that does not exist, and a pillar answer claiming IDE payload fixtures that arrive with G2.
  The seed is 18 allowlist entries over 16 files, listed by `process_gate.py pillars`.
- **The registry decides which checks exist, the repo decides whether it is held to them.** The
  policy is in `process-gates.json` because that file is read at the commit being checked, and
  `@framework/templates/governance.json` is read beside the running script: a requirement added
  to the registry would judge every commit CI re-checks, which is the defect G1 shipped with.
- **Mutation checks (each reverted):** sixteen — the evidence rule not running, an unresolved
  token accepted, markdown searched for content (self-certifying designs), P7 not flagging, every
  entrypoint counted as traced, test files treated as first-party, the allowlist ignored, an entry
  allowing every check on its path, the mode weakened, a new entry without approval, an approval
  id nobody recorded, the seed treated as a change, `report` blocking on code, `report` blocking
  on a pillar answer, the registry's `mechanical` mark ignored, and `enforce` reporting instead of
  failing. Twelve caught on the first run; the four survivors are findings 1, 2 and 5 below plus
  two mutations of mine that were equivalent (a redundant branch and a fallback that still fired),
  re-chosen so they bite. All sixteen caught after the fixes.

## Pass 1 — findings: 5

- `single-source-of-truth`, `guards-must-be-able-to-fail` — **finding:** the seed exemption was
  decided twice. `check_change` tested `previous.pillars_declared` before calling
  `transition_problems`, which tested `old is None` again — so the function's own guard was dead
  code and deleting it changed nothing any test saw. The caller now resolves the inherited policy
  and the function owns the rule.
- `test-that-cannot-fail` — **finding:** `test_a_test_file_is_not_first_party_code` committed the
  test file in a separate `--no-verify` commit to satisfy the design's scope, so the commit under
  test never touched it: the exclusion it claims to prove was never exercised. It now commits the
  file as part of the change, under a design whose scope covers `scripts/test/**`.
- `ambiguous-signals` — **finding:** `pillars` printed "every tracked file passes the mechanical
  checks" when the registry marked no pillar `mechanical` — that is nothing ran, not everything
  passed. It now says which, and names the checks that did run when they do.
- `failure-mode-visibility` — **finding:** an invalid mode reported the rule but not the value
  ("mode: Input should be 'off', 'report' or 'enforce'"), leaving the reader to find their own
  typo. The message now ends `(got 'enforced')`.
- `check-that-fires-on-everything` — **finding:** nothing covered the import-only half of
  `P7-pydantic` (`import dataclasses` with no decorated class), which is why a mutation of the
  class check survived: the import fallback silently covered for it. Tested now.

## Pass 2 — findings: 0

Every lever over the final diff: the policy model and its ratchet, the two checks, the resolver,
the three call sites (commit-msg, sweep, CI), the command, and the docs. Considered and declined:
the evidence token's glob is `fnmatch`, not this repo's GitHub-style `glob_match`, because
`gate_pillars` cannot import `process_gate` (the dependency runs the other way) and the only
question asked of it is "does anything match" — recorded here rather than left implicit.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_pillars.py (32); test_process_gate.py and
                          test_gate_records_single.py carry evidence in their designs,
                          and the fixture repo vendors scripts/gate_pillars.py
Mutation-checked:          yes — sixteen, each reverted; four survivors became findings 1, 2
                          and 5 and two re-chosen mutations
Fixtures re-pinned:        yes — templates/governance.json regenerated (P3 and P7 marked
                          mechanical) and .agent-rfc/fixtures/knowledge_graph.json
Gates run locally:         ruff, both suites, mutation_check.py, SPECS tree drift, --check-kg,
                          the registry drift check, and `process_gate.py pillars` and
                          `artifacts` against this checkout
Declared gaps:             (1) `P7-pydantic` cannot tell an internal value object from a model
                              built out of unvalidated input, so it flags both; AgentSmith's 16
                              seeded files are the evidence for narrowing it in G6b;
                          (2) `P3-tracing` finds only entrypoints a decorator declares, and
                              reads a handler that delegates to a tracing helper as untraced;
                          (3) evidence proves a token resolves, not that it is the right token;
                          (4) evidence is checked at commit and in CI, not at pre-edit or stop —
                              a design that names the file it is about, before that file exists,
                              is doing its job;
                          (5) a parent commit whose config cannot be parsed reads as no policy,
                              so the ratchet sees a seed; that commit is itself refused, and the
                              sweep catches it if it was made with --no-verify.
```
