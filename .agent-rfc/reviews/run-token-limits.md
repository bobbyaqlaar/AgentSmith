# Review: run-token-limits

The run half of the token goal, after the owner's instruction of 2026-11-10 to do the token items first. This record covers the caps per role and the limits per run. The trajectory `max_tokens` rule and the portal's tokens column built on #112, and are recorded as passes 3 and 4.

## Pass 1 — findings: 2

Against `docs/review-levers.md`.

1. **Three hand-built test gateways had no budget backend.** The real constructor always opens one, and the run limits read it, so 11 existing tests failed with `AttributeError`. Fixed in the shared fixture and the two files that build their own, not by making the gateway tolerate a missing backend.
2. **The streaming path cannot settle a run budget,** because a stream reports no usage. Decided, not fixed: the reservation stands as the charge, the same rule the money cap applies to streams, and the design says so.

## Pass 2 — findings: 0

- `agentsmith/test/test_token_limits.py`: an undeclared limit changes nothing; the role caps the answer; an oversized prompt is refused before it is sent; a run stops at its budget, settles to the real count, and keeps runs apart; a failed call is released; unreported usage keeps the reservation; the tool-call limit per run; the environment variable, and a malformed one.
- Nine hand mutants, all caught, including the gateway skipping the settle or the release.
- The 22 gateway, streaming, guard, moderation, tool and compliance suites: 250 passed; ruff and mypy clean.

## Pass 3 — findings: 1

The trajectory `max_tokens` rule and the portal's tokens column, once #112 had merged.

1. **A span that carries both name sets would have been counted twice,** because the library writes `gen_ai.usage.*` beside `llm.usage.*`. Fixed: one set per span, GenAI first; a test pins it.

## Pass 4 — findings: 0

