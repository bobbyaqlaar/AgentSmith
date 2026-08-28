# Review levers

The checklist a review pass runs against. Six groups; work down them.

**Each lever has a slug — that is its identifier, not its position.** Order is
for reading; slugs are for citing. Items can be added, reordered or regrouped
without invalidating a single reference, which is why there are no numbers here.

Every lever carries the defect it earned its place with, in
[`review-lever-scalps.md`](./review-lever-scalps.md). This file stays short so it
can be used; that one stays long so nothing here has to be taken on trust.

`(legacy)` marks the original standing list. Those are exempt from the evidence
requirement by design and are kept as a hygiene checklist — the things worth
confirming every pass whether or not a defect has been filed against any one.

Other marks record when an item arrived: `(+)` 2026-08-24, `(++)` and `(+++)`
2026-08-25, `(++++)` 2026-08-26, dates thereafter. Amendments to an existing item
carry their own mark inline.

**Citing a lever from code:** write the slug — `review-levers: grep-for-siblings`.
`scripts/test/test_lever_references.py` fails on a slug that does not exist.

---

## 1 · DRY & shared code

- `no-redundant-artifacts` — **(legacy)** No redundant code, files, or docs at the end of a slice — dead
  imports, unused exports and obsolete files included. *(Was two items, 1 and
  5, saying the same thing in the group about things that say the same thing.)*
- `no-copy-paste` — **(legacy)** No copy-paste functions (even under other names / other files) — extract to a shared library.
- `search-before-writing` — **(legacy)** Before writing a new function: search existing shared helpers first; reuse/extend.
- `parameterize-dont-clone` — **(legacy)** Prefer one parameterized helper over near-duplicates (vary by args, not by cloning).
- `one-verdict` — **(2026-08-28) One verdict, computed once.** A decision recomputed
  downstream, from different inputs than the one that made it, is right at
  both sites and wrong between them. Data duplication drifts loudly; a
  duplicated DECISION drifts silently, because each copy looks locally
  correct. Pass the verdict, never the ingredients to re-derive it.
- `one-catalog` — **(+) A catalog belongs to one module.** A list of valid suites, roles, event types or
  file names restated anywhere else is a second catalog that will drift.
- `pin-unremovable-duplicates` — **(++) A duplicate that CANNOT be removed must be pinned.** The four
  items above and `one-catalog` all say "extract to one module", which is impossible across a language or system
  boundary — a TypeScript catalog and a SQL `CHECK`, a Python resolver and its
  TypeScript mirror, a client-side validation and its server. The lever gave
  advice that could not be followed, so those cases fell straight through it.
  The substitute is a test that PARSES the other side rather than restating it,
  because a test that hardcodes the second copy is just a third copy.
- `merge-the-right-copy` — **(++++) When you merge N copies, find the one that is already right — and
  expect the merged version to face inputs none of them did.** Two halves.
  First: several implementations of one rule usually include a correct one,
  and writing a fresh N+1 discards whatever it learned. Read them all, pick
  the survivor, and say why in the module that keeps it. Second: extraction
  is not relocation. Each copy was correct for the narrow domain its own
  caller fed it, and the merged one is reachable from every caller at once,
  so cases that were unreachable per-copy become live on the first day.

## 2 · Quality / safety

- `use-existing-apis` — **(legacy)** Prefer standard, optimised, safe, secure library/APIs already in the repo — don't invent parallel paths.
- `consistent-auth-gates` — **(legacy)** Security/scope consistency matters: same gate pattern across mutating routes (no "forgot ActorDep / scope" holes).
- `no-fake-offline-fallback` — **(legacy)** Don't hide auth failures as "offline/mock" — network fallback only when appropriate.
- `environment-parity` — **(+) Environment parity.** Does this behave the same on a developer machine, in
  CI, and in production? Name what differs — runtime, filesystem, clock, git state.
  **(++)** The second environment is often INSIDE the app: server component vs
  client component, worker vs request, build vs run. Same question, same clock.
- `guards-must-be-able-to-fail` — **(+) A guard must be able to fail.** Assertions inside the `try` they guard,
  conditions that can never be true, `except Exception` around the check itself.
  **(++)** And a guard that CAN fail can still be too weak to hold: ask what
  the check would let through, not only whether it runs.
  **(2026-08-28)** And write the guard so a type checker can follow it, because
  a reader follows the same path. Narrowing that goes through an intermediate
  boolean, or that happens in a different method from the use, is narrowing
  only a human who already knows the code can see.
