# Review — intake-form

Design: `.agent-rfc/designs/intake-form.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 3

1. **Syntax `tsc` accepted and the test runner could not.** `IntakeTakenError`
   used a constructor parameter property (`readonly open?`). `npx tsc --noEmit`
   passed; `test/intakes.test.ts` and `test/catalogs.test.ts` then failed to load
   at all, with `ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX` — the portal's tests run under
   Node's strip-only TypeScript. Rewritten as a plain field. The finding behind it:
   the type-check and the test runner disagreed about what TypeScript is, and only
   one of them was being asked. TypeScript 5.9 has `erasableSyntaxOnly`; the whole
   portal already compiled under it, so it is on in `portal/tsconfig.json` (design
   amended first), and a probe file with a parameter property is now refused by
   `tsc` itself.

2. **A test line that read as logic and did nothing.** The YAML pin in
   `test/catalogs.test.ts` sliced the `styles:` block with
   `yaml.search(/^\S/m.source ? /^agentic:/m : /^agentic:/m)` — a ternary whose
   two branches are identical, written by me. It happened to work. Replaced with a
   bounded slice that asserts both bounds exist.

3. **Two time formats on one screen.** In the browser, the issued panel printed the
   expiry through `Timestamp` (`2026-10-02 15:52:52 UTC`) while the 409 beneath the
   form printed raw ISO (`2026-10-02T15:52:52.062Z`) — the server's messages used
   `toISOString()`. `lib/formatTime.ts` exists so the portal prints time one way.
   Every message a person reads now uses `formatUtc`; the machine field
   `consumed_at` stays ISO.

## Pass 2 — findings: 0

Re-read the form, the page, the nav, `lib/intakeCatalog.ts`, the `createIntake`
changes and the tests against Group 5's levers and the rest.

- `intuitive-journey`, end to end in a real browser, on the BUILT STANDALONE server —
  the Docker image's shape — through a local proxy that added a test Developer's
  credentials, so no password ever entered the browser or a URL:
  "Start a tenant" in the Dev nav → the form → submit → the panel: intake 75, its
  token once, the expiry, the three commands with this portal's own address, the
  paste-it-when-asked line. The server stored `architecture: hexagonal`,
  `ides: ["cursor"]`, and the criteria trimmed with the blank line dropped.
- **The trap this slice was redesigned for, walked**: "Start another tenant", the
  same id → "you already started globex-orders as intake 75 … replace it if you no
  longer have its token" and **Replace intake 75 — its token stops working** →
  intake 76 issued. The database: 75 withdrawn, 76 open; the audit, by `dev`:
  issued 75, withdrawn 75, issued 76.
- `no-double-submit` — the button is disabled while busy and the handler returns
  early; read in code, since a double click cannot be timed reliably in the pane.
- P12 — after issue, the token was in the page and nowhere else: not the URL, history
  state, `localStorage`, `sessionStorage` or a cookie.
- `keyboard-and-screen-reader-operable` — every control has a real label (the radios
  and IDE checkboxes inside fieldsets with legends), every `aria-describedby` resolves,
  and the tab order is the reading order: 12 controls, no positive `tabindex`.
- `works-at-real-viewport-sizes` — at 375 px the form is one column and nothing
  overflows sideways (page width 375 of 375).
- `denied-vs-missing` — the page's own denied branch says which role is needed. Every
  role that opens the Dev workspace holds `dev.create` today, so it cannot be reached
  live; it is there for the first role that changes that.
- Mutations, by hand, each caught: anyone can replace; any id replaces; the withdrawal
  dropped (the old token keeps working). The pure tests pin `linesOf`, the architecture
  refusal, that `lib/intakes.ts` re-exports the SAME catalogue objects, and that the
  browser's module imports nothing.

## Sign-off

Group 1 · DRY & shared code — [x] checked — the catalogue moved, not copied (re-exported, and a test asserts the same objects); `AppForm`'s and `IngestTokenPanel`'s classes and panel reused; `linesOf` is the one textarea-to-list rule; time printed through `lib/formatTime.ts`.
Group 2 · Quality / safety — [x] checked — 4 pure tests, 3 database tests, the architecture pin; three replace mutations caught by hand; `erasableSyntaxOnly` proved to refuse the bug it was added for.
Group 3 · Architecture / hygiene — [x] checked — the page is a server component deciding access; only the form is a client component; the browser loads an import-free catalogue.
Group 4 · Process — [x] checked — the design was amended before `portal/tsconfig.json` was touched; the replace flow was raised with the owner before building.
Group 5 · Intuitive UI — [x] checked — the journey walked end to end in a browser, the lost-token trap included; three failure renderings; disabled while busy; labels, hints and tab order verified; phone width checked.
Group 6 · Signal integrity — [x] checked — refused, taken and unreachable read differently, and "unreachable" says whether anything was created is unknown rather than claiming it was not.
Group 7 · Auth & session integrity — [x] checked — the token shown once and held only in component state; replacing is the author's alone, for that intake, in one transaction, audited.

Tests added: `portal/test/intakes.test.ts` (4), `portal/test/intakesDb.test.ts` (3), and the architecture pin in `portal/test/catalogs.test.ts`.
Mutation-checked: by hand — three replace guards, each caught; `scripts/mutation_check.py` drives pytest only.
Fixtures re-pinned: none; `contract/intake/v1/` is unchanged and its fixture's `hexagonal` is in the catalogue.
Gates run: `npx tsc --noEmit` (with `erasableSyntaxOnly`), `npm test` (16 files), `npm run test:db` (7 files, fresh Postgres), `npm run build`, the browser walk on the standalone server, and `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `intuitive-journey`, `failure-is-not-a-result`, `irreversible-needs-confirmation`, `no-double-submit`, `denied-vs-missing`, `keyboard-and-screen-reader-operable`, `works-at-real-viewport-sizes`, `matches-the-existing-component-language`, `pin-unremovable-duplicates`, `guards-must-be-able-to-fail`, `docs-match-behaviour`.

KG query: kg:78b8bde85148
