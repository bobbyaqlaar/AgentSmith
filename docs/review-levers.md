# Review levers

The checklist a review pass runs against. Six groups; work down them.

Every item marked with a date or a `(+)` was added because a pass using the
earlier list missed something. **The evidence lives in
[`review-lever-scalps.md`](./review-lever-scalps.md)** — one entry per lever,
naming the defect that earned it. This file stays short so it can be used; that
one stays long so nothing here has to be taken on trust.

`(legacy)` marks the original standing list. Those are exempt from the evidence
requirement by design and are kept as a hygiene checklist — the things worth
confirming every pass whether or not a defect has been filed against any one of
them.

Marks record when an item arrived: `(+)` 2026-08-24, `(++)` and `(+++)`
2026-08-25, `(++++)` 2026-08-26, and dates thereafter. Amendments to an existing
item carry their own mark inline.

**Citing a lever from code?** Write the number AND a short name —
`review-levers 2.8: validation belongs on the receiving side`. Numbers shift
when an item is inserted; `scripts/test/test_lever_references.py` reads both
files and fails when a citation names a lever other than the one at that number.

---

## 1 · DRY & shared code

1. **(legacy)** No redundant code, files, or docs at the end of a slice — dead
   imports, unused exports and obsolete files included. *(Was two items, 1 and
   5, saying the same thing in the group about things that say the same thing.)*
2. **(legacy)** No copy-paste functions (even under other names / other files) — extract to a shared library.
3. **(legacy)** Before writing a new function: search existing shared helpers first; reuse/extend.
4. **(legacy)** Prefer one parameterized helper over near-duplicates (vary by args, not by cloning).
5. **(2026-08-28) One verdict, computed once.** A decision recomputed
   downstream, from different inputs than the one that made it, is right at
   both sites and wrong between them. Data duplication drifts loudly; a
   duplicated DECISION drifts silently, because each copy looks locally
   correct. Pass the verdict, never the ingredients to re-derive it.
6. **(+) A catalog belongs to one module.** A list of valid suites, roles, event types or
   file names restated anywhere else is a second catalog that will drift.
7. **(++) A duplicate that CANNOT be removed must be pinned.** Items 1–4 and 6
   all say "extract to one module", which is impossible across a language or system
   boundary — a TypeScript catalog and a SQL `CHECK`, a Python resolver and its
   TypeScript mirror, a client-side validation and its server. The lever gave
   advice that could not be followed, so those cases fell straight through it.
   The substitute is a test that PARSES the other side rather than restating it,
   because a test that hardcodes the second copy is just a third copy.
8. **(++++) When you merge N copies, find the one that is already right — and
   expect the merged version to face inputs none of them did.** Two halves.
   First: several implementations of one rule usually include a correct one,
   and writing a fresh N+1 discards whatever it learned. Read them all, pick
   the survivor, and say why in the module that keeps it. Second: extraction
   is not relocation. Each copy was correct for the narrow domain its own
   caller fed it, and the merged one is reachable from every caller at once,
   so cases that were unreachable per-copy become live on the first day.

## 2 · Quality / safety

1. **(legacy)** Prefer standard, optimised, safe, secure library/APIs already in the repo — don't invent parallel paths.
2. **(legacy)** Security/scope consistency matters: same gate pattern across mutating routes (no "forgot ActorDep / scope" holes).
3. **(legacy)** Don't hide auth failures as "offline/mock" — network fallback only when appropriate.
4. **(+) Environment parity.** Does this behave the same on a developer machine, in
   CI, and in production? Name what differs — runtime, filesystem, clock, git state.
   **(++)** The second environment is often INSIDE the app: server component vs
   client component, worker vs request, build vs run. Same question, same clock.
