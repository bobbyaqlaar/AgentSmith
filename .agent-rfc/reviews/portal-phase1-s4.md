# Review — portal phase 1, S4 and S5: three areas, and the Dev workspace

Design: `.agent-rfc/designs/portal-phase1.md` (S4 and S5, shipped together — the design records
why: a switcher pointing at an area with no pages would be a dead link between two commits).

**Built evidence (2026-09-18):**

- **Looked at, not only tested.** The pages were run against a throwaway Postgres seeded with
  AgentSmith's own last thirty commits, as `process_gate.py ci --json` recorded them, plus an app
  that has sent nothing and a GitLab app. Viewed in the browser pane as an Administrator and as a
  Developer granted one app, in dark and light, at desktop and phone width. Sign-in went through a
  local proxy that adds a throwaway test user's header, so no password was typed into a page.
- **What the Developer saw:** `/` lands in Dev with no switcher (one area); `/ops` says "You do not
  have access to the Ops workspace"; another app says "You do not have access to kyc-sentinel";
  an unknown one says "No app called no-such-app". Old URLs (`/tenants/…`, `/dlq`) redirect.
- **Tests:** `portal/test/devView.test.ts` (5, pure) and `portal/test/devReadDb.test.ts` (9,
  Postgres) — the seed goes in through the same handler CI uses, so what the ingest stores is what
  the pages read. `test_dev_record.py` +1 for the head designs.
- **Mutation checks (each reverted):** fourteen — an unsafe repository URL linked, GitLab linked
  like GitHub, a path left unencoded, "never received" shown as stale, repairs ignored, status
  taken from the last citation, closed designs counted as awaiting, approved deviations counted
  as awaiting, a `LIKE` wildcard accepted as a hash prefix, the verdict filter ignored, an old CI
  run rolling the designs back, an unbuilt area offered, the head designs dropped by the
  validator, the gate writing no head designs. All caught.

## Pass 1 — findings: 5

- `docs-match-behaviour`, `ambiguous-signals` — **finding, found by looking:** AgentSmith showed
  seven active designs; it has two. A design is closed by a records commit that does not cite it,
  so the last citing commit still says `active`, and "awaiting approval" was read the same way. The
  gate now writes every design as it stands at the head (`designs`), the portal keeps one snapshot
  per app, and status and approvals are read from it. The commit history keeps what was true when
  each commit was made. Tests `status is the head's, not the last citation's`, and
  `test_the_record_carries_every_design_as_it_stands_at_the_head`.
- `out-of-order-and-repeated` — **finding, same change:** a re-run of an old CI job would post an
  older head after a newer one and roll the designs back. The snapshot is replaced only by a head
  committed at least as late; test `an older CI run posted late does not roll the designs back`.
- `intuitive-journey` — **finding:** the commit page accepted only a full hash, and people copy
  short ones from CI logs and chat. A unique prefix of seven or more characters redirects to the
  full hash; an ambiguous one says so; anything that is not hex is refused before it reaches a
  `LIKE`.
- `intuitive-journey` — **finding:** neither the area links nor the app's tabs marked where you
  were, and a design written before pillar sections existed showed `0 · 0 · 0 · 0` — which reads
  as "answered nothing" when it means "has no answers to read". Current links are marked (and
  `aria-current`), and such a design says "no answers".
- `test-that-cannot-fail` — **finding:** nothing tested that the switcher hides an area with no
  pages (the Administration area until S6), or that short hashes resolve. Both are tested now.

## Pass 2 — findings: 0

Every lever over the final diff and every page, in both themes. Considered and declined:

- Aligning the Ops pages with Dev's denied-versus-missing. The Ops pages answer 404 for an app
  outside the user's grants, deliberately, to avoid confirming that an app exists; the approved
  specification asks for the two screens, and the Dev pages follow it. Changing the Ops pages is
  a behaviour change of their own — a backlog item, not this slice.
- Showing which gate judged each record. A backfill — `ci --json` run over old history — judges
  every commit by today's rules, so commits that passed at the time can show as failed (the seed
  here showed two). Real CI judges each push by the gate at its head. Recorded as a declared gap.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] checked
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] checked

Tests added/updated:      portal/test/devView.test.ts (5), devReadDb.test.ts (9),
                          devIngest.test.ts (+1), authz.test.ts (+1),
                          scripts/test/test_dev_record.py (+1)
Mutation-checked:          yes — fourteen, each reverted; all caught
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:8e07004937b5
Gates run locally:         npm test, the DB suites on a throwaway Postgres, tsc --noEmit,
                          next build, the Python gate suites (160), the pages in the browser
Declared gaps:             (1) a record does not say which gate judged it, so a backfill of
                              old history shows today's verdicts;
                          (2) the Ops pages still answer 404 for an app outside a user's
                              grants, where Dev shows "no access" — backlog
```
