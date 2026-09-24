# Design review checklist — build it right the first time

**Phase:** design and build. Read this *before* writing a line of the change,
and keep it open while you write it. Its post-build counterpart is
[`validation-checklist.md`](./validation-checklist.md) — that one asks "did
you get this right"; this one is what you consult so the answer already is
yes.

## What this is, in industry terms

Most engineering orgs keep two artifacts around a change: a **Definition of
Ready** / design-review checklist consulted going in, and a **Definition of
Done** / code-review checklist consulted coming out. This is AgentSmith's
version of the first one. It is not generic — every line traces to a lever in
[`review-levers.md`](./review-levers.md), and every lever there traces to a
defect that actually shipped (`(legacy)` items excepted, and the small number
marked `(unevidenced)`, which are named as such rather than dressed up as
proven). Reframing "did you avoid X" as "here is how you avoid X" is the only
new content here — the RULE lives in one place.

## How to use it

1. Skim the group headers below before starting. They mirror
   `review-levers.md`'s groups exactly, so a lever you already know by
   slug is easy to find.
2. While designing, work the groups that bear on what you're building — Group
   5 for anything with a screen, Group 2 and 6 for anything that writes data
   or reports a result, Group 7 for anything with a cookie or bearer session,
   Group 1 and 3 before you create a new file or a new abstraction.
3. This is a design aid, not a gate. The gate is
   [`validation-checklist.md`](./validation-checklist.md) and the CI run —
   this document exists so fewer findings reach that stage in the first
   place.
4. If a lever here does not fit the change you're making, skip it — the cost
   of over-applying a checklist is a worse habit than the defect it prevents.

---

## Group 1 · DRY & shared code — before you create anything

- **`no-redundant-artifacts`** — Plan the slice's END STATE, including what
  becomes dead: an import, an export, a doc paragraph a fix makes stale. Dead
  weight is easiest to see at design time, before it's buried in a diff.
- **`no-copy-paste`** — If the mental draft of this change starts "copy
  function X, rename it, tweak it" — stop. That is the design for a helper
  with a parameter, not a second function.
- **`search-before-writing`** — Before sketching a new function, grep for
  its shape. Five minutes of search beats a five-line duplicate nobody
  notices until it drifts.
- **`parameterize-dont-clone`** — If two near-identical helpers seem needed,
  design one parameterised helper up front. Writing both first and merging
  later is strictly more work — and see `merge-the-right-copy` below for why
  the merge itself is not mechanical.
- **`one-verdict`** — Decide, at design time, WHERE the pass/fail decision
  for this change gets computed. Every other site — a notifier, a log line, a
  UI badge — must read that decision, never re-derive it from the same
  ingredients. Two computations of one verdict are two chances to disagree.
- **`one-catalog`** — A new constant, enum, or lookup table gets ONE home,
  decided before the first call site is written. Deciding this after three
  call sites exist means picking which two must be migrated.
- **`every-line-earns-its-place`** — Decide what the change looks like when it
  is FINISHED, not when it first works. A wrapper with one caller, a comment
  restating the line under it, a branch no input reaches, a docstring longer
  than the code it describes: each is cheap to write and permanent to read.
  When a change unifies duplicated logic, the shims and the prose about the old
  duplication are part of what it removes, or the duplication just moves. The
  counterweight is not negotiable: shorter, never denser — a comment recording
  WHY is load-bearing, and golfing a loop into an unreadable expression moves
  the cost to every future reader instead of paying it once here.
- **`pin-unremovable-duplicates`** — If a duplicate genuinely cannot be
  removed (two runtimes, a vendored bundle, an air-gapped copy), design the
  drift test alongside the duplicate, in the same change — not as a follow-up
  that never lands. It must PARSE the other side, not hand-compare strings.
- **`merge-the-right-copy`** — When a design calls for merging N existing
  implementations into one: read all N before writing the merged version.
  The survivor is usually one of them, already correct for cases the others
  never saw — and the merged version will face inputs none of the N ever
  faced alone, because it's now reachable from every caller at once.

## Group 2 · Quality / safety — while you're writing the logic

- **`use-existing-apis`** — Default to the repo's existing safe path (the
  gateway, the guard, the redactor). A parallel path is a second place every
  future safety fix has to remember to touch.
- **`consistent-auth-gates`** — Every mutating route gets the SAME auth and
  scope check as its siblings, decided as one rule, not copied per-route from
  whichever one was closest.
- **`no-fake-offline-fallback`** — Design the failure path for "the
  auth/credential check itself failed" explicitly. It must read as a failure,
  never as a silent "offline" or "mock" mode a caller can't distinguish from
  the real thing being unavailable by design.
- **`environment-parity`** — Before branching on `ENVIRONMENT` or a
  dev/prod flag, ask whether the branch is necessary at all. A behaviour that
  differs between a dev machine, CI and production is a behaviour that gets
  tested somewhere it doesn't run.
- **`guards-must-be-able-to-fail`** — For every guard you design, write down
  what it lets through when it itself fails to evaluate — not just when it
  evaluates false. If a type checker cannot follow the guard's return type
  to the narrowed branch, redesign it so it can.
