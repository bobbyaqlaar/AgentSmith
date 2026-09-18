# Review lever notes

Why each lever in [`review-levers.md`](./review-levers.md) exists, and the defect
it earned its place with. The checklist stays one line per item so it can be
worked down; this is where the reasoning and the evidence live, so nothing there
has to be taken on trust.

Keyed by **slug**, the same identifier the checklist uses, so reordering a lever
cannot orphan its notes. `(legacy)` items — the original standing list — are
exempt by design and absent here. `scripts/test/test_lever_notes.py` fails if the
two files disagree.

---

## Group 1 · DRY & shared code

### `one-verdict` — One verdict, computed once

**Why.** A decision recomputed downstream, from different inputs than the one that made it, is right at both sites and wrong between them. Data duplication drifts loudly; a duplicated DECISION drifts silently, because each copy looks locally correct. Pass the verdict, never the ingredients to re-derive it.

*Caught twice in one pass: `notify_eval_result(avg_score, fail_below)`
derived pass/fail itself while `run_scorecard` had already gated on parity,
the hallucination rate, a missed positive control and the adversarial guard
— so a fairness run that exited 1 and printed ❌ notified as ✅ at normal
urgency, on the copy of the verdict that reaches a human not watching CI.
And "Failing pairs" was listed against `fail_below` while the gate that
failed them used `parity_floor`, two numbers the code's own comment says
must never be coupled.*

### `one-catalog` — A catalog belongs to one module

**Why.** A list of valid suites, roles, event types or file names restated anywhere else is a second catalog that will drift.

*Caught: `SCORECARDS` restating `_shared.RESULTS_FILE`; the `Role` union written
three times; the audit event catalog in a union plus two arrays.*

### `pin-unremovable-duplicates` — A duplicate that CANNOT be removed must be pinned

**Why.** The four items above and `one-catalog` all say "extract to one module", which is impossible across a language or system boundary — a TypeScript catalog and a SQL `CHECK`, a Python resolver and its TypeScript mirror, a client-side validation and its server. The lever gave advice that could not be followed, so those cases fell straight through it. The substitute is a test that PARSES the other side rather than restating it, because a test that hardcodes the second copy is just a third copy.

*Caught: three TS catalogs against `db/schema.sql`'s CHECK constraints, one of
them with a fourth copy in a route; `portal/lib/environment.ts` against
`runtime/environment.py`'s alias table.*

### `merge-the-right-copy` — When you merge N copies, find the one that is already right — and
  expect the merged version to face inputs none of them did

**Why.** Two halves. First: several implementations of one rule usually include a correct one, and writing a fresh N+1 discards whatever it learned. Read them all, pick the survivor, and say why in the module that keeps it. Second: extraction is not relocation. Each copy was correct for the narrow domain its own caller fed it, and the merged one is reachable from every caller at once, so cases that were unreachable per-copy become live on the first day.

*Caught: four resolvers turning an endpoint variable into an OTLP URL. The
TypeScript one was the only one that handled a base already naming
`/v1/traces` — the trap this repo's own docs set — so it became the shared
Python one rather than a fifth invention. And because it had only ever
resolved traces, it had never had to handle a base naming a DIFFERENT
signal; asking it for metrics would have produced `/v1/traces/v1/metrics`,
a case that did not exist until the two signals shared a resolver.*

## Group 2 · Quality / safety

---

## Group 2 · Quality / safety

### `environment-parity` — Environment parity

**Why.** Does this behave the same on a developer machine, in CI, and in production? Name what differs — runtime, filesystem, clock, git state. **(++)** The second environment is often INSIDE the app: server component vs client component, worker vs request, build vs run. Same question, same clock.

*Caught: `node:crypto` passing `tsc` and `npm test` and failing only `next build`;
`runtime/` never loading `.env`; a sweep whose coverage depended on whether its
own file was committed yet; mtimes rewritten by `actions/checkout`.*
*Caught: `toLocaleString()` in two server components and one client one —
one instant, four strings across four timezones and two different dates, plus
a hydration mismatch on every render.*

