---
status: done
scope:
  - portal/package.json
  - portal/test/runtimeImageScripts.test.ts
---
# `npm run db:migrate` runs in the image the Dockerfile builds

## Problem

`portal/Dockerfile`'s final stage copies `scripts/` and `db/` with this comment:

> Not part of Next's own build trace (it's a standalone migration script, never imported by the app
> itself) — copied explicitly so `docker compose run portal npm run db:migrate` works against the
> running image without a separate build step.

It does not work. The script is

```json
"db:migrate": "node --experimental-strip-types --experimental-loader=./test/ts-extension-loader.mjs scripts/migrate.ts"
```

and the final stage does not copy `test/`, so the documented command fails:

```
Error [ERR_MODULE_NOT_FOUND]: url: 'file:///app/test/ts-extension-loader.mjs'
```

Found 2026-10-18 while verifying the portal for the demo: the Chapter 3 checklist told the reader to
run exactly that command, and it had presumably never worked against a built image. Dropping the
loader runs it correctly — `Ops Portal schema applied successfully.` — which is how the demo's
database got its schema.

**The loader is not the problem; its presence in this script is.** `test/ts-extension-loader.mjs`
exists because tests run under plain Node need `.ts` and `@/…` specifiers resolved, which Next's
bundler does at build time. `scripts/migrate.ts` imports only `node:fs`, `node:url`, `node:path` and
`pg` — nothing the loader has to resolve. It was copied into the script from the test invocations
beside it, and nothing failed in development, where `test/` is present.

This is a `declared-vs-enforced` defect: the Dockerfile declares the command works, and no check
reads that claim.

## Approach

**Take the loader out of `db:migrate`**, leaving `node --experimental-strip-types scripts/migrate.ts`.
The test invocations keep it — they need it.

**Then enforce the Dockerfile's claim, so it cannot rot again.**
`portal/test/runtimeImageScripts.test.ts` reads both files and compares them:

- parse the final stage of `portal/Dockerfile` (from its last `FROM … AS` to the end) for
  `COPY --from=… <src> <dest>` destinations, giving the set of paths the image carries;
- for each script the image is expected to run — `db:migrate` today, named in one list with the
  reason — extract every relative file path the command line mentions;
- assert each of those paths is carried by the final stage.

Today that fails on `./test/ts-extension-loader.mjs`; after the fix it passes, and it will fail
again the day someone adds a flag pointing at a path the image does not have, or deletes a `COPY`
the script depends on. The test is registered in `portal/package.json`'s `test` chain, which the
`Ops Portal (Next.js)` gate runs.

**Not in scope:** making the whole test suite runnable in the runtime image (it is not meant to be),
moving the loader out of `test/`, and `npm start` (the container's `CMD` is `node server.js`, so npm
is not in that path). The one script the Dockerfile promises is the one checked.

## Pillars

- P1 applies — this note (`.agent-rfc/designs/portal-migrate-runs-in-the-image.md`) precedes the change; the failure and the working command are recorded in `DemoScript.md`'s Chapter 3 checklist, where the broken command was published to the reader.
- P2 n/a — no dependency added; the test uses `node:fs`, `node:assert` and `node:test` as the portal's other tests do.
- P3 n/a — a build-time script and a test; no tracing path.
- P4 applies — the failing test comes first: `portal/test/runtimeImageScripts.test.ts` fails against today's `portal/package.json` on `./test/ts-extension-loader.mjs`, and passes once the flag is gone.
- P7 applies — TypeScript test under the portal's own conventions (`node --experimental-strip-types --experimental-loader=./test/ts-extension-loader.mjs test/runtimeImageScripts.test.ts`), registered in the `test` chain beside its siblings.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the test reads `portal/Dockerfile` and `portal/package.json` as text and only matches path shapes; nothing is executed from either.
- P12 n/a — no credentials. `scripts/migrate.ts` reads its connection string from the environment, unchanged.
- P13 n/a — no gate is touched. The `Ops Portal (Next.js)` CI gate gains a test.
- P14 n/a — no fixture; `.agent-rfc/fixtures/knowledge_graph.json` is regenerated only because a tracked file changes.
- P15 applies — "the loader is needed here" and "the loader is needed by the tests next to it" were one signal in `portal/package.json`; the new test states which scripts the image must run, so the two are no longer read together.
- P16 applies — the test fails closed: if the final stage cannot be found in the Dockerfile, or a script names no paths, it asserts rather than passing silently (a `declared-vs-enforced` check that matches nothing is the defect it exists to prevent).

## Deviations

none

## Dependencies

None added.

## Levers

- `declared-vs-enforced` — the Dockerfile's comment is a claim; now something reads it.
- `environment-parity` — the command worked in development, where `test/` exists, and failed in the image; the difference is what the test encodes.
- `test-that-cannot-fail` — the check asserts it found a final stage and at least one path per script, so it cannot pass by matching nothing.
- `docs-match-behaviour` — `DemoScript.md`'s checklist already carries the working command and the reason; this makes the documented one true.
- `grep-for-siblings` — every other `--experimental-loader` use in `portal/package.json` is a test invocation, which needs it; only `db:migrate` is run against the image.
