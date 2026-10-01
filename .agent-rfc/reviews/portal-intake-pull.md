# Review — portal-intake-pull

Design: `.agent-rfc/designs/portal-intake-pull.md`
Levers: `docs/review-levers.md`

Built in two commits under one design. Passes 1–3 cover **2a** — the contract
and the portal side (`9d5120f`). Passes 4–6 cover **2b** — the CLI. The sign-off
covers both.

## Pass 1 — findings: 3

1. **`guards-must-be-able-to-fail` — the race test did not race.** Removing the
   `consumed_at IS NULL AND expires_at > now()` guard from the consume `UPDATE`
   left all eight database tests green. The handler checked the row it had just
   read before opening the transaction, and that pre-check caught every repeat;
   five `Promise.all` consumes evidently did not interleave between read and
   write. The guard is what protects two portal instances from both consuming,
   and nothing tested it. Fixed by removing the pre-check, so the `UPDATE`'s own
   conditions are the only gate: now the mutation fails three tests, including
   the plain sequential "used once, then refused". The code is shorter for it.

   Worth recording how it nearly went unseen: my first attempt at the mutation
   was a `sed` that did not match, the `&&` chain stopped, and the output was
   silence — which reads like a pass. It was re-run as an exact string replace
   that asserts it applied.

2. **A green check that could not see the change.** The `docs/DESIGN.md`
   repo-tree drift check passed — and it reads `git ls-files`, so every new file
   was invisible to it while untracked. Re-run with 2a staged: still green, and
   its counts did not move, so `contract/`'s sub-tree is not one it inspects.
   That is a fact about the check, recorded rather than assumed.

3. **A tool changed a line I did not mean to touch.** Registering the three new
   test files by re-serialising `portal/package.json` with `json.dumps` re-escaped
   the `›` in its unrelated `description`. Reverted and redone as a text edit;
   the diff is now the two script lines. The registration itself matters: those
   scripts list every file explicitly, so an unregistered test never runs.

## Pass 2 — findings: 2

1. **`single-source-of-truth` — two clocks judged one expiry.** `unusable()`
   compared `expires_at` with the Node process's `Date.now()`; the consume
   `UPDATE` compares it with Postgres's `now()`. Under clock skew an intake could
   read as live and then fail to consume, and the fallback would have labelled
   that "the intake changed — retry". Both reads now select
   `expires_at <= now() AS expired`, so Postgres decides everywhere, and
   `portal/test/intakes.test.ts` pins that `lib/intakes.ts` consults no process
   clock.

2. **`pin-unremovable-duplicates` — two limits existed twice, unpinned.** The
   architecture pattern and the 500-character item limit are in both
   `portal/lib/intakes.ts` and `contract/intake/v1/record.schema.json`. The
   contract test pinned the enums, the tenant-id pattern and three limits, not
   these two. `ARCHITECTURE` is exported and both are pinned.

## Pass 3 — findings: 0

Re-read `portal/lib/intakes.ts`, the three routes, `portal/middleware.ts`, the
schema, the four test files and the two contract files against the levers after
the Pass 2 fixes.

- `consistent-auth-gates` — the create route is `portal/app/api/admin/apps/route.ts`'s
  two-step `can()` verbatim; the machine routes authenticate inside the handler as
  `/api/dev/ingest` does.
- `validate-on-the-receiving-side` — the portal validates what an author sends; what
  it serves back is what it wrote from validated input. The CLI's re-validation is 2b.
- `denied-vs-missing` — 401 for no or unknown token, 404 for an id the token does not
  open, 410 `consumed` and 410 `expired` with different words.
- `every-line-earns-its-place` — the one remaining defensive branch, the 409 after a
  refused `UPDATE`, is what `unusable()` needs to be total; its comment says the
  `UPDATE`'s conditions make it unreachable.
- Checked live, not only in tests: the built portal, started against a throwaway
  database, answered all seven requests as designed under Next's own matcher —
  `/api/dev/scaffold/:id` with no credentials got the handler's 401 and no
  basic-auth challenge; `/api/dev/scaffolding` got the middleware's challenge.

## Pass 4 — findings: 5