### `guards-must-be-able-to-fail` — A guard must be able to fail

**Why.** Assertions inside the `try` they guard, conditions that can never be true, `except Exception` around the check itself. **(++)** And a guard that CAN fail can still be too weak to hold: ask what the check would let through, not only whether it runs. **(2026-08-28)** And write the guard so a type checker can follow it, because a reader follows the same path. Narrowing that goes through an intermediate boolean, or that happens in a different method from the use, is narrowing only a human who already knows the code can see.

*Caught: `if span is None` on a value that is never None; F-scenario drivers
raising `AssertionError` inside a caught block.*
*Caught: `redirect_to.startsWith("/")` accepting `//evil.example`, which
resolves to another origin.*
*Caught three times while turning mypy on: `reported = a is not None and b is
not None` followed by `int(a)`; `PgVectorStore.dsn` and `HashEmbedder._model`
guarded in `__init__` and used elsewhere; `any(v is None for v in values)`
before `int(v)`. Every one was correct and unreadable to the checker, which
is the same thing as unreadable to the next person.*

### `out-of-order-and-repeated` — Out-of-order and repeated messages

**Why.** Every best-effort POST, retry, heartbeat and at-least-once queue means two writes can arrive in the other order, or twice. Ask it of each one: what does the row look like then? An upsert is where this lands, and a guard applied to four columns and not the fifth is the usual shape.

*Caught: a retried `running` heartbeat overwriting a terminal status, leaving
`finished_at` set — the widget reported a completed run as running for good,
and in a group that row masked a real `failed`. Every neighbouring column in
that upsert already carried the guard.*

### `when-the-fallback-fails` — Ask what happens when the FALLBACK fails

**Why.** Every recovery ladder — retry, then auto-correct, then park it for a human — is reviewed at the rungs and not at the joints. The question is not "does step B work" but "when step B FAILS, does control reach step C, or does B's failure escape the ladder entirely?" A recovery step that raises is the case nobody writes a test for, because the step exists to handle failure and is not imagined as a source of it.

*Caught: `run_with_self_correction` asks a model for a corrected payload and
parses it with `json.loads`. A model answering in prose — the ordinary
failure of "return ONLY JSON" — raised straight out of the method and past
`run_with_recoverable_step`, the human DLQ path. The most likely failure of
the automatic fixer was the one that stopped the work ever reaching a person.
Both twins, the plain loop and the Temporal one.*

### `validate-on-the-receiving-side` — Validation belongs on the receiving side of a trust boundary

**Why.** A check the caller performs is a courtesy; the same check where the value is accepted is a control. Finding the rule already implemented on the wrong side is the tell — it means someone knew, and put it where it does not bind. **(+++)** The receiving side is often an INTERPRETER, not a network peer. Text spliced into shell, AppleScript, SQL or HTML source has crossed into a language whether or not it left the process — so ask of every string built with `f"..."` and then handed to something that EXECUTES it: what is the most hostile value the source of this string can produce?

*Caught: `scripts/sync-portal-history.py` verified `replay_webhook_url` was
`http(s)` before sending it; the portal stored and fetched whatever arrived,
including from its other writer.*
*Caught: `scripts/notifier.py` interpolating a notification body into
`display notification "{message}"` and running it under `osascript`. A `"`
closes the literal and `do shell script` follows; the body reaching that
sink is `"\n".join(state["issues"])` — the Validator agent's own model
output. Confirmed by running it: the payload wrote a file.*

## Group 3 · Architecture / product hygiene

---

## Group 3 · Architecture / product hygiene

### `declared-vs-enforced` — Declared vs enforced

**Why.** Every control a config file or doc declares must have something that reads it. A declared-but-unenforced control is worse than an absent one: it reads as a control in an audit and is not one. **(++)** Includes controls whose enforcer is a HUMAN: an instruction filed where its audience never reads is not assigned to anyone.

