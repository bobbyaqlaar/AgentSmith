# Review — `npm run db:migrate` runs in the image the Dockerfile builds

Design: `.agent-rfc/designs/portal-migrate-runs-in-the-image.md`. Owner's instruction, 2026-10-18:
"fix the db:migrate script", after the portal verification found the documented command broken.

**Built evidence (2026-10-18):**

- **The defect, as the image reports it:** `docker compose run --rm portal npm run db:migrate` →
  `ERR_MODULE_NOT_FOUND: file:///app/test/ts-extension-loader.mjs`. The final stage copies
  `scripts/` and `db/` — with a comment saying it does so *expressly* for this command — and does
  not copy `test/`.
- **Why dropping the loader is safe, checked rather than assumed:** `portal/scripts/migrate.ts`
  imports `node:fs`, `node:url`, `node:path` and `pg`, and nothing else. The loader resolves
  extensionless `.ts` and `@/…` specifiers for tests run under plain Node, which Next's bundler
  handles at build time; every other `--experimental-loader` use in `portal/package.json` is a test
  invocation that needs it.
- **Tests first:** `portal/test/runtimeImageScripts.test.ts` — 2 failing against the old script
  (`"db:migrate" references test/ts-extension-loader.mjs, but the image's final stage does not copy
  test/ (it carries: .next, db, node_modules, package.json, scripts, server.js)`), 2 passing after
  the one-line change. Registered at the end of `portal/package.json`'s `test` chain, which the
  `Ops Portal (Next.js)` gate runs.
- **No CHANGELOG entry:** `.agenticframework/process-gates.json`'s `changelog.paths` are the paths a
  tenant receives — `hooks/**`, `scripts/**`, `runtime/**`, `workflow-templates/**`,
  `templates/agent-rules.yaml` and friends. `portal/**` is gated but not among them, and this is a
  build-script fix inside the portal, visible to whoever builds the image rather than to a tenant.
  Said here rather than skipped silently.

## Pass 1 — findings: 1

- `test-that-cannot-fail` — **finding, in my own test:** the first version **passed while the defect
  was still present**. `carriedByFinalStage` read `COPY --from=build /app/.next/standalone ./` as
  carrying "`.`", and the assertion allowed any path when "`.`" was present — so the check matched
  everything and proved nothing. A guard written to enforce a claim, that cannot fail, is worse than
  no guard: it reads green in CI forever.
  Fixed by enumerating what the standalone bundle actually provides (`server.js`, `node_modules`,
  `.next`, `package.json`) and dropping the wildcard, with a comment recording why. Both tests then
  failed against the old script and pass against the new one, which is the only sequence that proves
  a guard works.

## Pass 2 — findings: 0

- `declared-vs-enforced` — the Dockerfile's comment is now read by something. The failure message
  quotes that promise back, so whoever breaks it learns why the file was copied in the first place.
- `environment-parity` — the command worked where `test/` exists (a developer checkout) and failed
  in the image; the test encodes exactly that difference rather than the symptom.
- `grep-for-siblings` — every `--experimental-loader` in `portal/package.json` was read: all the
  others are test invocations, which need it, and `npm start` is not in the container's path at all
  (`CMD ["node", "server.js"]`), so `db:migrate` is the one script the image must run.
- **Verification needs a rebuild, and that is worth knowing:** the first re-run of the documented
  command still failed, because `package.json` is baked into the image (`COPY … ./package.json`).
  The source fix is not provable without `docker compose up -d --build portal`. Recorded in the
  closing pass below with the result.
- `irreversible-needs-confirmation` — n/a, but noted: this slice changes no data and no gate; the
  migration it unblocks is the same `db/schema.sql` apply as before.

## Pass 3 — findings: 1

Hand mutants, six of them, split deliberately: three of **what the guard guards**, three of **the
guard's own rails**. First run: **3 of 6**.

- `test-that-cannot-fail` — **finding:** all three rail mutants survived — the standalone wildcard
  restored, the "paths were found" assertion disabled, the "final stage exists" assertion disabled.
  Not because the rails are wrong, but because with a correct `package.json` there is nothing for a
  weakened rail to miss: a single mutant cannot show it. That is the same gap
  `scripts/test/test_documented_env_vars_exist.py` closes with its `test_the_scan_finds_candidates`
  guard-the-guard test.
  Fixed by making the checks a function over `(package.json, Dockerfile)` — `checkRuntimeScripts`,
  `carriedByFinalStage`, `referencedPaths`, exported — and adding four tests that feed it synthetic
  inputs: the standalone bundle is enumerated and never `.` (plus the consequence: a script reaching
  into `test/` throws), a script naming no paths is refused, an unparsable Dockerfile is refused, and
  a missing runtime script is refused. 2 tests → 6.
  Re-run: **6 of 6 caught**, and the three guarded-side mutants (db:migrate reaching into `test/`,
  db:migrate pointing at an uncopied path, the Dockerfile dropping `COPY … ./scripts`) were caught
  in both runs.

## Pass 4 — findings: 0

- **The end-to-end proof, which needed the rebuild:** `docker compose up -d --build portal`, then
  `docker compose run --rm portal npm run db:migrate` →
  `> node --experimental-strip-types scripts/migrate.ts` / **`Ops Portal schema applied
  successfully.`** The same command on the pre-fix image failed with `ERR_MODULE_NOT_FOUND`, and on
  the post-fix *source* with the pre-fix *image* also failed — `package.json` is baked in, so only a
  rebuild proves it.
- **The portal's whole suite**, the command the `Ops Portal (Next.js)` gate runs: `npm test`, every
  file in the chain, **0 failures** (the new file's 6 among them).
- Gates by name, all passing: the process gate itself, commit guardrails, `ruff`, `--check-kg`,
  `npx tsc --noEmit` (the portal type-checks with the new test in the tree), `npm test — the in-app
  widget`, `npm test — cross-tenant isolation`.
- `docs-match-behaviour` — `DemoScript.md`'s Chapter 3 checklist already carried the working command
  and the packaging reason; with this slice the documented `npm run db:migrate` is the working one,
  so the warning there now reads as history rather than a live workaround.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked — pass 1 was a guard that could not fail
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      portal/test/runtimeImageScripts.test.ts — new, 6 tests (2 failing
                          first against the old script, 4 added in pass 3 to prove the guard's
                          own rails bite); registered in the portal's `test` chain
Mutation-checked:          6 by hand, 6 caught after pass 3 (3 of 6 before it), each reverted:
                          three of what the guard guards, three of the guard's own rails
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:524b01d2d7bd
Gates run locally:         seven by name, all passing — the process gate, commit guardrails,
                          ruff, --check-kg, npx tsc --noEmit, the widget suite and the
                          cross-tenant suite — plus the portal's full `npm test` chain with 0
                          failures, and the documented command proven against a rebuilt image
Declared gaps:             the rest of the portal's test suite is not runnable in the runtime
                          image and is not meant to be; the loader stays in `test/` rather than
                          moving to `scripts/`; `npm start` is unchecked because the container
                          runs `node server.js`
```
