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
- `every-line-earns-its-place` — **(2026-09-24)** Read the diff as an expert would: a wrapper with one caller, a comment restating the line under it, a branch no input reaches, a docstring longer than the code. Delete rather than explain — but shorter, never denser: a line removed must not move its cost into the reader.

## 2 · Quality / safety

- `use-existing-apis` — **(legacy)** Prefer the repo's existing safe APIs; don't invent a parallel path.
- `consistent-auth-gates` — **(legacy)** The same auth and scope gate on every mutating route.
- `no-fake-offline-fallback` — **(legacy)** Don't hide an auth failure as "offline" or "mock".
- `environment-parity` — **(+)** Same behaviour on a dev machine, in CI, in production — and across boundaries inside the app.
- `guards-must-be-able-to-fail` — **(+)** Can this guard fail? What would it let through? Can a type checker follow it?
- `out-of-order-and-repeated` — **(++)** Two writes can arrive twice, or reversed. What does the row look like then?
- `when-the-fallback-fails` — **(2026-08-28)** When the recovery step itself fails, does control still reach the next rung?
- `validate-on-the-receiving-side` — **(++)** Validate where the value is ACCEPTED — including where it enters an interpreter.
- `commit-before-side-effect` — **(2026-11-19, unevidenced)** Save, confirm the save, then act: the response, the mail, the file and the one-time password all come after the commit.
- `lock-what-you-decide-on` — **(2026-11-19, unevidenced)** A record edited while something decides on it needs a lock or a version check, or the decision is recorded against a different state.
- `partial-is-not-complete` — **(2026-11-19, unevidenced)** A dependency that answers for some items yields partial or failed, never complete. Design the threshold, not only all-or-nothing.
- `outage-is-not-a-finding` — **(2026-11-19, unevidenced)** A check that could not run is never recorded as that check's result. "Could not determine" has its own value.
- `identity-not-label` — **(2026-11-19, unevidenced)** A property earned by a specific thing binds to its identity (digest, version, id), never to the name of the slot it sits in.

## 3 · Architecture / product hygiene

- `single-source-of-truth` — **(legacy)** One home for catalogs and constants. Same lever as `one-catalog`, asked in an architecture review.
- `docs-match-behaviour` — **(legacy)** Docs match shipped behaviour; no stale contradictions.
- `backlog-discipline` — **(legacy)** Open in the backlog, done in the archive, with a date and evidence.
- `declared-vs-enforced` — **(+)** Every declared control needs something that reads it — including when the enforcer is a human.
- `provenance-and-precedence` — **(+)** Where can this value come from, and which source wins when two disagree?
- `minimal-host-dependency` — **(+)** What does this require of the machine beyond the package?
- `implemented-not-invoked` — **(++++)** Who calls this? Grep the entrypoints a deployment actually starts.
- `two-owners-two-cadences` — **(++++)** If both sides ship independently, the wire needs a version and a written compatibility window.
- `runnable-docs` — **(2026-11-19, unevidenced)** Every command a document gives runs as printed, on a clean machine: no placeholder that stays a placeholder, and no step that needs a file the reader does not have.
- `move-and-restore-are-features` — **(2026-11-19, unevidenced)** Backup, restore and moving to another machine are paths the design covers. A restore brings back permissions, keys and the audit chain.

## 4 · Process (how work is done)

- `design-before-code` — **(legacy)** Brainstorm → design → spec → plan → build. No blind coding.
- `expect-re-review` — **(legacy)** Expect a thorough re-review after build; multi-pass if asked.
- `small-verified-slices` — **(legacy)** Ship small, testable slices. Verify before claiming done.
- `review-the-branch` — **(+)** Scope the pass by what the branch ships and what CI checks, not by the files you edited.
- `grep-for-siblings` — **(+)** When a fix lands, grep for its siblings — following the DATA, not the directory.
- `run-the-gates-ci-lists` — **(+)** Run the gates CI lists, not the ones you remember, against the state CI will see. `agentsmith gates run` reads them from the workflow and says which ones could not run here.
- `fix-the-class-not-the-case` — **(2026-11-19, unevidenced)** A reported defect is one instance of a kind. Name the kind, list the other routes to the same fault, and say in words what the fix does not cover.
- `prove-it-fails-first` — **(2026-11-19, unevidenced)** A finding that was only read is made to happen before anything changes. If it will not fail, the finding or the understanding is wrong.

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
- `screens-tell-the-truth` — **(2026-11-19, unevidenced)** Every message names what actually happened: not "failed" when it worked, not a cause that is not the real one, and not a raw error code when a session ends.
- `background-refresh-is-not-activity` — **(2026-11-19, unevidenced)** A screen that refreshes itself does not count as the user being present. Polling must not keep an unattended session alive past its idle limit.
- `bilingual-and-rtl` — **(2026-11-19, unevidenced)** Where users or documents are Arabic or another right-to-left language, the layout direction, fonts and mixed-direction text are designed from the start.

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
- `fixture-truth` — **(2026-09-12, from Tenant B)** Do not prove "not mock" by forbidding strings that real seed or shared fixtures also use — assert a unique created name, an auth header, or the signed-in chrome.
- `metrics-survive-time` — **(2026-11-19, unevidenced)** A rate still holds after retention expires, after the period changes, after a record is edited, and after a failed run. Failures sit in its denominator.
- `tests-cannot-touch-live` — **(2026-11-19, unevidenced)** Test set-up refuses to run unless every connection setting the code might read points at a test target, including the one the application prefers.

