# Review levers

The checklist a review pass works down. **The slug is the identifier** — order is
for reading, so levers can be reordered or regrouped without breaking a citation.

Why each one exists, and the defect it caught:
[`review-lever-notes.md`](./review-lever-notes.md). `(legacy)` marks the original
standing list — kept for hygiene, exempt from needing evidence. Other marks date
an item's arrival. Cite one from code as `review-levers: grep-for-siblings`.

---

## 1 · DRY & shared code

- `no-redundant-artifacts` — **(legacy)** No redundant code, files or docs at the end of a slice — dead imports and unused exports included.
- `no-copy-paste` — **(legacy)** No copy-paste functions, even renamed or in another file.
- `search-before-writing` — **(legacy)** Search existing helpers before writing a new function.
- `parameterize-dont-clone` — **(legacy)** One parameterised helper, not near-duplicates.
- `one-verdict` — **(2026-08-28)** Pass the verdict, never the ingredients to re-derive it.
- `one-catalog` — **(+)** A catalog belongs to one module; a second copy will drift.
- `pin-unremovable-duplicates` — **(++)** A duplicate you cannot remove must be pinned by a test that PARSES the other side.
- `merge-the-right-copy` — **(++++)** Merging N copies: keep the one already correct, and expect inputs none of them saw alone.

## 2 · Quality / safety

- `use-existing-apis` — **(legacy)** Prefer the repo's existing safe APIs; don't invent a parallel path.
- `consistent-auth-gates` — **(legacy)** The same auth and scope gate on every mutating route.
- `no-fake-offline-fallback` — **(legacy)** Don't hide an auth failure as "offline" or "mock".
- `environment-parity` — **(+)** Same behaviour on a dev machine, in CI, in production — and across boundaries inside the app.
- `guards-must-be-able-to-fail` — **(+)** Can this guard fail? What would it let through? Can a type checker follow it?
- `out-of-order-and-repeated` — **(++)** Two writes can arrive twice, or reversed. What does the row look like then?
- `when-the-fallback-fails` — **(2026-08-28)** When the recovery step itself fails, does control still reach the next rung?
- `validate-on-the-receiving-side` — **(++)** Validate where the value is ACCEPTED — including where it enters an interpreter.

## 3 · Architecture / product hygiene

- `single-source-of-truth` — **(legacy)** One home for catalogs and constants. Same lever as `one-catalog`, asked in an architecture review.
- `docs-match-behaviour` — **(legacy)** Docs match shipped behaviour; no stale contradictions.
- `backlog-discipline` — **(legacy)** Open in the backlog, done in the archive, with a date and evidence.
- `declared-vs-enforced` — **(+)** Every declared control needs something that reads it — including when the enforcer is a human.
- `provenance-and-precedence` — **(+)** Where can this value come from, and which source wins when two disagree?
- `minimal-host-dependency` — **(+)** What does this require of the machine beyond the package?
- `implemented-not-invoked` — **(++++)** Who calls this? Grep the entrypoints a deployment actually starts.
- `two-owners-two-cadences` — **(++++)** If both sides ship independently, the wire needs a version and a written compatibility window.

## 4 · Process (how work is done)

- `design-before-code` — **(legacy)** Brainstorm → design → spec → plan → build. No blind coding.
- `expect-re-review` — **(legacy)** Expect a thorough re-review after build; multi-pass if asked.
- `small-verified-slices` — **(legacy)** Ship small, testable slices. Verify before claiming done.
- `review-the-branch` — **(+)** Scope the pass by what the branch ships and what CI checks, not by the files you edited.
- `grep-for-siblings` — **(+)** When a fix lands, grep for its siblings — following the DATA, not the directory.
- `run-the-gates-ci-lists` — **(+)** Run the gates CI lists, not the ones you remember, against the state CI will see.

## 5 · Intuitive UI

- `intuitive-journey` — **(legacy)** The journey stays intuitive and product-shippable; no auth-mode chrome.
- `failure-is-not-a-result` — **(+)** Empty, zero and unavailable are three different things on a screen.

## 6 · Signal integrity — does green mean green? **(+ new group)**

- `ambiguous-signals` — One value must not mean two things. Name "measured zero" and "never measured" apart.
- `gate-integrity` — Can this check fail? Does it verify its own output?
- `failure-mode-visibility` — When this fails, will anyone know?
- `test-the-contract` — Assert on the emitted artifact, not on the helper you just fed.
- `test-that-cannot-fail` — A sweep matching nothing, a loop over an empty collection, a guard exempting itself.
- `aggregates-name-their-scope` — **(++)** A count, a rate or a "nothing found" must state what it covered.
- `early-exit-keeps-the-record` — **(+++)** A raise or return between recording and deciding skips the record.
- `check-that-fires-on-everything` — **(2026-08-28)** A result too large to match the code is a broken query, not a discovery.
- `test-that-pins-a-defect` — **(2026-08-28)** A docstring justifying behaviour by history rather than a requirement is a lock, not diligence.