2b, found while building it. Before any code, reading `urllib` showed that
`HTTPRedirectHandler.redirect_request` keeps the `Authorization` header, so a
redirecting portal address would hand the token on; the design was amended to
refuse redirects before the client was written. `scripts/send_dev_record.py` has
the same exposure with the app's ingest token — outside this design, so a
backlog row, and the two scripts' address rule is now pinned to each other.

1. **mypy — my new parameter shadowed an existing local.** `_scaffold_tenant`'s
   `rfc` parameter shared its name with `rfc = _rfc_reference(root)`, a string,
   further down the same function. Harmless at runtime only because the
   parameter was used first. Renamed `intake_rfc`. Run with the pinned
   `mypy==1.14.1` through `uvx`, since it is not installed here; the only other
   errors were missing `yaml` stubs, which CI installs.
2. **The env-var sweep could not see the new variables — and passed anyway.**
   `runtime/intake.py` read `os.environ.get(TOKEN_VAR)` through a constant;
   `scripts/test/test_env_var_documentation.py` finds reads by their literal. It
   passed because "any tracked .md counts" and the design note committed in 2a
   names the variable — documentation no author would find. The reads are now
   literal, so the sweep enforces them; a test pins each literal to its constant;
   and both variables are in `docs/UserManual.md`'s Runtime Flags, where the
   sweep's own header says a variable belongs.
3. **My re-run advice was wrong.** The message for an intake whose RFC could not
   land said to re-run "with --force". `write_scaffold_records` never writes an
   RFC beside an existing one, forced or not. It now names the RFC that blocked
   it and says to move it aside.
4. **A column-0 `⚠️`** in the failed-consume message — the pattern
   `.github/scratch-tenants/build.sh:95` fails a tenant build on. Indented, and
   `test_a_failed_consume_leaves_the_scaffold_and_says_so` asserts the indent.
5. **A wrapper that added nothing.** `intake.render_rfc` only called
   `architectures.render_scaffold_rfc`. Removed.

## Pass 5 — findings: 2

1. **The token was in the object's repr.** `Intake` is a `@dataclass`, and the
   generated `__repr__` prints every field, `_token` included — so a traceback or
   a debug print of it would print the token. `field(repr=False)`, a test, and an
   eleventh mutation that puts it back and is caught.
2. **A test parameter that tested nothing.** The address-rule pin's `""` case
   returned before asserting. Removed, and two cases that do test something added
   in its place: `http://localhost.example.com` and `http://127.0.0.1@example.com`.

## Pass 6 — findings: 0

Re-read `runtime/intake.py`, the `tenant init` changes in `runtime/cli.py`, the
filled RFC in `runtime/architectures.py`, `runtime/test/test_intake.py` and the
new mutation suite against the levers.

- `validate-on-the-receiving-side` — every field re-checked; unknown fields
  refused; the id checked against the one asked for; `--from` digits-only before
  a URL exists.
- `when-the-fallback-fails` — a refused fetch writes nothing (tested: the
  directory stays empty); an RFC that could not land leaves the intake unused; a
  failed consume leaves a complete scaffold; a re-run after it consumes cleanly.
- `denied-vs-missing` — exit 2 to change something, 4 to retry, each with the
  portal's own words.
- Considered and accepted: should a newer portal ever offer an IDE this CLI
  cannot write, the refusal reads "--ide <name>: …" though the author typed
  `--from`. It still names the IDE and what is available, the catalog test keeps
  the portal and the CLI in step, and one IDE check for both paths is the design.
- **Checked end to end against the real portal**: built from the committed 2a,
  on a throwaway Postgres. The portal issued intake 1; `tenant init --from 1`
  scaffolded `e2e-orders` with the author's RFC, `ides: ["claude"]` and only
  `.claude/settings.json`, and consumed it; the same command again was refused
  with the portal's 410 and wrote nothing. Then the exact first-commit command
  `tenant init` printed was run: `pre-commit` skipped 169 vouched files, the
  process gate accepted `Review: n/a: generated scaffold` for 139 gated files
  matching the manifest, and the commit — the portal-authored RFC inside it —
  was made.

## Pass 7 — findings: 1