*Caught: `budget.monthly_usd_cap: 5` declared while $150 was enforced;
`tenant.id`, `workflow.task_queue`, `tenant.owner`, `workflow.engine`,
`redaction_profile` all declared and unread; pillar 3's span contract.*
*Caught: the `revoked_sessions` pruning schedule, stated only inside
`db/schema.sql` while the table grew a row per logout, forever.*

### `provenance-and-precedence` — Provenance and precedence

**Why.** Where can this value come from, and when two sources disagree, which wins and is that written down? Distinguish a channel the operator *declared* from one that is merely *ambient*.

*Caught: `.zshrc` silently outranking every tenant's `tenant.owner`; the tenant id
in six places; two budget keys, one feeding the dashboard and one the enforcement.*

### `minimal-host-dependency` — Minimal host dependency

**Why.** What does this require of the machine beyond the package — a shell profile, a specific shell, a writable `$HOME`, an OS?

*ACCEPTED OPEN since 2026-08-24, not a scalp: 15 zsh functions and ~61 lines
in `~/.zshrc`, none testable, none portable. Recorded as accepted rather than
left looking like a finding nobody actioned — the lever still applies to new
work, and this instance is a known debt with an owner.*

### `implemented-not-invoked` — Implemented is not invoked. Ask "who calls this?" and grep

**Why.** The inverse of `declared-vs-enforced`: not a control that is declared and unenforced, but one that is fully BUILT and never reached. Correct code, correct tests, zero call sites. It is invisible precisely because everything you would inspect looks right, and a component that no-ops when uninstalled — the usual, correct choice for telemetry — cannot tell you it was never installed. The check costs one grep per public entry point, and it should run against the ENTRYPOINTS a deployment actually starts: the worker, the CLI, the container command.

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

### `two-owners-two-cadences` — Two owners, two cadences

**Why.** For every interface, ask who ships each side and whether they can deploy independently. When the answer is yes — platform team and product team, IT and the business, framework and tenant — then a version lag is the DESIGN, not a defect, and three things must exist: a version on the wire, a written compatibility window, and consumers that read an unknown or absent field as "other version" rather than "fault". Pinning gives the downstream side a cadence of its own; it does not by itself tell the upstream side what it must keep accepting.

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

---

## Group 4 · Process (how work is done)

### `review-the-branch` — Review the branch, not the diff

**Why.** Scope the pass by what the branch ships and what CI checks — `self-test.yml` is the definitive list — not by the files you edited.

*Caught: three review passes reporting clean while `main` had been red for three
commits, all three failures outside the reviewed diff.*

### `grep-for-siblings` — When a fix lands, grep for the siblings

**Why.** A fix applied at one call site and not its identical neighbours is the most repeated defect in this codebase. **(++)** Follow the DATA, not the directory. The sibling that gets missed is the one in another package, another language, or another repo — searching where you are editing finds every copy except that one.

*Caught: the TS loader on 2 of 3 invocations; `return 2` graceful-skip on 1 of 2;
`is_recording()` correct in one function and absent in its sibling.*
*Caught: a tenant-supplied URL validated at two of three render sites; the
third was `templates/in-app-widget/widget.js`, which renders it as an `href`
inside the tenant's own product.*

### `run-the-gates-ci-lists` — Run the gates locally before pushing

**Why.** — and check the git state matches what CI will see, or the local run is not the same run. **(++++)** Run the ones CI LISTS, not the ones you remember. Enumerate the workflow's steps and work down them; a subset that passes is not a pass.

*Caught: a push that failed on docs/DESIGN.md's §16 repo-tree drift check — a new
module had been added to the module table and not to the tree — after a
local run of every gate the author happened to know about. Item 4 of this
group already says `self-test.yml` is the definitive list.*

## Group 5 · Intuitive UI

---

## Group 5 · Intuitive UI

