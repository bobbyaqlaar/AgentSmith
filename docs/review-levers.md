# Review levers

The checklist a review pass runs against. Groups 1–5 are the standing list.
Group 6 and the items marked **(+)** were added on 2026-08-24, each one traceable
to a defect that a pass using the earlier list did not catch — the provenance is
kept because a lever with no scalp is decoration.

---

## 1 · DRY & shared code

1. No redundant code, files, or docs at the end of a slice.
2. No copy-paste functions (even under other names / other files) — extract to a shared library.
3. Before writing a new function: search existing shared helpers first; reuse/extend.
4. Prefer one parameterized helper over near-duplicates (vary by args, not by cloning).
5. Clean up dead imports, unused exports, and obsolete docs/files when the slice finishes.
6. **(+) A catalog belongs to one module.** A list of valid suites, roles, event types or
   file names restated anywhere else is a second catalog that will drift.
   *Caught: `SCORECARDS` restating `_shared.RESULTS_FILE`; the `Role` union written
   three times; the audit event catalog in a union plus two arrays.*

## 2 · Quality / safety

1. Prefer standard, optimised, safe, secure library/APIs already in the repo — don't invent parallel paths.
2. Security/scope consistency matters: same gate pattern across mutating routes (no "forgot ActorDep / scope" holes).
3. Don't hide auth failures as "offline/mock" — network fallback only when appropriate.
4. **(+) Environment parity.** Does this behave the same on a developer machine, in
   CI, and in production? Name what differs — runtime, filesystem, clock, git state.
   *Caught: `node:crypto` passing `tsc` and `npm test` and failing only `next build`;
   `runtime/` never loading `.env`; a sweep whose coverage depended on whether its
   own file was committed yet; mtimes rewritten by `actions/checkout`.*
5. **(+) A guard must be able to fail.** Assertions inside the `try` they guard,
   conditions that can never be true, `except Exception` around the check itself.
   *Caught: `if span is None` on a value that is never None; F-scenario drivers
   raising `AssertionError` inside a caught block.*

## 3 · Architecture / product hygiene

1. Single source of truth for catalogs/constants (streams, function units, etc.) — don't re-home lists across web/API/ingest.
2. Keep docs aligned with shipped behavior (SPECS / UserManual / OPERATIONS / DemoScript); no stale contradictions.
3. Backlog discipline: open in PRODUCT_BACKLOG; done → PRODUCT_ARCHIVE with date + evidence.
4. **(+) Declared vs enforced.** Every control a config file or doc declares must have
   something that reads it. A declared-but-unenforced control is worse than an absent
   one: it reads as a control in an audit and is not one.
   *Caught: `budget.monthly_usd_cap: 5` declared while $150 was enforced;
   `tenant.id`, `workflow.task_queue`, `tenant.owner`, `workflow.engine`,
   `redaction_profile` all declared and unread; pillar 3's span contract.*
5. **(+) Provenance and precedence.** Where can this value come from, and when two
   sources disagree, which wins and is that written down? Distinguish a channel the
   operator *declared* from one that is merely *ambient*.
   *Caught: `.zshrc` silently outranking every tenant's `tenant.owner`; the tenant id
   in six places; two budget keys, one feeding the dashboard and one the enforcement.*
6. **(+) Minimal host dependency.** What does this require of the machine beyond the
   package — a shell profile, a specific shell, a writable `$HOME`, an OS?
   *Open: 15 zsh functions and ~61 lines in `~/.zshrc`, none testable, none portable.*

## 4 · Process (how work is done)

1. Brainstorm → design approve → spec → plan → build (no blind coding).
2. After build, expect thorough re-review for repeats / gaps / redundancy (multi-pass if asked).
3. Ship small, testable slices; verify before claiming done.
4. **(+) Review the branch, not the diff.** Scope the pass by what the branch ships and
   what CI checks — `self-test.yml` is the definitive list — not by the files you edited.
   *Caught: three review passes reporting clean while `main` had been red for three
   commits, all three failures outside the reviewed diff.*
5. **(+) When a fix lands, grep for the siblings.** A fix applied at one call site and
   not its identical neighbours is the most repeated defect in this codebase.
   *Caught: the TS loader on 2 of 3 invocations; `return 2` graceful-skip on 1 of 2;
   `is_recording()` correct in one function and absent in its sibling.*
6. **(+) Run the gates locally before pushing** — and check the git state matches what
   CI will see, or the local run is not the same run.

## 5 · Intuitive UI

1. UI stays intuitive on the user journey — product-shippable; no confusing auth-mode chrome; reuse normal SSO → work path.
2. **(+) An interface must not present a failure as a result.** Empty, zero and
   unavailable are three different things on a screen as much as in a metric.
   *Caught: a failed query rendering as "No shadow-eval failures in the last 24h".*

## 6 · Signal integrity — does green mean green? **(+ new group)**

The group that produced the most findings, and the one the earlier list had no
lever for. Every item asks the same question from a different side: *if this
check did not actually run, would anything look different?*

1. **Ambiguous signals.** One value must not mean two things. `0.0`, `[]`, `None`, a
   skip — each is routinely used for both "measured, all good" and "never measured".
   Report the states separately and name them.
   *Caught: a flagged-claim rate of `0.000` over zero cases; `passed: null` read as
   falsy-as-fail; `input_tokens=0` for "the provider reported none".*
2. **Gate integrity.** Can this check fail? Does it verify its own output? Does a
   threshold still mean something after being moved?
   *Caught: `--check-kg` regenerating the graph and then asserting things about the
   graph it had just written — green while the committed file was 703 lines stale.*
3. **Failure-mode visibility.** When this fails, will anyone know? Exit 0 plus a green
   check is how a gate stops grading and nobody notices.
   *Caught: judged suites reporting NO VERDICT and exiting 0 on every push; an ignored
   environment override; span attributes silently dropped onto a non-recording span.*
4. **Test the contract, not the helper.** Assert over the artifact or the emitted
   signal, not over the function that produced it with the input you just handed it.
   *Caught: `tenant.id == "acme"` asserted on a call that passed `tenant_id="acme"`,
   while most real spans carried no tenant at all.*
5. **A test that cannot fail is a finding.** Sweeps that match nothing, loops over empty
   collections, guards exempting themselves.
   *Caught: an import-graph walker that resolved zero files twice, both times passing.*