## 7 · Auth & session integrity **(+ new group, 2026-09-12, from Tenant B)**

For any cookie, bearer, or dual client/server session. Skip if the slice has no auth.

- `channel-precedence` — List every identity channel (storage, httpOnly cookie, demo headers, forwarded internal headers). Which wins, and can a weaker channel impersonate a stronger one? Write it down if two exist.
- `untrusted-headers-are-not-a-session` — Anything the browser can set is not equivalent to an httpOnly cookie. Internal headers used for same-request forwarding must be stripped on every continue path and set only after a successful server-side exchange.
- `same-request-cookie-invisibility` — `Set-Cookie` in middleware or a route is not visible to `cookies()` / the app server in that same render. If a later step in the same request must see the new value, forward it explicitly.
- `in-flight-must-not-undo-logout` — Cookie-clear and token refresh racing navigation or sign-out must not restore a session the user just ended. Use keepalive, await, or a generation/cancelled flag.
- `retry-bounds` — At most one refresh-and-retry on 401. No retry storm. A failed refresh clears the session; do not treat 401 as offline (`no-fake-offline-fallback`).
- `session-lifetimes` — **(2026-11-19, unevidenced)** Every session has an absolute limit and an idle limit, expired sessions are swept, and the sign-in page says why the user was signed out.
- `mfa-by-capability` — **(2026-11-19, unevidenced)** A second factor is required by what an account can do, not by its role's name. Enrolment cannot be undone by a refresh or a second tab, and lost-device and last-administrator recovery are designed.
- `no-account-oracle` — **(2026-11-19, unevidenced)** Sign-in, reset and lockout take the same time and say the same thing whether or not the username exists. Throttle per username and per client address.

## 8 · Security engineering — input, secrets, privilege, supply chain **(+ new group, 2026-11-19, unevidenced)**

For anything that takes outside input, holds a credential, runs another program or changes what goes into a build.

- `least-privilege-by-construction` — **(2026-11-19, unevidenced)** The running service's database account can read and write rows and nothing else. Schema changes run in a separate one-shot step. Check permissions granted by a second route too.
- `containers-run-unprivileged` — **(2026-11-19, unevidenced)** No container process runs as root. A program that opens untrusted files runs as its own user, with no network, no secrets and no view of stored data.
- `subprocess-gets-nothing` — **(2026-11-19, unevidenced)** A started program inherits nothing: a minimal explicit environment, a throwaway folder and a time limit. Libraries that start programs count. Keep a list of modules allowed to start them.
- `secrets-have-one-home` — **(2026-11-19, unevidenced)** Secrets live only in the secrets store or settings file. Example files carry no working default, and a published default password is refused at start-up.
- `no-query-from-a-value` — **(2026-11-19, unevidenced)** No database command, shell command or path is built by pasting a value in. Parameterise, or allow-list.
- `untrusted-input-is-hostile` — **(2026-11-19, unevidenced)** Every upload, document and field is treated as an attack: size checked before receipt, type by content, pages and length capped, control characters stripped, refused leftovers deleted. Every route counts.
- `prompt-injection-is-contained` — **(2026-11-19, unevidenced)** Assume the input to a model carries instructions. The model holds no tools and writes nothing, its answer is a validated structure, and a verdict needs evidence checked against the source. Test with hostile documents.
- `encrypted-in-transit-and-at-rest` — **(2026-11-19, unevidenced)** HTTPS is the deployment, and plain HTTP redirects. Outbound calls refuse a clear-text fallback and name the setting that would fix it. Record how stored data and backups are encrypted.
- `security-headers-and-csp` — **(2026-11-19, unevidenced)** Every response carries the security headers and a content-security policy, in every deployment mode.
- `supply-chain-is-pinned` — **(2026-11-19, unevidenced)** Libraries come from a locked, checksummed list, base images are pinned by digest, and models are verified against a recorded fingerprint. A bill of materials says what is in the build.
- `security-gates-in-ci` — **(2026-11-19, unevidenced)** The change clears its security gates before it enters history: secrets scan, static analysis, dependency and image scans, and project rules as code. Existing findings go on a baseline that only shrinks.
- `handover-contains-only-the-program` — **(2026-11-19, unevidenced)** A release or handover package is defined by an explicit include list. Commercial documents, data, keys and undo copies stay out unless named.