### `failure-is-not-a-result` — An interface must not present a failure as a result

**Why.** Empty, zero and unavailable are three different things on a screen as much as in a metric.

*Caught: a failed query rendering as "No shadow-eval failures in the last
24h". Lever 6.6 cites the same SENTENCE for a different defect — there, the
query worked and read one page of a paginated endpoint. One screen, two ways
to claim a clean result you do not have.*

### `irreversible-needs-confirmation` — An action that cannot be undone says so before it fires

**Why.** DLQ discard and replay are live actions in the Ops Portal today, and a HITL approve/reject screen is about to join them — each is effectively one-way once the discard or the Temporal signal has gone out. A control that fires on a single click gives an operator no chance to notice they picked the wrong row before it is gone.

*Not yet caught — added ahead of the HITL approve/reject build rather than after it ships without one. `(unevidenced)`.*

### `no-double-submit` — A write-triggering control cannot be fired twice by its own UI

**Why.** Group 2's `out-of-order-and-repeated` already asks what a row looks like when a write arrives twice or reversed at the backend; nothing asks the same question of the button that sends it. An approve/reject action is a Temporal signal, and a second click landing before the first response returns is the UI manufacturing the exact race that lever exists to catch.

*Not yet caught. `(unevidenced)`.*

### `denied-vs-missing` — "Not authorized" and "not found" are different screens

**Why.** The portal is multi-tenant with RBAC and optional SSO. `ambiguous-signals` (Group 6) already says one value must not mean two things; this is that rule asked of an auth screen. "You cannot see this" and "this does not exist" read identically to an operator and point to opposite next actions — request access, or conclude the record was never there.

*Not yet caught. `(unevidenced)`.*

### `stale-data-is-labelled` — A number an operator could act on names when it was last measured

**Why.** Cost-vs-cap and run history are exactly the kind of number an ops team acts on — pausing a tenant, approving spend. This entire lever set exists because green does not always mean measured now; that principle has a UI half nobody had written down.

*Not yet caught. `(unevidenced)`.*

### `keyboard-and-screen-reader-operable` — Every control reachable without a mouse or sight

**Why.** An ops console only one kind of operator can drive is a console the team cannot fully staff, and it is the most honestly unevidenced entry on this list — no portal screen has been reviewed against it yet. Said plainly rather than implied otherwise, which is the entire point of marking it `(unevidenced)` instead of writing it up as something it caught.

*Not yet caught — added on request, ahead of the HITL screens, so review works down this list from the first build instead of retrofitting it later.*

### `works-at-real-viewport-sizes` — No control clipped, overlapped or scroll-trapped at the sizes people actually run

**Why.** Ops staff run this at whatever window size their day has, not a design canvas. A control trapped behind a scrollbar or clipped by a narrow pane is unusable, which is a different failure from merely looking cramped.

*Not yet caught. `(unevidenced)`.*

### `matches-the-existing-component-language` — A new screen reuses the app's existing components, not a one-off

**Why.** `one-catalog` and `single-source-of-truth` (Groups 1 and 3) already say a concept belongs in one place; a new screen inventing its own spacing and button style is the UI version of a second implementation of "what a button looks like here," and it will drift from the first one the same way any duplicated logic does.

*Not yet caught. `(unevidenced)`.*

## Group 6 · Signal integrity — does green mean green?

---

## Group 6 · Signal integrity — does green mean green? **(+ new group)**

### `ambiguous-signals` — 

**Why.** **Ambiguous signals.** One value must not mean two things. `0.0`, `[]`, `None`, a skip — each is routinely used for both "measured, all good" and "never measured". Report the states separately and name them.

*Caught: a flagged-claim rate of `0.000` over zero cases; `passed: null` read as
falsy-as-fail; `input_tokens=0` for "the provider reported none".*

### `gate-integrity` — 

**Why.** **Gate integrity.** Can this check fail? Does it verify its own output? Does a threshold still mean something after being moved?