5. **(+) A guard must be able to fail.** Assertions inside the `try` they guard,
   conditions that can never be true, `except Exception` around the check itself.
   **(++)** And a guard that CAN fail can still be too weak to hold: ask what
   the check would let through, not only whether it runs.
   **(2026-08-28)** And write the guard so a type checker can follow it, because
   a reader follows the same path. Narrowing that goes through an intermediate
   boolean, or that happens in a different method from the use, is narrowing
   only a human who already knows the code can see.
6. **(++) Out-of-order and repeated messages.** Every best-effort POST, retry,
   heartbeat and at-least-once queue means two writes can arrive in the other
   order, or twice. Ask it of each one: what does the row look like then? An
   upsert is where this lands, and a guard applied to four columns and not the
   fifth is the usual shape.
7. **(2026-08-28) Ask what happens when the FALLBACK fails.** Every recovery
   ladder — retry, then auto-correct, then park it for a human — is reviewed at
   the rungs and not at the joints. The question is not "does step B work" but
   "when step B FAILS, does control reach step C, or does B's failure escape the
   ladder entirely?" A recovery step that raises is the case nobody writes a
   test for, because the step exists to handle failure and is not imagined as a
   source of it.
8. **(++) Validation belongs on the receiving side of a trust boundary.** A
   check the caller performs is a courtesy; the same check where the value is
   accepted is a control. Finding the rule already implemented on the wrong side
   is the tell — it means someone knew, and put it where it does not bind.
   **(+++)** The receiving side is often an INTERPRETER, not a network peer.
   Text spliced into shell, AppleScript, SQL or HTML source has crossed into a
   language whether or not it left the process — so ask of every string built
   with `f"..."` and then handed to something that EXECUTES it: what is the
   most hostile value the source of this string can produce?

## 3 · Architecture / product hygiene

1. **(legacy)** Single source of truth for catalogs/constants — don't re-home
   lists across web/API/ingest. *This is lever **1.6** stated twice, in two
   groups; 1.6 is the version with scalps and with the cross-language case
   (1.7). Kept here as a pointer because the hygiene question belongs in an
   architecture review too — follow it there.*
2. **(legacy)** Keep docs aligned with shipped behavior (SPECS / UserManual / OPERATIONS / DemoScript); no stale contradictions.
3. **(legacy)** Backlog discipline: open in PRODUCT_BACKLOG; done → PRODUCT_ARCHIVE with date + evidence.
4. **(+) Declared vs enforced.** Every control a config file or doc declares must have
   something that reads it. A declared-but-unenforced control is worse than an absent
   one: it reads as a control in an audit and is not one.
   **(++)** Includes controls whose enforcer is a HUMAN: an instruction filed
   where its audience never reads is not assigned to anyone.
5. **(+) Provenance and precedence.** Where can this value come from, and when two
   sources disagree, which wins and is that written down? Distinguish a channel the
   operator *declared* from one that is merely *ambient*.
6. **(+) Minimal host dependency.** What does this require of the machine beyond the
   package — a shell profile, a specific shell, a writable `$HOME`, an OS?
7. **(++++) Implemented is not invoked. Ask "who calls this?" and grep.**
   The inverse of item 4: not a control that is declared and unenforced, but
   one that is fully BUILT and never reached. Correct code, correct tests,
   zero call sites. It is invisible precisely because everything you would
   inspect looks right, and a component that no-ops when uninstalled — the
   usual, correct choice for telemetry — cannot tell you it was never
   installed. The check costs one grep per public entry point, and it should
   run against the ENTRYPOINTS a deployment actually starts: the worker, the
   CLI, the container command.
8. **(++++) Two owners, two cadences.** For every interface, ask who ships each
   side and whether they can deploy independently. When the answer is yes —
   platform team and product team, IT and the business, framework and tenant —
   then a version lag is the DESIGN, not a defect, and three things must
   exist: a version on the wire, a written compatibility window, and consumers
   that read an unknown or absent field as "other version" rather than
   "fault". Pinning gives the downstream side a cadence of its own; it does
   not by itself tell the upstream side what it must keep accepting.