After `a44e586`, CI's `ruff` step failed: `scripts/mutation_check.py:497` was 133
characters, over the 120 limit — the https mutation's search string, which I
added in 2b. I had run ruff on `runtime/` only, with whatever ruff was installed;
CI runs the pinned `ruff==0.15.20` over the whole repository (`ruff check .`).
The sign-off below said "`ruff`" under gates run, which claimed more than was run.
The literal is split into two adjacent strings with the same content; the
mutation still applies (the harness reports "target absent" and exits 1 when a
search string no longer matches) and is still caught.

## Pass 8 — findings: 0

CI's exact command — `uvx --from ruff==0.15.20 ruff check .` — passes across the
repository, and the `intake` mutation suite is 11 of 11 caught after the split.

## Sign-off

Group 1 · DRY & shared code — [x] checked — 2a reuses the token shape, `APP_ID`, `Parsed`, `ISOLATION_VALUES` and the audit types; 2b reuses `validate_tenant_id`, `STACKS`, `ISOLATIONS`, slice 1's `--ide` check and the existing RFC path. The rules that must exist twice — the Python sets the portal mirrors, the contract's patterns and limits the CLI mirrors, and the portal address rule shared with `scripts/send_dev_record.py` — are each pinned by a test.
Group 2 · Quality / safety — [x] checked — 2a: 28 portal tests and four hand-run mutations, each caught. 2b: 55 tests in `runtime/test/test_intake.py` against a real local HTTP server, and an `intake` suite of 11 mutations in `scripts/mutation_check.py`, all caught. Both checked live, and end to end together.
Group 3 · Architecture / hygiene — [x] checked — the portal holds and the author's machine pulls; the portal never writes into a repository. `runtime/intake.py` is standard-library only because `runtime/` is vendored into tenants; the record's shape is one versioned contract.
Group 4 · Process — [x] checked — designed before code, and the design amended before the code that needed it (redirects, the token prompt, exit codes, consume-only-when-landed); six passes recorded, including the checks that passed while seeing nothing.
Group 5 · Intuitive UI — [x] gap — no screen until slice 4. The CLI's words were reviewed: each refusal says what to change or that the same command is the retry. Left for slice 4's form: nothing warns when an intake names a tenant id already registered, or already named by another open intake.
Group 6 · Signal integrity — [x] checked — consumed, expired, refused and unreachable are different answers with different exit codes; one clock decides expiry; nothing reads as success unless the scaffold, RFC included, was written.
Group 7 · Auth & session integrity — [x] checked — a per-intake token: hashed at rest, shown once, single-use under concurrency, 24 hours; never an argument, asked for without echo, never in a repr, never across a redirect, never over plain http to another host. The path that skips sign-in is pinned by `portal/test/middleware.test.ts`.

Tests added: 2a — `portal/test/intakes.test.ts` (14), `portal/test/intakesDb.test.ts` (8), `portal/test/middleware.test.ts` (6), two in `portal/test/catalogs.test.ts`. 2b — `runtime/test/test_intake.py` (55).
Mutation-checked: 2b — `scripts/mutation_check.py` suite `intake`, 11 mutations, all caught. 2a — four by hand, each caught; `scripts/mutation_check.py` drives pytest only, so portal mutations there need node and Postgres in that job, which this design does not cover.
Fixtures re-pinned: none stale. `contract/intake/v1/fixture.json` is pinned from both sides now — the portal's tests and `runtime/test/test_intake.py`'s stub portal serve it.
Gates run: 2b — the pinned `ruff==0.15.20` over the whole repository, as CI runs it (Pass 7: it was first run on `runtime/` only), `mypy==1.14.1` (47 files, clean), the `intake` mutation suite, the doc and env-var sweeps, the end-to-end run against the real portal, and the Python suite — 2054 passed, 10 skipped, with the doc-reading tests re-run after the last `docs/DESIGN.md` edit. 2a's are recorded in Pass 3 and were green in CI on `9d5120f`.

Levers reviewed: `validate-on-the-receiving-side`, `consistent-auth-gates`, `denied-vs-missing`, `single-source-of-truth`, `pin-unremovable-duplicates`, `guards-must-be-able-to-fail`, `when-the-fallback-fails`, `every-line-earns-its-place`, `implemented-not-invoked`, `use-existing-apis`, `docs-match-behaviour`, `search-before-writing`, `small-verified-slices`.

KG query: kg:95d62282382a
