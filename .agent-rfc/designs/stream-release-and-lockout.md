---
status: active
scope:
  - agentsmith/llm_gateway.py
  - agentsmith/test/test_token_limits.py
  - portal/lib/signInPolicy.ts
  - portal/test/signInPolicy.test.ts
---
# A stream that never starts releases what it reserved, and a flood of names cannot reset the lockout

From the 4.1.0 review's second pass (the owner's local `review-4.1.0-pass2.md`): P2-R1 and P2-R18, two minors the
owner asked for before the release. Follows `.agent-rfc/designs/run-token-limits.md` (R1) and
`.agent-rfc/designs/portal-compliance-holds.md` (R17).

## Problem

- **P2-R1.** `complete_stream` reserves the run's tokens and the tenant's money, then calls `_resolve_endpoint` and
  `build_request` outside the `try` whose `except` calls `release()`. An error there (an Anthropic system prompt given
  as content blocks raises `TypeError` in `build_request`) keeps both reservations although nothing was sent: 502
  tokens and $1.00 in the review's run.
- **P2-R18.** The sign-in lockout keeps at most 10,000 names. At the cap it evicts the oldest entry that is not locked,
  so an attacker makes four guesses at `admin`, sends 10,000 invented names, and `admin`'s count starts again: four
  guesses per flood, the rate R17 described. And once the map is full of locked names, a new name is not tracked at
  all, so it can be guessed without limit for fifteen minutes.

## Approach

- **P2-R1.** Move `_resolve_endpoint` and `build_request` inside the `try` that releases, so every exit before the
  first byte is sent gives the reservations back. The existing fallback to `complete()` stays for provider exhaustion
  only; a request that cannot be built is not exhaustion, so it is raised after the release.
- **P2-R18.** A live count is never evicted: an entry leaves the map only when its fifteen-minute window has passed.
  The map holds up to 100,000 names (a few megabytes). When it is full of live entries, a name it does not hold is
  refused as locked, because it could not be counted: the lockout fails closed. The cost is stated: a flood of
  100,000 failed sign-ins inside fifteen minutes on one process (about 110 a second) refuses new names there until
  entries expire, rather than allowing unlimited guesses. Expired entries are pruned from the oldest (the map keeps
  insertion order, and an entry is re-inserted when its window restarts), at most once a second.

## Pillars

- P1 applies — P2-R1 and P2-R18 are the requirement; `.agent-rfc/designs/stream-release-and-lockout.md` is the plan.
- P2 applies — `agentsmith/llm_gateway.py` moves two calls into an existing `try`; `portal/lib/signInPolicy.ts` changes its eviction rule.
- P3 n/a — no spans or evaluations change.
- P4 applies — `agentsmith/test/test_token_limits.py` and `portal/test/signInPolicy.test.ts` gain the review's scenarios; hand mutants after.
- P7 n/a — no model choice changes.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 applies — `agentsmith/llm_gateway.py`: the money and run budgets are given back on a call that was never sent.
- P11 n/a — no untrusted content.
- P12 applies — `portal/lib/signInPolicy.ts` guards HTTP Basic passwords against guessing.
- P13 applies — `portal/test/signInPolicy.test.ts` holds both flood attacks; the lockout fails closed when it cannot count.
- P14 n/a — no fixture or baseline changes.
- P15 applies — `portal/lib/signInPolicy.ts`: "not tracked" no longer reads as "not locked".
- P16 applies — `CHANGELOG.md` states the trade: under a flood that fills the map, new names are refused until entries expire.

## Deviations

none

## Dependencies

none

## Levers

- `early-exit-keeps-the-record` — a raise between reserving and sending (P2-R1).
- `guards-must-be-able-to-fail` — the lockout is tested against the attacks that defeated it (P2-R18).
- `failure-is-not-a-result` — a name the map cannot hold is not a name with no failures.
- `test-that-cannot-fail` — hand mutants.