- `out-of-order-and-repeated` — **(++) Out-of-order and repeated messages.** Every best-effort POST, retry,
  heartbeat and at-least-once queue means two writes can arrive in the other
  order, or twice. Ask it of each one: what does the row look like then? An
  upsert is where this lands, and a guard applied to four columns and not the
  fifth is the usual shape.
- `when-the-fallback-fails` — **(2026-08-28) Ask what happens when the FALLBACK fails.** Every recovery
  ladder — retry, then auto-correct, then park it for a human — is reviewed at
  the rungs and not at the joints. The question is not "does step B work" but
  "when step B FAILS, does control reach step C, or does B's failure escape the
  ladder entirely?" A recovery step that raises is the case nobody writes a
  test for, because the step exists to handle failure and is not imagined as a
  source of it.
- `validate-on-the-receiving-side` — **(++) Validation belongs on the receiving side of a trust boundary.** A
  check the caller performs is a courtesy; the same check where the value is
  accepted is a control. Finding the rule already implemented on the wrong side
  is the tell — it means someone knew, and put it where it does not bind.
  **(+++)** The receiving side is often an INTERPRETER, not a network peer.
  Text spliced into shell, AppleScript, SQL or HTML source has crossed into a
  language whether or not it left the process — so ask of every string built
  with `f"..."` and then handed to something that EXECUTES it: what is the
  most hostile value the source of this string can produce?

## 3 · Architecture / product hygiene

- `single-source-of-truth` — **(legacy)** Single source of truth for catalogs/constants — don't re-home
  lists across web/API/ingest. *This is `one-catalog` stated twice, in two
  groups; that one has the scalps and the cross-language case
  (`pin-unremovable-duplicates`). Kept here as a pointer because the hygiene
  question belongs in an architecture review too — follow it there.*
- `docs-match-behaviour` — **(legacy)** Keep docs aligned with shipped behavior (SPECS / UserManual / OPERATIONS / DemoScript); no stale contradictions.
- `backlog-discipline` — **(legacy)** Backlog discipline: open in PRODUCT_BACKLOG; done → PRODUCT_ARCHIVE with date + evidence.
- `declared-vs-enforced` — **(+) Declared vs enforced.** Every control a config file or doc declares must have
  something that reads it. A declared-but-unenforced control is worse than an absent
  one: it reads as a control in an audit and is not one.
  **(++)** Includes controls whose enforcer is a HUMAN: an instruction filed
  where its audience never reads is not assigned to anyone.
- `provenance-and-precedence` — **(+) Provenance and precedence.** Where can this value come from, and when two
  sources disagree, which wins and is that written down? Distinguish a channel the
  operator *declared* from one that is merely *ambient*.
- `minimal-host-dependency` — **(+) Minimal host dependency.** What does this require of the machine beyond the
  package — a shell profile, a specific shell, a writable `$HOME`, an OS?
- `implemented-not-invoked` — **(++++) Implemented is not invoked. Ask "who calls this?" and grep.**
  The inverse of `declared-vs-enforced`: not a control that is declared and
  unenforced, but
  one that is fully BUILT and never reached. Correct code, correct tests,
  zero call sites. It is invisible precisely because everything you would
  inspect looks right, and a component that no-ops when uninstalled — the
  usual, correct choice for telemetry — cannot tell you it was never
  installed. The check costs one grep per public entry point, and it should
  run against the ENTRYPOINTS a deployment actually starts: the worker, the
  CLI, the container command.
- `two-owners-two-cadences` — **(++++) Two owners, two cadences.** For every interface, ask who ships each
  side and whether they can deploy independently. When the answer is yes —
  platform team and product team, IT and the business, framework and tenant —
  then a version lag is the DESIGN, not a defect, and three things must
  exist: a version on the wire, a written compatibility window, and consumers
  that read an unknown or absent field as "other version" rather than
  "fault". Pinning gives the downstream side a cadence of its own; it does
  not by itself tell the upstream side what it must keep accepting.

## 4 · Process (how work is done)