## 9 · Regulation & compliance — data, evidence, AI governance **(+ new group, 2026-11-19, unevidenced)**

For anything that stores personal or government data, makes an automated judgement, or produces evidence an auditor will rely on. Name the instruments that bind, and say which are claimed as compliance and which as alignment.

- `residency-is-enforced` — **(2026-11-19, unevidenced)** If data must stay in a jurisdiction, the code refuses an endpoint outside it unless an administrator allows it, and the allowance is audited.
- `classify-and-minimise` — **(2026-11-19, unevidenced)** Every stored item carries a classification. Collect and send only what the purpose needs, and redact before any outside call.
- `retention-and-disposal` — **(2026-11-19, unevidenced)** Every store, including uploads, intermediate passages, archives and backups, has a retention period and a disposal routine that actually runs. An archive nobody reads back is not retention.
- `lawful-basis-and-subject-rights` — **(2026-11-19, unevidenced)** For personal data, record what is processed, its lawful basis and how a person asks what is held about them. Do the impact assessment before go-live.
- `audit-trail-is-tamper-evident` — **(2026-11-19, unevidenced)** Security and decision events are recorded with who, what, when and how the actor signed in. The trail is append-only, chained, keyed and anchored outside the store. The running service cannot shorten or rewrite it, and an anchor reset is recorded and shown.
- `records-name-the-right-actor` — **(2026-11-19, unevidenced)** A record names the person who acted and the event that happened: not a system account, and not an event that was planned but never occurred.
- `forensic-readiness` — **(2026-11-19, unevidenced)** On a suspected incident, logs, their anchor and the affected documents can be preserved and exported before they age out.
- `monitoring-and-incident-response` — **(2026-11-19, unevidenced)** Decide which events alert, such as repeated sign-in failures, a failed integrity check or a residency override, and send them to a central feed. Write the incident procedure, the recovery targets and a restore-drill schedule.
- `access-is-reviewed` — **(2026-11-19, unevidenced)** Plan a periodic review of who holds access and what they can do, and a leaver process.
- `human-in-the-loop-is-enforced` — **(2026-11-19, unevidenced)** No automated result reaches a customer without a named approver. The state machine makes skipping that step impossible, and outputs say what they are.
- `ai-governance-pack` — **(2026-11-19, unevidenced)** Each model has a model card, an intended-use and limits statement, a risk-register entry, and a re-rating when the model or its environment changes. Quality gates measure accuracy per language and per other relevant subgroup.
- `compliance-register` — **(2026-11-19, unevidenced)** One register names each instrument, what it requires, who owns it, what evidences it, and a review date. A compliance claim with no evidence row is an alignment claim at best.
- `honest-assurance` — **(2026-11-19, unevidenced)** Until an independent assessment or penetration test is done, the claim is "built to these controls, not yet audited against them".

## 10 · Code optimisation & performance — paths that grow with use **(+ new group, 2026-11-19, unevidenced)**

Optimisation means less code and less work, never cleverness. A change justified as faster needs a measured before and after.

- `bounded-by-default` — **(2026-11-19, unevidenced)** Every list a screen or API returns is paged, filtered and counted in the database. It is never fetched whole and sifted in the app, and never silently capped by an inherited number.
- `stream-what-must-be-whole` — **(2026-11-19, unevidenced)** An export meant to include everything streams row by row, so its size is not limited by the process's memory.
- `read-once` — **(2026-11-19, unevidenced)** A request reads each thing once. Load per request, or cache with an explicit invalidation rule.
- `dont-redo-finished-work` — **(2026-11-19, unevidenced)** A retry resumes from what already succeeded. The cache it resumes from is keyed by everything that changes the answer, including model identity and version.
- `measure-at-real-volume` — **(2026-11-19, unevidenced)** Time a path with data at the size a working system reaches, and record the figure and the date it was measured.
- `index-what-you-filter` — **(2026-11-19, unevidenced)** Every filter, sort and join a screen uses at scale has an index, designed together with the query.
- `batch-not-one-at-a-time` — **(2026-11-19, unevidenced)** Where users act on many items, design the batch operation and the batch query, not one round trip per item.
- `delete-before-optimise` — **(2026-11-19, unevidenced)** The cheapest code is removed code. Delete first, merge repeated definitions second, and tune last, once the tests that would catch a mistake can be trusted.