*Caught: `--check-kg` regenerating the graph and then asserting things about the
graph it had just written — green while the committed file was 703 lines stale.*

### `failure-mode-visibility` — 

**Why.** **Failure-mode visibility.** When this fails, will anyone know? Exit 0 plus a green check is how a gate stops grading and nobody notices.

*Caught: judged suites reporting NO VERDICT and exiting 0 on every push; an ignored
environment override; span attributes silently dropped onto a non-recording span.*

### `test-the-contract` — 

**Why.** **Test the contract, not the helper.** Assert over the artifact or the emitted signal, not over the function that produced it with the input you just handed it.

*Caught: `tenant.id == "acme"` asserted on a call that passed `tenant_id="acme"`,
while most real spans carried no tenant at all.*

### `test-that-cannot-fail` — 

**Why.** **A test that cannot fail is a finding.** Sweeps that match nothing, loops over empty collections, guards exempting themselves.

*Caught: an import-graph walker that resolved zero files twice, both times passing.*

### `aggregates-name-their-scope` — An aggregate must name what it aggregated over

**Why.** A count, a rate, or a "nothing found" claim is only checkable if it states its scope — which project, how many rows, which window, and whether the source had more to give. This is not `ambiguous-signals`: the number is not ambiguous, it is unattributed, and a reader has no way to notice.

*Caught: a tenant page rendering the length of a list capped at 200 as the
issue COUNT, disagreeing with the dashboard's SQL count for the same tenant;
"Last 24h: N traces" taken from whichever project the Phoenix instance
happened to list first; "No shadow-eval failures in the last 24h" from one
page of a cursor-paginated endpoint — the same sentence lever 5.2 cites, but
a different defect: there the query FAILED, here it succeeded and saw a
fraction of the rows.*

### `early-exit-keeps-the-record` — An early exit must not take the bookkeeping with it

**Why.** When a function both RECORDS something and DECIDES something, every `raise`, `return` and `break` between the two skips the record. Ask of each one: what had this function already committed to that it is now not going to finish? Tripping, denying and rejecting are decisions about what happens NEXT — never grounds to un-record what already happened. The tell is a guard sitting textually between an append and an accrual.

*Caught: `scripts/circuit_breaker.py`'s burst tier raising between "append
the event" and "add this call's cost to the month", so every call that
tripped tier 1 — the heaviest bursts, the ones a spend cap most needs to
see — was free on the monthly ledger. Its two tiers were each tested alone
and never in the combination where they interact: the monthly test raises
the burst limit to 10,000,000 specifically to keep tier 1 out of the way.*

### `check-that-fires-on-everything` — A check that fires on almost everything is as broken as one
  that never fires

**Why.** `test-that-cannot-fail` covers the sweep that matches nothing. This is its twin, and it is the one that wastes a reviewer's afternoon: a query returning a result too large to match what the code obviously does is a broken query, not a discovery. Read the count before reading the hits — if a sweep says most of the codebase is defective, the sweep is the defect.

