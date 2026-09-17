# Review — the idempotency row is a boundary, and it is parsed like one

Design: `.agent-rfc/designs/idempotency-row-boundary.md`. Option B of three the owner compared
on 2026-09-18: validate the row, leave the public type alone.

**Built evidence (2026-09-18):**

- **Read the code before choosing.** The unpack sits inside a `try` whose `except Exception` logs
  and falls through, so the defect was never a crash — it was a silent re-run, a second paid
  completion, and an infrastructure-shaped log line for a quality fact. That is what made option B
  (parse the row) the right size of fix rather than option A (convert the public type, a
  compatibility-matrix event for a type tenants mostly receive).
- **Failing tests first.** `runtime/test/test_idempotency_boundary.py` (14) was written before
  `_CachedCompletion`; the module did not import on the first run.
- **The legacy row was designed for, not ignored.** Rows written before this change are the old
  `__dict__` and have the same field names, so `v` defaults to 0 and they validate and are used.
  A row from a NEWER build is refused by version rather than guessed at.
- **Mutation checks (each reverted):** ten — the row not validated, a newer row read anyway, an
  unexpected field dropped in silence, a refused row logged as an infra failure, a refused row
  served anyway, `__dict__` written again, a field lost from the row model, moderation no longer
  re-run on a hit, every unpack counted as validated, and any call counted as a validated dump.
  Eight caught on the first run; the two remaining are findings 1 and 2.

## Pass 1 — findings: 2

- `test-the-contract`, `consistent-auth-gates` — **finding:** "moderation re-runs on every cache
  hit (SEC-MOD-001)" was a comment with nothing behind it. This change MOVED that line into
  `_cached_completion`, and deleting it broke no test — a refactor could have dropped a security
  property silently. Two tests now: that the moderator sees the cached text, and that a block
  raises past the cache instead of being served.
- `gate-integrity` — **finding:** `_VALIDATED_CALLS` started as `{"model_dump", "dict"}` for
  Pydantic v1 compatibility, which would have matched `.dict()` on *any* object — a hole in a rule
  about validation, in the same change that tightens it. This repo is Pydantic V2; the set is
  `{"model_dump"}`, and a bare `dict(...)` is excluded by requiring a method call.

## Pass 2 — findings: 0

Every lever over the final diff: the model and its version rule, both cache paths, the three log
levels, the parity test, the checker's new precision, and the allowlist shrink. Considered and
declined: raising on a stale row instead of treating it as a miss — the miss is the recovery the
code already had, and turning a recoverable cache problem into a user-visible failure would be a
worse trade than the re-run it replaces. Recorded in the design.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_idempotency_boundary.py (14), test_gate_pillars.py (+1 for
                          the checker's new precision)
Mutation-checked:          yes — ten, each reverted; two survivors became pass 1
Fixtures re-pinned:        none stale; the stored row itself becomes a pinned shape
                          (CACHE_SCHEMA_VERSION) with a field-parity test
Gates run locally:         ruff, both suites, `process_gate.py pillars` (clean, allowlist
                          down to 2), the full pytest run
Declared gaps:             (1) a rollback to a build before this change re-runs cached calls
                              for up to the 24h TTL — it reads `"v"` as an unexpected keyword.
                              No error, a cost spike; stated in the CHANGELOG;
                          (2) `CompletionResult` stays a dataclass — one model library
                              everywhere is a major-version change, not this one;
                          (3) the rule still cannot see a dataclass filled field by field
                              from a parsed payload; that limit is unchanged.
```
