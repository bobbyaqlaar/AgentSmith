---
status: done
scope:
  - runtime/llm_gateway.py
  - runtime/test/test_idempotency_boundary.py
  - .agenticframework/process-gates.json
  - scripts/gate_pillars.py
  - scripts/test/test_gate_pillars.py
---
# The idempotency row is a boundary, and it is parsed like one

## Problem

`GatewayClient.complete()` writes a cache row as `result.__dict__` and reads it back as
`CompletionResult(**cached)`. The row is JSON in Postgres or Redis with a 24-hour TTL, written by
whichever build was deployed at the time, so every deploy that changes the class leaves a day of
rows shaped for a different one.

What happens then is not a crash. The unpack sits inside a `try` whose `except Exception` logs
`idempotency lookup failed` and falls through to a real completion, so a mismatched row means:

- the duplicate-call guarantee silently stops holding for that key;
- the tenant pays for a second completion;
- the log line reads like a database outage, when the truth is "this row was written by a
  different version of this class". An infrastructure message for a quality fact is exactly what
  P13 warns about — it is the shape of failure that teaches a team to ignore the log.

`json.dumps(..., default=str)` on the write side makes the quiet case worse: a value JSON cannot
encode comes back as a **string**, and nothing checks, so a typed object carries the wrong type
without any error at all.

The narrowed `P7-pydantic` check found this on 2026-09-17 and is right to: a model built out of
data the code did not write belongs to the receiving side.

## Approach

Parse the row where it enters, and leave the public type alone.

- **`_CachedCompletion`** — a Pydantic V2 model beside `CompletionResult`, with the same fields
  plus `v`, the row's schema version. It is the shape of the STORED ROW, which is the thing that
  crosses the boundary; `CompletionResult` itself is built from code-controlled values at its two
  other construction sites and is not a boundary model.
- **Read**: `model_validate(cached).to_result()`. A row that does not validate, or that carries a
  version this build does not know, is treated as a **miss** — the same recovery the code already
  takes — but logged as its own fact, at warning level, naming the field or the version. The
  infrastructure `logger.error` stays for what it was always about: the store being unreachable.
- **Write**: `from_result(result).model_dump()`, so the row is a declared shape rather than
  whatever `__dict__` happened to hold. A private attribute added later cannot leak into the row.
- **Version**: `CACHE_SCHEMA_VERSION = 1`. A row with no `v` is a legacy row from before this
  change; it has the same field names, so it validates and is used. A row with a HIGHER version
  was written by a newer build and is refused as a miss rather than guessed at.
- **Field parity is tested**, so a field added to `CompletionResult` without the row model fails a
  test rather than becoming a silent drop.
- `extra="forbid"`: an unexpected key is a miss with a message, never a silently discarded field.
- Moderation still re-runs on every cache hit (SEC-MOD-001); that behaviour is unchanged.

**One precision fix to the checker, in the same change.** With the row parsed, `to_result()`
still builds the result by unpacking — `CompletionResult(**self.model_dump())` — and
`P7-pydantic` flags it, because the AST sees the same `**`. The data there is provably validated:
it came out of a model this code just built. The rule means "built from data the code did not
write", so the rule learns that unpacking a `model_dump()` is not that. The alternative — writing
out every field at the call site to satisfy a checker — is worse code and a third copy of the
field list, and it is the kind of change that makes a check pass without making anything safer.
`X(**json.loads(raw))` still fails, which is the case that matters.

**Not done here, on purpose:** converting `CompletionResult` itself to a Pydantic model. It is a
public type in the compatibility matrix and keyword-only construction would break any tenant that
built one positionally — a major-version event for a type tenants mostly receive. If one model
library everywhere is wanted later, that change rides the next major.

## Pillars

- P1 applies — this note precedes the code; the option compared against it is recorded in `.agent-rfc/designs/idempotency-row-boundary.md`.
- P2 applies — no new dependency: `runtime/structured_output.py` already imports pydantic, pinned in `requirements.lock`.
- P3 applies — the hit and miss paths already report through `record_cache`; a refused row takes the miss path, so the counter keeps meaning what it says.
- P4 applies — failing tests first in `runtime/test/test_idempotency_boundary.py`, one per rejection reason.
- P7 applies — the row is validated on the receiving side by `_CachedCompletion`, a Pydantic V2 model.
- P8 n/a — no telemetry wiring changes; the existing metrics calls are untouched.
- P9 n/a — no orchestration.
- P10 applies — a row this cannot read is a second paid completion; `_CachedCompletion` is what stops that happening silently.
- P11 applies — the cache row is data this process did not write, and it is parsed, not trusted: `model_validate`.
- P12 applies — the row holds completion text and counts, never credentials; `runtime/idempotency.py` stores what it is given and this change narrows that to declared fields.
- P13 applies — no check is weakened: the allowlist entry for this file in `.agenticframework/process-gates.json` is removed rather than kept, so the rule applies here from now on.
- P14 applies — the stored row becomes a pinned shape (`CACHE_SCHEMA_VERSION`), and a field added on one side without the other fails a parity test.
- P15 applies — "the store is unreachable", "this row is from another version" and "a cache miss" are three different messages; `idempotency lookup failed` stays the infrastructure one.
- P16 applies — a row that cannot be read falls back to a real completion, which is what `record_cache` already counts as a miss; nothing raises at a cache hit that did not raise before.

## Deviations

none

## Dependencies

None added. `pydantic` 2.x is already in `requirements.lock` and already imported by
`runtime/structured_output.py`; no transitive additions.

## Levers

- `validate-on-the-receiving-side` — the row is parsed where it enters the process, not trusted because it once came from here.
- `ambiguous-signals` — a refused row is its own message at its own level, not a database error.
- `failure-mode-visibility` — the reason a duplicate call re-ran is in the log, with the field that did not match.
- `pin-unremovable-duplicates` — the row model repeats `CompletionResult`'s fields, so a test pins the two together.
- `when-the-fallback-fails` — the fallback is the miss path the code already takes; the change is that it says why.
- `gate-integrity` — the checker is made more precise about what it means, not quieter: the unvalidated case still fails, and the allowlist entry that covered this file is deleted rather than kept.