- `design-before-code` — **(legacy)** Brainstorm → design approve → spec → plan → build (no blind coding).
- `expect-re-review` — **(legacy)** After build, expect thorough re-review for repeats / gaps / redundancy (multi-pass if asked).
- `small-verified-slices` — **(legacy)** Ship small, testable slices; verify before claiming done.
- `review-the-branch` — **(+) Review the branch, not the diff.** Scope the pass by what the branch ships and
  what CI checks — `self-test.yml` is the definitive list — not by the files you edited.
- `grep-for-siblings` — **(+) When a fix lands, grep for the siblings.** A fix applied at one call site and
  not its identical neighbours is the most repeated defect in this codebase.
  **(++)** Follow the DATA, not the directory. The sibling that gets missed is
  the one in another package, another language, or another repo — searching
  where you are editing finds every copy except that one.
- `run-the-gates-ci-lists` — **(+) Run the gates locally before pushing** — and check the git state matches what
  CI will see, or the local run is not the same run.
  **(++++)** Run the ones CI LISTS, not the ones you remember. Enumerate the
  workflow's steps and work down them; a subset that passes is not a pass.

## 5 · Intuitive UI

- `intuitive-journey` — **(legacy)** UI stays intuitive on the user journey — product-shippable; no confusing auth-mode chrome; reuse normal SSO → work path.
- `failure-is-not-a-result` — **(+) An interface must not present a failure as a result.** Empty, zero and
  unavailable are three different things on a screen as much as in a metric.

## 6 · Signal integrity — does green mean green? **(+ new group)**

The group that produced the most findings, and the one the earlier list had no
lever for. Every item asks the same question from a different side: *if this
check did not actually run, would anything look different?*

- `ambiguous-signals` — **Ambiguous signals.** One value must not mean two things. `0.0`, `[]`, `None`, a
  skip — each is routinely used for both "measured, all good" and "never measured".
  Report the states separately and name them.
- `gate-integrity` — **Gate integrity.** Can this check fail? Does it verify its own output? Does a
  threshold still mean something after being moved?
- `failure-mode-visibility` — **Failure-mode visibility.** When this fails, will anyone know? Exit 0 plus a green
  check is how a gate stops grading and nobody notices.
- `test-the-contract` — **Test the contract, not the helper.** Assert over the artifact or the emitted
  signal, not over the function that produced it with the input you just handed it.
- `test-that-cannot-fail` — **A test that cannot fail is a finding.** Sweeps that match nothing, loops over empty
  collections, guards exempting themselves.
- `aggregates-name-their-scope` — **(++) An aggregate must name what it aggregated over.** A count, a rate, or a
  "nothing found" claim is only checkable if it states its scope — which
  project, how many rows, which window, and whether the source had more to
  give. This is not `ambiguous-signals`: the number is not ambiguous, it is
  unattributed,
  and a reader has no way to notice.
- `early-exit-keeps-the-record` — **(+++) An early exit must not take the bookkeeping with it.** When a
  function both RECORDS something and DECIDES something, every `raise`,
  `return` and `break` between the two skips the record. Ask of each one:
  what had this function already committed to that it is now not going to
  finish? Tripping, denying and rejecting are decisions about what happens
  NEXT — never grounds to un-record what already happened. The tell is a
  guard sitting textually between an append and an accrual.
- `check-that-fires-on-everything` — **(2026-08-28) A check that fires on almost everything is as broken as one
  that never fires.** `test-that-cannot-fail` covers the sweep that matches
  nothing. This is its
  twin, and it is the one that wastes a reviewer's afternoon: a query returning
  a result too large to match what the code obviously does is a broken query,
  not a discovery. Read the count before reading the hits — if a sweep says
  most of the codebase is defective, the sweep is the defect.
- `test-that-pins-a-defect` — **(2026-08-28) A test can pin a defect, and a confident docstring is what
  makes it survive.** `test-that-cannot-fail` is a test that cannot fail. This
  one can, and
  does, and asserts the wrong thing — so it defends the defect from the next
  reviewer. The tell is a test whose docstring justifies surprising behaviour
  by HISTORY rather than by a requirement: "preserves the previous
  normalization", "matches what the old script did". That sentence reads as
  due diligence and functions as a lock. When you meet one, ask what the
  behaviour SHOULD be, not what it has been — and check the docstring of the
  function under test, which in the worst case already promises the opposite.