- **`out-of-order-and-repeated`** — For every write, design for its message
  or request arriving twice, or arriving out of order. Idempotency keys and
  ordering checks are cheap at design time and expensive to retrofit onto a
  live table.
- **`when-the-fallback-fails`** — Recovery is a ladder (retry → repair →
  human). Design each rung's OWN failure path before writing the rung — a
  repair step that can itself fail and has no plan for that is not a rung,
  it's a trapdoor.
- **`validate-on-the-receiving-side`** — Decide, at design time, where a
  value is validated: the point where it is ACCEPTED, including any
  interpreter it is about to enter (a shell, a query, a template). Validating
  only at the point of origin misses every other path the value can arrive
  by.

## Group 3 · Architecture / product hygiene — the shape of the change

- **`single-source-of-truth`** — Same discipline as `one-catalog`, asked one
  level up: does this change introduce a SECOND home for a concept that
  already has one? If yes, the design is a migration, not an addition.
- **`docs-match-behaviour`** — If this change alters documented behaviour,
  the doc update is part of the design, not a follow-up ticket. Decide which
  paragraph changes before you write the code that makes it stale.
- **`backlog-discipline`** — A design that defers part of the work should
  name that part explicitly, with a trigger for when it gets picked up — not
  leave it implicit for a future reader to rediscover.
- **`declared-vs-enforced`** — For every control this design introduces or
  touches (a policy, a threshold, a permission), design what actually READS
  it. A control nothing enforces is a comment with a name.
- **`provenance-and-precedence`** — Whenever a value can come from more than
  one source (env var, config file, CLI flag, a default), decide and write
  down the precedence BEFORE implementing — not as an emergent property of
  which `if` happens to run first.
- **`minimal-host-dependency`** — Ask what this design requires of the
  machine beyond the package itself: a binary on PATH, a specific OS, a
  writable path outside the repo. Each one is a thing that works on your
  machine and nowhere else until proven otherwise.
- **`implemented-not-invoked`** — Before calling a design element "done,"
  identify WHO calls it — the actual entrypoints a real deployment starts,
  not a test harness that constructs it directly. A module with no caller in
  any real entrypoint is not shipped, whatever its test coverage says.
- **`two-owners-two-cadences`** — If this design crosses a boundary that two
  teams or two repos ship independently across, it needs a version on the
  wire and a written compatibility window — decided now, because "we'll keep
  them in sync" is not a design, it's a hope.

## Group 4 · Process — how the work itself gets done

- **`design-before-code`** — This document is that discipline made concrete:
  brainstorm → design → spec → plan → build. If you're reading this while
  code is already half-written, finish the design retroactively before
  writing more — better late than never, worse than on time.
- **`expect-re-review`** — Design for a second pass to exist. Leave the
  change in a state where a re-reviewer can tell what you were trying to do,
  not only what you did.
- **`small-verified-slices`** — Scope the design to a slice that can be
  shipped and verified on its own. A design that can't be checked until every
  part lands is a design that hides its own defects until the end.
- **`review-the-branch`** — Scope the change by what the branch will ship
  and what CI will check, not by the files that happen to be open. Design the
  diff's boundary around the feature, not the editor state.
- **`grep-for-siblings`** — If this design fixes or changes a pattern that
  exists more than once, plan the sibling search as part of the design —
  across languages and repos, not just the directory you're already in.
