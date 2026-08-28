# Review lever scalps

The evidence behind [`review-levers.md`](./review-levers.md). One entry per
lever, naming the defect that earned it.

Kept separate so the checklist stays usable, and kept at all because a lever
with no scalp is decoration — an item nobody can trace to a real failure is a
habit somebody once had, and it will be followed with the same conviction as one
that has caught things. `(legacy)` items are the deliberate exception: the
original standing list, exempt by design and absent from this file.

Numbering follows `review-levers.md` exactly. `scripts/test/test_lever_scalps.py`
fails if the two disagree.

---

## Group 1 · DRY & shared code

### 1.5 — One verdict, computed once

*Caught twice in one pass: `notify_eval_result(avg_score, fail_below)`
derived pass/fail itself while `run_scorecard` had already gated on parity,
the hallucination rate, a missed positive control and the adversarial guard
— so a fairness run that exited 1 and printed ❌ notified as ✅ at normal
urgency, on the copy of the verdict that reaches a human not watching CI.
And "Failing pairs" was listed against `fail_below` while the gate that
failed them used `parity_floor`, two numbers the code's own comment says
must never be coupled.*

### 1.6 — A catalog belongs to one module

*Caught: `SCORECARDS` restating `_shared.RESULTS_FILE`; the `Role` union written
three times; the audit event catalog in a union plus two arrays.*

### 1.7 — A duplicate that CANNOT be removed must be pinned

*Caught: three TS catalogs against `db/schema.sql`'s CHECK constraints, one of
them with a fourth copy in a route; `portal/lib/environment.ts` against
`runtime/environment.py`'s alias table.*

### 1.8 — **(++++) When you merge N copies, find the one that is already right —

*Caught: four resolvers turning an endpoint variable into an OTLP URL. The
TypeScript one was the only one that handled a base already naming
`/v1/traces` — the trap this repo's own docs set — so it became the shared
Python one rather than a fifth invention. And because it had only ever
resolved traces, it had never had to handle a base naming a DIFFERENT
signal; asking it for metrics would have produced `/v1/traces/v1/metrics`,
a case that did not exist until the two signals shared a resolver.*

## Group 2 · Quality / safety

### 2.4 — Environment parity

*Caught: `node:crypto` passing `tsc` and `npm test` and failing only `next build`;
`runtime/` never loading `.env`; a sweep whose coverage depended on whether its
own file was committed yet; mtimes rewritten by `actions/checkout`.*
*Caught: `toLocaleString()` in two server components and one client one —
one instant, four strings across four timezones and two different dates, plus
a hydration mismatch on every render.*

### 2.5 — A guard must be able to fail

*Caught: `if span is None` on a value that is never None; F-scenario drivers
raising `AssertionError` inside a caught block.*
*Caught: `redirect_to.startsWith("/")` accepting `//evil.example`, which
resolves to another origin.*
*Caught three times while turning mypy on: `reported = a is not None and b is
not None` followed by `int(a)`; `PgVectorStore.dsn` and `HashEmbedder._model`
guarded in `__init__` and used elsewhere; `any(v is None for v in values)`
before `int(v)`. Every one was correct and unreadable to the checker, which
is the same thing as unreadable to the next person.*

### 2.6 — Out-of-order and repeated messages

*Caught: a retried `running` heartbeat overwriting a terminal status, leaving
`finished_at` set — the widget reported a completed run as running for good,
and in a group that row masked a real `failed`. Every neighbouring column in
that upsert already carried the guard.*

### 2.7 — Ask what happens when the FALLBACK fails

*Caught: `run_with_self_correction` asks a model for a corrected payload and
parses it with `json.loads`. A model answering in prose — the ordinary
failure of "return ONLY JSON" — raised straight out of the method and past
`run_with_recoverable_step`, the human DLQ path. The most likely failure of
the automatic fixer was the one that stopped the work ever reaching a person.
Both twins, the plain loop and the Temporal one.*

### 2.8 — Validation belongs on the receiving side of a trust boundary

*Caught: `scripts/sync-portal-history.py` verified `replay_webhook_url` was
`http(s)` before sending it; the portal stored and fetched whatever arrived,
including from its other writer.*
*Caught: `scripts/notifier.py` interpolating a notification body into
`display notification "{message}"` and running it under `osascript`. A `"`
closes the literal and `do shell script` follows; the body reaching that
sink is `"\n".join(state["issues"])` — the Validator agent's own model
output. Confirmed by running it: the payload wrote a file.*

## Group 3 · Architecture / product hygiene

### 3.4 — Declared vs enforced

*Caught: `budget.monthly_usd_cap: 5` declared while $150 was enforced;
`tenant.id`, `workflow.task_queue`, `tenant.owner`, `workflow.engine`,
`redaction_profile` all declared and unread; pillar 3's span contract.*
*Caught: the `revoked_sessions` pruning schedule, stated only inside
`db/schema.sql` while the table grew a row per logout, forever.*

### 3.5 — Provenance and precedence

*Caught: `.zshrc` silently outranking every tenant's `tenant.owner`; the tenant id
in six places; two budget keys, one feeding the dashboard and one the enforcement.*

### 3.6 — Minimal host dependency

*ACCEPTED OPEN since 2026-08-24, not a scalp: 15 zsh functions and ~61 lines
in `~/.zshrc`, none testable, none portable. Recorded as accepted rather than
left looking like a finding nobody actioned — the lever still applies to new
work, and this instance is a known debt with an owner.*

### 3.7 — Implemented is not invoked. Ask "who calls this?" and grep

