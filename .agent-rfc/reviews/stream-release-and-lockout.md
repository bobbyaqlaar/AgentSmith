# Review: stream-release-and-lockout

Each fix has a test that fails without it: `test_a_stream_that_cannot_be_built_gives_back_what_it_reserved` in
`agentsmith/test/test_token_limits.py` (the review's own case: 502 tokens and $1.00 kept), and the flood tests in
`portal/test/signInPolicy.test.ts` (the map had no `MAX_TRACKED` export and evicted live counts).
`test_a_stream_refused_by_the_compliance_guard_or_the_run_gives_everything_back` passed before the fix: it pins two
exits the second-pass review found untested (its surviving mutants M1 and M5), and both mutants are now killed.

## Pass 1 — findings: 1

Against `docs/review-levers.md`, by hand mutants (seven).

1. **Pruning from the front depends on an order no test held.** An entry whose window restarts must move behind the
   live ones; restarted in place, the pruner stops at it, the map stays full of expired names, and new names are
   refused for no reason. The mutant that drops the re-insertion survived. A test now fills the map, restarts its
   oldest name below the cap, fills it again, and expects a new name to be let through. Writing it found that the
   lockout tests share one module's state: a name left live by the test before let the pruner clear everything first,
   hiding the case. The test now starts from a map it filled and let expire.

## Pass 2 — findings: 0

- Seven mutants: build outside the `try`; no release on a compliance refusal; no money in `release()`; evict the oldest
  entry at the cap; let an uncountable name through; never prune; restart in place. All killed.
- `agentsmith/test/test_token_limits.py`, `agentsmith/test/test_ttft_stream.py` and the gateway tests: 36 passed.
  Portal `npm test`: exit 0. `npx tsc --noEmit`: clean. ruff: clean.
- Siblings: the stream's `except` handler reads none of the variables now assigned inside the `try` (`url`, `headers`,
  `body`). `complete()` already builds its request inside `_invoke`, under the `try` that releases. `proxy.ts` calls
  `isLockedOut` before checking the password, so an uncountable name is refused before any guess is tried.
- Stated trade, in the design, the code comment and the CHANGELOG: a flood that fills the map with live names refuses
  new names on that process for up to fifteen minutes, instead of letting them be guessed without limit. HTTP Basic is
  refused on a compliance profile, so this reaches non-profile portals only.

## Sign-off

Group 1 · DRY & shared code — [x] checked — no new helper; the stream's request is built where it is released.
Group 2 · Quality / safety — [x] checked — every exit before sending releases; the lockout fails closed when it cannot count.
Group 3 · Architecture / hygiene — [x] checked — two modules changed in place; one constant exported for the tests.
Group 4 · Process — [x] checked — design first; CHANGELOG and backlog updated.
Group 5 · Intuitive UI — [x] checked — a refused sign-in says "Too many failed sign-ins. Try again later.", as before.
Group 6 · Signal integrity — [x] checked — "not tracked" no longer reads as "not locked".
Group 7 · Auth & session integrity — [x] checked — `retry-bounds`: no attacker-driven path resets a live count.

Tests added: two in `agentsmith/test/test_token_limits.py`; four in `portal/test/signInPolicy.test.ts`.
Mutation-checked: yes, by hand; seven mutants, all killed after pass 1.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the suites above; `npm test`; `tsc`; ruff; `scripts/verify_system.py --check-kg`; the process gate against the commit.

Levers reviewed: `early-exit-keeps-the-record`, `guards-must-be-able-to-fail`, `failure-is-not-a-result`, `retry-bounds`, `test-that-cannot-fail`

KG query: kg:d8740b9c9176