- **`run-the-gates-ci-lists`** — Know, before you start, which gates
  `self-test.yml` (or the tenant's own CI file) will run against this change.
  Design against the real list, not the subset you remember.

## Group 5 · Intuitive UI — building the screen

This is the newest group and the one with the most levers, because a screen
fails in more distinct ways than a backend call does — and because it's the
one about to get real, first-time exercise on the Ops Portal's HITL
approve/reject build. Walk these in order as you design a screen or a control
on one.

- **`intuitive-journey`** — Design the journey a user actually takes, start
  to finish, before designing any one screen in it. No auth-mode chrome —
  a control that only appears to prove a permission system exists is not part
  of the product journey.
- **`failure-is-not-a-result`** — For every place this screen can show
  nothing, decide up front which of three it is — empty (queried, genuinely
  none), unavailable (couldn't check), or zero (checked, the count is zero)
  — and design three different renderings. One "No results" string covering
  all three is a design decision to hide which one happened.
- **`irreversible-needs-confirmation`** — Before wiring a control that
  fires a one-way action — discard, reject, revoke — design its confirmation
  step in the same pass as the control itself, not as a later polish item.
- **`no-double-submit`** — Design every write-triggering control's DISABLED
  state before its enabled one. Between click and response is exactly the
  window `out-of-order-and-repeated` (Group 2) warns about, manufactured by
  the UI itself if you don't.
- **`denied-vs-missing`** — For every screen behind a permission check,
  design the "not authorized" rendering as a DIFFERENT screen from "not
  found," before you build either. They point an operator at opposite next
  actions.
- **`stale-data-is-labelled`** — Any number this screen shows that someone
  could act on (a cost, a cap, a count) carries a "measured at" alongside it
  in the design, not bolted on once someone asks why a decision was made on
  an hour-old figure.
- **`keyboard-and-screen-reader-operable`** — Design every control's
  keyboard path and its accessible name at the same time as its click
  handler — an icon-only button designed without a label is a button
  half-designed, whatever it looks like.
- **`works-at-real-viewport-sizes`** — Design against the viewport sizes
  this screen's actual users run, not a full-width canvas. A control that
  only works at 1440px wide was designed for a monitor, not an operator.
- **`matches-the-existing-component-language`** — Before inventing a new
  spacing value, colour, or component for this screen, check what the rest
  of the app already uses for the same purpose. A new pattern here is a
  second definition of "what a button looks like" — see `one-catalog` above,
  applied to pixels instead of code.

## Group 6 · Signal integrity — before you decide what "done" reports

- **`ambiguous-signals`** — For every value this change can return or print,
  design what it means when the check DIDN'T run, and make sure that's
  distinguishable from "ran, and the answer was clean." A `0.0` or an empty
  list covering both is a false green waiting for its first real quiet
  failure.
- **`gate-integrity`** — For every check this design adds, ask whether it
  CAN fail, on paper, before you write it. A check with no reachable failure
  path is decoration, not a gate.
- **`failure-mode-visibility`** — For every failure this design can produce,
  design who finds out and how — a log line nobody reads is a failure mode
  with no visibility, whatever the code technically does.
- **`test-the-contract`** — Design the test for this change against the
  ARTIFACT it produces (the file written, the row stored, the response
  sent) — not against the helper function you're about to feed it, which
  proves only that the helper does what you just told it to.
- **`test-that-cannot-fail`** — When designing a sweep, a loop, or a guard
  that checks "for every X, Y holds," design a test that FORCES a violating X
  to exist — a check that only ever runs over an empty or self-exempting
  collection has never actually been exercised.
- **`aggregates-name-their-scope`** — Any count, rate, or "nothing found"
  this design produces states what it covered — a scope, a time window, a
  page — in the same design as the number itself.
- **`early-exit-keeps-the-record`** — For every early return or raise
  between "recording" and "deciding," design what the record looks like if
  the deciding step never runs. A skipped decision must not also skip the
  bookkeeping that was supposed to survive it.
- **`check-that-fires-on-everything`** — If a check's match set could be
  "almost everything," design a sanity bound on its own result size — a
  query broad enough to match nearly the whole repo is a broken filter
  wearing the shape of a finding.
- **`test-that-pins-a-defect`** — If you're about to write a test whose
  justification is "this is how it's always behaved" rather than a stated
  requirement, design the requirement first. A test with no requirement
  behind it locks in whatever the code currently does, defect included.
- **`fixture-truth`** — Before writing a "not mock" assertion, check whether
  the real seed data or a shared fixture uses the same string you're about to
  forbid. Design the assertion around a positive signal — a uniquely created
  name, an auth header, the signed-in chrome — not the absence of a string
  that a correct page and an empty one can both satisfy.

## Group 7 · Auth & session integrity — any cookie, bearer, or dual client/server session

Skip this group if the slice has no auth. Walk it before writing the first
line that touches a token, a cookie, or a session check.

- **`channel-precedence`** — Before writing the first auth check, list every
  identity channel this slice can see — storage, httpOnly cookie, demo
  header, a forwarded internal header — and decide which one wins when two
  disagree. Deciding this after the code exists means reverse-engineering the
  precedence from whichever `if` happened to run first.
- **`untrusted-headers-are-not-a-session`** — If this design forwards an
  internal header for same-request server-to-server use, design where it gets
  stripped BEFORE writing where it gets set. A header a client can set is not
  a session, however it is used internally.
- **`same-request-cookie-invisibility`** — If a later step in this same
  request needs a cookie this request is about to set, design that value as
  an explicit forward, not a re-read through `cookies()` — a `Set-Cookie` in
  this response is not visible to this render.
- **`in-flight-must-not-undo-logout`** — For every logout or navigation call
  that races an in-flight refresh or fetch, design the ordering guarantee
  (keepalive, await, or a generation/cancelled flag) in the same change as
  the call itself — not after a late response is observed reviving a session.
- **`retry-bounds`** — Design the refresh-and-retry path with an explicit
  bound (at most one retry) and an explicit failure branch that clears the
  session — before writing the happy path, so "then what" already has an
  answer.

---

## Keeping this in step with `review-levers.md`

Every lever added to `review-levers.md` needs its design-phase counterpart
added here in the same change — `scripts/test/test_design_and_validation_docs.py`
checks that every non-legacy slug appears in this file, the same discipline
`scripts/test/test_lever_notes.py` already holds `review-lever-notes.md` to.
Adding a lever without a design-phase reframe here is exactly the
`no-redundant-artifacts` / `declared-vs-enforced` failure this checklist
exists to prevent, aimed at itself.