*Caught three times in one session, which is why it is a lever:
`configure_metrics()` had no caller in the framework, the tenant or the
example, so every counter wrote into a proxy meter that was never resolved;
`IdempotencyStore.purge_expired` had no caller while its table grew a row
per gateway call forever; `_DEFAULT_REGISTRY` was private with no accessor,
so a tool registered through the documented decorator could not be invoked
by anything.*
*And five more on the lever's first run, once it was written as a test
(`scripts/test/test_no_orphaned_entrypoints.py`): `get_logger`,
`notify_circuit_breaker`, `require_online`, `start_background_watcher` and
its `pass`-bodied partner `stop_background_watcher`, kept "for API symmetry"
with a function nothing called. All five deleted — an allowlist is where
dead code goes to become permanent. Collect references from the AST, not by
grepping text: a function named in a docstring is not a caller, and the
prose being right while the wiring is absent is the exact case.*

### 3.8 — Two owners, two cadences

*Caught: AgentSmith pinned and tracked its LIBRARY surface — `runtime/`
imported into the tenant process — and left the WIRE surface (span
attributes, the run-status POST, `agent_runs` columns) carrying no version
at all, though that is the surface IT upgrades unilaterally and the one the
monitoring product is built on. A v1.2.0 tenant's NULL cost and a current
tenant's broken exporter were the same cell.*
*Also caught, in the review itself: reading the tenant's version lag as a
defect to be fixed rather than as the independence the pin exists to
provide. A review that calls a designed separation a bug will propose
coupling as the remedy.*

## Group 4 · Process (how work is done)

### 4.4 — Review the branch, not the diff

*Caught: three review passes reporting clean while `main` had been red for three
commits, all three failures outside the reviewed diff.*

### 4.5 — When a fix lands, grep for the siblings

*Caught: the TS loader on 2 of 3 invocations; `return 2` graceful-skip on 1 of 2;
`is_recording()` correct in one function and absent in its sibling.*
*Caught: a tenant-supplied URL validated at two of three render sites; the
third was `templates/in-app-widget/widget.js`, which renders it as an `href`
inside the tenant's own product.*

### 4.6 — Run the gates locally before pushing

*Caught: a push that failed on SPECS.md's §16 repo-tree drift check — a new
module had been added to the module table and not to the tree — after a
local run of every gate the author happened to know about. Item 4 of this
group already says `self-test.yml` is the definitive list.*

## Group 5 · Intuitive UI

### 5.2 — An interface must not present a failure as a result

*Caught: a failed query rendering as "No shadow-eval failures in the last
24h". Lever 6.6 cites the same SENTENCE for a different defect — there, the
query worked and read one page of a paginated endpoint. One screen, two ways
to claim a clean result you do not have.*

## Group 6 · Signal integrity — does green mean green?

### 6.1 — Ambiguous signals

*Caught: a flagged-claim rate of `0.000` over zero cases; `passed: null` read as
falsy-as-fail; `input_tokens=0` for "the provider reported none".*

### 6.2 — Gate integrity

*Caught: `--check-kg` regenerating the graph and then asserting things about the
graph it had just written — green while the committed file was 703 lines stale.*

### 6.3 — Failure-mode visibility

*Caught: judged suites reporting NO VERDICT and exiting 0 on every push; an ignored
environment override; span attributes silently dropped onto a non-recording span.*

### 6.4 — Test the contract, not the helper

*Caught: `tenant.id == "acme"` asserted on a call that passed `tenant_id="acme"`,
while most real spans carried no tenant at all.*

### 6.5 — A test that cannot fail is a finding

*Caught: an import-graph walker that resolved zero files twice, both times passing.*

### 6.6 — An aggregate must name what it aggregated over

*Caught: a tenant page rendering the length of a list capped at 200 as the
issue COUNT, disagreeing with the dashboard's SQL count for the same tenant;
"Last 24h: N traces" taken from whichever project the Phoenix instance
happened to list first; "No shadow-eval failures in the last 24h" from one
page of a cursor-paginated endpoint — the same sentence lever 5.2 cites, but
a different defect: there the query FAILED, here it succeeded and saw a
fraction of the rows.*

### 6.7 — An early exit must not take the bookkeeping with it

*Caught: `scripts/circuit_breaker.py`'s burst tier raising between "append
the event" and "add this call's cost to the month", so every call that
tripped tier 1 — the heaviest bursts, the ones a spend cap most needs to
see — was free on the monthly ledger. Its two tiers were each tested alone
and never in the combination where they interact: the monthly test raises
the burst limit to 10,000,000 specifically to keep tier 1 out of the way.*

### 6.8 — **(2026-08-28) A check that fires on almost everything is as broken as

*Caught three times in three passes, all mine: an orphan-function grep that
flagged 190 of 192 (it counted occurrences wrong); an early-return sweep that
flagged 32 tests (`ast.walk` descends into test-local stub functions, whose
`return` is not the test's); a security-runner sweep reporting nine of eleven
with no verdict at all (they delegate to a shared body). Every one would have
been reported as findings by a reviewer who trusted the output.*

### 6.9 — **(2026-08-28) A test can pin a defect, and a confident docstring is w

*Caught: `test_pair_parity_coerces_missing_fairness_bit_to_zero` asserted
that two unscored members of a fairness pair are "equal" and score 1.0,
citing run-evals' historical normalization. `pair_parity`'s own docstring
said "pairs with fewer than two SCORED members are omitted". The test won,
the bias control reported "no divergence" about pairs it had never measured,
and the behaviour was carried into `runtime/` on promotion because a test
appeared to have decided it.*

