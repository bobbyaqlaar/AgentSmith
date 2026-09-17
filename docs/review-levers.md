# Review levers

The checklist a review pass works down. **The slug is the identifier** — order is
for reading, so levers can be reordered or regrouped without breaking a citation.

Why each one exists, and the defect it caught:
[`review-lever-notes.md`](./review-lever-notes.md). `(legacy)` marks the original
standing list — kept for hygiene, exempt from needing evidence. Other marks date
an item's arrival. `(unevidenced)` marks a lever added ahead of a caught
defect, on purpose — unlike `(legacy)` it still needs a note saying why, and it
drops the mark the day it catches something. Cite one from code as
`review-levers: grep-for-siblings`.

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
- `run-the-gates-ci-lists` — **(+)** Run the gates CI lists, not the ones you remember, against the state CI will see. `agentsmith gates run` reads them from the workflow and says which ones could not run here.

## 5 · Intuitive UI

- `intuitive-journey` — **(legacy)** The journey stays intuitive and product-shippable; no auth-mode chrome.
- `failure-is-not-a-result` — **(+)** Empty, zero and unavailable are three different things on a screen.
- `irreversible-needs-confirmation` — **(2026-09-11, unevidenced)** An action that cannot be undone — discard, reject, revoke — says so before it fires, not after.
- `no-double-submit` — **(2026-09-11, unevidenced)** A control that triggers a write is disabled, or its effect is idempotent, between click and response.
- `denied-vs-missing` — **(2026-09-11, unevidenced)** "You cannot see this" and "this does not exist" are different screens.
- `stale-data-is-labelled` — **(2026-09-11, unevidenced)** A number an operator could act on states when it was last measured.
- `keyboard-and-screen-reader-operable` — **(2026-09-11, unevidenced)** Every control reachable and usable without a mouse, and every icon-only control carries a label something can read aloud.
- `works-at-real-viewport-sizes` — **(2026-09-11, unevidenced)** No control clipped, overlapped or scroll-trapped at the sizes this screen's actual users run.
- `matches-the-existing-component-language` — **(2026-09-11, unevidenced)** A new screen reuses this app's existing spacing, type and components rather than inventing a one-off pattern.

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
- `fixture-truth` — **(2026-09-12, from AqlaarTeleologyStudio)** Do not prove "not mock" by forbidding strings that real seed or shared fixtures also use — assert a unique created name, an auth header, or the signed-in chrome.

## 7 · Auth & session integrity **(+ new group, 2026-09-12, from AqlaarTeleologyStudio)**

For any cookie, bearer, or dual client/server session. Skip if the slice has no auth.

- `channel-precedence` — List every identity channel (storage, httpOnly cookie, demo headers, forwarded internal headers). Which wins, and can a weaker channel impersonate a stronger one? Write it down if two exist.
- `untrusted-headers-are-not-a-session` — Anything the browser can set is not equivalent to an httpOnly cookie. Internal headers used for same-request forwarding must be stripped on every continue path and set only after a successful server-side exchange.
- `same-request-cookie-invisibility` — `Set-Cookie` in middleware or a route is not visible to `cookies()` / the app server in that same render. If a later step in the same request must see the new value, forward it explicitly.
- `in-flight-must-not-undo-logout` — Cookie-clear and token refresh racing navigation or sign-out must not restore a session the user just ended. Use keepalive, await, or a generation/cancelled flag.
- `retry-bounds` — At most one refresh-and-retry on 401. No retry storm. A failed refresh clears the session; do not treat 401 as offline (`no-fake-offline-fallback`).