*Caught three times in three passes, all mine: an orphan-function grep that
flagged 190 of 192 (it counted occurrences wrong); an early-return sweep that
flagged 32 tests (`ast.walk` descends into test-local stub functions, whose
`return` is not the test's); a security-runner sweep reporting nine of eleven
with no verdict at all (they delegate to a shared body). Every one would have
been reported as findings by a reviewer who trusted the output.*

### `test-that-pins-a-defect` — A test can pin a defect, and a confident docstring is what
  makes it survive

**Why.** `test-that-cannot-fail` is a test that cannot fail. This one can, and does, and asserts the wrong thing — so it defends the defect from the next reviewer. The tell is a test whose docstring justifies surprising behaviour by HISTORY rather than by a requirement: "preserves the previous normalization", "matches what the old script did". That sentence reads as due diligence and functions as a lock. When you meet one, ask what the behaviour SHOULD be, not what it has been — and check the docstring of the function under test, which in the worst case already promises the opposite.

*Caught: `test_pair_parity_coerces_missing_fairness_bit_to_zero` asserted
that two unscored members of a fairness pair are "equal" and score 1.0,
citing run-evals' historical normalization. `pair_parity`'s own docstring
said "pairs with fewer than two SCORED members are omitted". The test won,
the bias control reported "no divergence" about pairs it had never measured,
and the behaviour was carried into `runtime/` on promotion because a test
appeared to have decided it.*

### `fixture-truth` — Do not prove "not mock" by forbidding strings real fixtures also use

**Why.** A test asserting "the mock name never appears" is checking the wrong
thing when the real seed data or a shared fixture uses that same name — the
assertion passes on a skeleton with no data rendered yet just as readily as on
a correct page, because neither state contains the forbidden string. Assert a
positive signal instead: a uniquely created name, an auth header, or the
signed-in chrome.

*Caught (AqlaarTeleologyStudio): `expect("Acme Corp").toHaveCount(0)` after
SSO sign-in, meant to prove the mock tenant was gone — but the API's own seed
data IS "Acme Corp", and the same assertion passed on the loading skeleton
before any card had rendered.*

## Group 7 · Auth & session integrity

### `channel-precedence` — List every identity channel and say which wins

**Why.** A session can arrive through more than one channel at once — browser
storage, an httpOnly cookie, a demo header, a middleware-forwarded internal
header — and if precedence between them is never written down, whichever one
happens to be checked first becomes the de facto rule, silently, and a weaker
channel can end up impersonating a stronger one.

*Caught (AqlaarTeleologyStudio): a server component read a Bearer token off a
header the browser could set directly; client-side `sessionStorage` expired
about 30 seconds before the access cookie it was meant to mirror, so which one
"won" depended on timing.*

### `untrusted-headers-are-not-a-session` — A browser-settable header is not a cookie

**Why.** Anything the client can set is not equivalent to an httpOnly cookie,
even when it is only meant for same-request, server-to-server forwarding.
Left unstripped past the point it was forwarded for, it becomes a channel a
client can drive on its own.

*Caught (AqlaarTeleologyStudio): `x-ots-refreshed-access` accepted from the
client directly, until stripped on every continue path and set only after a
successful server-side token exchange.*

### `same-request-cookie-invisibility` — A `Set-Cookie` in this response isn't visible to this render

**Why.** Middleware or a route handler setting a cookie does not make that
cookie visible to `cookies()` or the app server within the SAME request/render
— cookies take effect on the next request. If a later step in that same
request needs the new value, it has to be forwarded explicitly, not read back
out of the cookie jar.

*Caught (AqlaarTeleologyStudio): an idle SSO deep link 401'd until the new
access token was forwarded as an explicit request header instead of being
re-read from `cookies()` in the same render that had just set it.*

### `in-flight-must-not-undo-logout` — A race must not restore a session the user just ended

**Why.** Cookie-clear and token-refresh calls that were already in flight when
a user signs out or navigates away can complete AFTER the sign-out and put the
session back. Fire-and-forget logout and refresh calls need a keepalive,
an await, or a generation/cancelled flag so a late response cannot win.

*Caught (AqlaarTeleologyStudio): a `void fetch("/logout")` aborted mid-flight
by the Keycloak redirect it triggered; a token-refresh handler calling
`setAuthSession` after sign-out had already cleared it, reviving the session
it was told to end.*

### `retry-bounds` — At most one refresh-and-retry on a 401

**Why.** A 401 handler that retries without a bound can retry-storm against
an identity provider, and a failed refresh must clear the session outright —
treating a failed refresh as `no-fake-offline-fallback`'s offline/mock state
just hides an ended session behind a UI that looks like a network hiccup.

*Caught (AqlaarTeleologyStudio): a failed middleware refresh left both the
access and refresh cookies in place until an explicit `clearTokenCookies`
call was added to the failure path.*