## 4 · Process (how work is done)

1. **(legacy)** Brainstorm → design approve → spec → plan → build (no blind coding).
2. **(legacy)** After build, expect thorough re-review for repeats / gaps / redundancy (multi-pass if asked).
3. **(legacy)** Ship small, testable slices; verify before claiming done.
4. **(+) Review the branch, not the diff.** Scope the pass by what the branch ships and
   what CI checks — `self-test.yml` is the definitive list — not by the files you edited.
5. **(+) When a fix lands, grep for the siblings.** A fix applied at one call site and
   not its identical neighbours is the most repeated defect in this codebase.
   **(++)** Follow the DATA, not the directory. The sibling that gets missed is
   the one in another package, another language, or another repo — searching
   where you are editing finds every copy except that one.
6. **(+) Run the gates locally before pushing** — and check the git state matches what
   CI will see, or the local run is not the same run.
   **(++++)** Run the ones CI LISTS, not the ones you remember. Enumerate the
   workflow's steps and work down them; a subset that passes is not a pass.

## 5 · Intuitive UI

1. **(legacy)** UI stays intuitive on the user journey — product-shippable; no confusing auth-mode chrome; reuse normal SSO → work path.
2. **(+) An interface must not present a failure as a result.** Empty, zero and
   unavailable are three different things on a screen as much as in a metric.

## 6 · Signal integrity — does green mean green? **(+ new group)**

The group that produced the most findings, and the one the earlier list had no
lever for. Every item asks the same question from a different side: *if this
check did not actually run, would anything look different?*

1. **Ambiguous signals.** One value must not mean two things. `0.0`, `[]`, `None`, a
   skip — each is routinely used for both "measured, all good" and "never measured".
   Report the states separately and name them.
2. **Gate integrity.** Can this check fail? Does it verify its own output? Does a
   threshold still mean something after being moved?
3. **Failure-mode visibility.** When this fails, will anyone know? Exit 0 plus a green
   check is how a gate stops grading and nobody notices.
4. **Test the contract, not the helper.** Assert over the artifact or the emitted
   signal, not over the function that produced it with the input you just handed it.
5. **A test that cannot fail is a finding.** Sweeps that match nothing, loops over empty
   collections, guards exempting themselves.
6. **(++) An aggregate must name what it aggregated over.** A count, a rate, or a
   "nothing found" claim is only checkable if it states its scope — which
   project, how many rows, which window, and whether the source had more to
   give. This is not item 1: the number is not ambiguous, it is unattributed,
   and a reader has no way to notice.
7. **(+++) An early exit must not take the bookkeeping with it.** When a
   function both RECORDS something and DECIDES something, every `raise`,
   `return` and `break` between the two skips the record. Ask of each one:
   what had this function already committed to that it is now not going to
   finish? Tripping, denying and rejecting are decisions about what happens
   NEXT — never grounds to un-record what already happened. The tell is a
   guard sitting textually between an append and an accrual.
8. **(2026-08-28) A check that fires on almost everything is as broken as one
   that never fires.** Item 5 covers the sweep that matches nothing. This is its
   twin, and it is the one that wastes a reviewer's afternoon: a query returning
   a result too large to match what the code obviously does is a broken query,
   not a discovery. Read the count before reading the hits — if a sweep says
   most of the codebase is defective, the sweep is the defect.
9. **(2026-08-28) A test can pin a defect, and a confident docstring is what
   makes it survive.** Item 5 is a test that cannot fail. This one can, and
   does, and asserts the wrong thing — so it defends the defect from the next
   reviewer. The tell is a test whose docstring justifies surprising behaviour
   by HISTORY rather than by a requirement: "preserves the previous
   normalization", "matches what the old script did". That sentence reads as
   due diligence and functions as a lock. When you meet one, ask what the
   behaviour SHOULD be, not what it has been — and check the docstring of the
   function under test, which in the worst case already promises the opposite.