- `scripts/test/test_trajectory_evals.py`: a run over its budget fails, read from mixed-name model spans; a span with both sets counts once; recorded `tokens` count for a named trajectory; a budget with no tokens recorded is `not_gradable`. Evals contract and trajectory suites: 119 passed.
- Five hand mutants, all caught.
- `portal/test/opsIngestDb.test.ts`: a run's tokens are listed, and one that reported none returns null, shown as "not reported". The whole file passes against a throwaway Postgres; `tsc` and the portal unit tests pass.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one module for the arithmetic; the gateway and registry call it; the run counters reuse the spend cap's atomic backend.
Group 2 · Quality / safety — [x] checked — every limit refuses before anything is sent, with an error that names the setting.
Group 3 · Architecture / hygiene — [x] checked — additive; `ToolRegistry.invoke` gains an optional keyword.
Group 4 · Process — [x] checked — design first; manual, environment-variable table and CHANGELOG updated.
Group 5 · Intuitive UI — [x] n/a — no screen in this part.
Group 6 · Signal integrity — [x] checked — unreported usage is charged as the estimate, never as zero.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: `agentsmith/test/test_token_limits.py`.
Mutation-checked: yes, by hand; nine mutants, all killed.
Fixtures re-pinned: `agentsmith/test/_gateway_fixtures.py` and two hand-built test gateways gain a budget backend; `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; ruff; mypy; the documentation checks; the process gate against the commit.

Levers reviewed: `failure-is-not-a-result`, `test-that-cannot-fail`, `declared-vs-enforced`.

Scope at the first sign-off: kg:fc8af98fa70e

## Pass 5 — findings: 7

The 4.1.0 release review, read against this record's own sign-off. Each was verified in the code before it was fixed; each fix has a test that failed on `origin/main`.

1. **R1** — a call the money cap refused kept its run reservation, as did the `text is None` exit, and the stream path discarded `reserve_run`'s return so nothing could release it. The sign-off's "a failed call is released" held for one exit of four. Fixed: the run is reserved after the money cap; every exit that sends nothing releases both.
2. **R20** — a stream that fell back to `complete()` dropped `data_class` and `user_id` and kept its own reservation while `complete()` reserved again. A sibling the review did not name: the "provider cannot stream" fallback dropped both arguments too. Both fixed.
3. **R5** — a fallback tier was sent the first role's sizes. Fixed per attempt.
4. **R4** — `100k` read as no limit and `true` as 1. Fixed: `LimitUnreadableError`.
5. **R6** — run counters lived in the money table, with the month in their key, for ever. Fixed: their own store per backend, pruned.
6. **R2** — a trace with no usage read as 0 tokens and passed `max_tokens`. The sign-off's "unreported usage … never as zero" held in the gateway and not in the judge. Fixed.
7. **R11** — `[]` divided by zero. Fixed in `dataset`, for every suite.

## Pass 6 — findings: 2

Hand mutants against the fixes above (scratch `mutate.py`: apply one edit, run the file's tests, restore).

1. **The `text is None` release survived its mutant**: the test emptied `gw.models`, so the call failed at the role lookup before reserving. The test now points the degrade chain at a role that is not configured.
2. **Releasing the money when the run refuses survived**: no test had the money cap accept and the run refuse. Added `test_a_call_the_run_budget_refuses_spends_no_money`.

## Pass 7 — findings: 0

- `agentsmith/test/test_token_limits.py`: 21 passed; `scripts/test/test_trajectory_evals.py` with the evals contract: 124 passed; all of `agentsmith/test`: 869 passed, 17 skipped.
- Twelve hand mutants (gateway 6, `token_limits` 3, `evals_port` 3), all killed, including the two above after their tests were fixed.
- Read again for the review's levers: every exit between reserve and send releases (`early-exit-keeps-the-record`); the unreadable limit raises at the call and at a fallback, as itself (`guards-must-be-able-to-fail`); an unmeasured span is absent, not 0 (`ambiguous-signals`); the Postgres counter statement is one atomic upsert guarded by the limit, like the money cap's (`use-existing-apis`). Not run against Redis or Postgres: the two stores are read, not exercised.

## Sign-off (after the 4.1.0 review)

Group 1 · DRY & shared code — [x] checked — one `release()` per stream call; one counter interface over three stores, chosen from the budget backend.
Group 2 · Quality / safety — [x] checked — a refused or unsent call costs the run nothing; an unreadable limit fails loudly.
Group 3 · Architecture / hygiene — [x] checked — the money ledger holds money only; a new table is created on first use.
Group 4 · Process — [x] checked — design addendum first; manual and CHANGELOG updated.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — a trace that reports no usage is `not_gradable`; an empty case file is `not_gradable`.
Group 7 · Auth & session integrity — [x] n/a — no auth or session code.

Tests added: seven in `agentsmith/test/test_token_limits.py`, five cases in `scripts/test/test_trajectory_evals.py`.
Mutation-checked: yes, by hand; twelve mutants, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; the knowledge-graph check; the process gate against the commit.

Levers reviewed: `early-exit-keeps-the-record`, `guards-must-be-able-to-fail`, `declared-vs-enforced`, `ambiguous-signals`, `use-existing-apis`, `grep-for-siblings`, `test-that-cannot-fail`.

Scope at an earlier sign-off: kg:9b6d9d28af67
## Pass 8 — findings: 1

Ruff, pinned from `requirements-lint.txt`, over the whole tree before pushing.

1. **B017**: `test_a_call_with_no_tier_to_try_spends_nothing_against_the_run` asserted a bare `Exception`, so any failure, including the one the test set out to rule out, would satisfy it. It now expects the `RuntimeError` naming "No configured model tier".

## Pass 9 — findings: 0

- `agentsmith/test/test_token_limits.py`: 21 passed; ruff clean; mypy (pinned) clean over its scope.

## Sign-off (after lint)

Group 1 · DRY & shared code — [x] n/a — one assertion.
Group 2 · Quality / safety — [x] checked — the test now fails on any other error.
Group 3 · Architecture / hygiene — [x] n/a.
Group 4 · Process — [x] checked — found by the lint gate CI runs.
Group 5 · Intuitive UI — [x] n/a — no screen.
Group 6 · Signal integrity — [x] checked — a narrower assertion.
Group 7 · Auth & session integrity — [x] n/a.

Tests added: none; one assertion narrowed.
Mutation-checked: the earlier `text is None` mutant is still killed by the narrowed test.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: ruff; mypy; the test file; the process gate against the commit.

Levers reviewed: `test-that-cannot-fail`.

KG query: kg:5ef85d2d8a0e
