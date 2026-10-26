---
status: done
scope:
  - scripts/test/test_ts_runner_invocations.py
---
# `db:migrate` cannot pass a loader the runtime image does not carry

## Problem

`scripts/test/test_ts_runner_invocations.py::test_every_runner_invocation_passes_the_loader`
is red on this branch:

```
these run TypeScript without ts-extension-loader.mjs, so an extensionless
relative import in portal/lib will fail there only:
    portal/package.json scripts.db:migrate
```

Two invariants collide, and both are real:

- **The sweep's rule.** `portal/lib` modules import each other with extensionless
  relative specifiers, which `node --experimental-strip-types` does not resolve.
  `portal/test/ts-extension-loader.mjs` closes that gap, and the sweep exists
  because a third call site missed the flag and `main` stayed red for three
  commits (the test's own docstring records it).
- **The image.** `portal/Dockerfile`'s `runner` stage copies `scripts`, `db` and
  `package.json` (lines 36–38) and **not** `test`. A `db:migrate` that names
  `./test/ts-extension-loader.mjs` fails in the one place the command is
  documented for — the defect `510aaf7` fixed and
  `portal/test/runtimeImageScripts.test.ts` now guards.

I introduced the collision in `3439bd2` (originally `510aaf7`) by removing the
flag, and did not run the Python suite on that slice — only `portal/`'s own
tests — so the guard has been red in local commits since. Nothing was pushed, so
`main` was never red.

**And the guard has a hole of its own**, found while verifying that it still
catches what it is for. The sweep tests each `package.json` script as ONE
string, but `scripts.test` is a twenty-link `&&` chain: deleting the loader from
the first link alone left the file green, because the other nineteen links still
mention the flag. That is the file's own stated defect — a call site missing the
flag — passing its own check. It predates this branch and `main` has it today.

## Approach

**Exempt the one invocation by name, and pin the premise that makes the
exemption sound.** `portal/scripts/migrate.ts` imports `node:fs`, `node:url`,
`node:path` and `pg` — no relative specifier, so there is nothing for the loader
to resolve. The loader was never load-bearing there; the sweep's rule was simply
blanket.

- `EXEMPT_INVOCATIONS = {"portal/package.json scripts.db:migrate"}`, holding the
  full `where` string the sweep emits, so the entry stays exact and the
  invocation is still **found** — `test_the_sweep_finds_the_known_invocations`
  asserts `db:migrate` is in the swept set and keeps asserting it.
- `test_the_exempt_invocations_import_nothing_needing_resolution` reads each
  exempt script's `.ts` entry point out of `portal/package.json` and fails if it
  contains a relative (`./`, `../`) or aliased (`@/`, from `portal/tsconfig.json`
  `compilerOptions.paths`) import specifier. The day `migrate.ts` gains one, the
  exemption's reason stops being true and that test says so — instead of an
  `ERR_MODULE_NOT_FOUND` in a container at migration time.

**And check one invocation at a time.** `_shell_invocations` splits a script
on `&&`, `||` and `;` and yields each part that spawns the runner, so every link
of the `test` and `test:db` chains is asserted on its own. The `where` string
gains the entry point it runs — `portal/package.json scripts.test
(test/authz.test.ts)` — which is also what makes the exemption above name
`scripts/migrate.ts` explicitly instead of a script name that could come to mean
something else. A stale exemption, naming an invocation the sweep no longer
finds, fails rather than quietly exempting nothing.

**And make each rule falsifiable on its own.** Both conditions move out of the
comprehension into named predicates — `_missing_loader` and
`_needs_resolution` — each with a test that feeds it a synthetic case either
way. A sweep over a clean tree says nothing about its own rule: replacing the
loader condition with `False` left all seven tests green, and replacing
`_needs_resolution`'s alias half left them green too, because nothing in the
repository exercises that branch. A predicate with its own control fails in both
cases.

Rejected: copying `test/ts-extension-loader.mjs` into the `runner` stage. It puts
test scaffolding in a production image to satisfy a script that does not need it,
and `portal/test/runtimeImageScripts.test.ts` would then be satisfied by shipping
more, not by needing less.

## Pillars

- P1 applies — this note precedes the edit; the failing assertion is quoted verbatim in `## Problem`, and the two colliding guards are named (`scripts/test/test_ts_runner_invocations.py`, `portal/test/runtimeImageScripts.test.ts`).
- P2 n/a — no module boundary moves; one test file gains a constant and a test.
- P3 n/a — a pytest guard, not a traced runtime path.
- P4 applies — ten mutants, each applied to `scripts/test/test_ts_runner_invocations.py`, `portal/package.json` or `portal/scripts/migrate.ts` and each reverted: a relative or aliased import added to `portal/scripts/migrate.ts` (five forms — `from "./x"`, bare `import "../x"`, `await import("./x")`, `export … from "@/x"`, `import d from "@/x"`); the loader deleted from the FIRST link of `scripts.test`, and from the LAST; `db:migrate` renamed; `_shell_invocations` returning the whole script; `_specifiers` returning `[]`; `_alias_prefixes` returning `set()`; the entry point dropped from the `where` label; `_needs_resolution` losing its relative half, then its alias half; `_missing_loader` returning `False`. All ten fail. Three of them did **not** before the fixes they prompted: the first-link drop (before `_shell_invocations`), the alias half (before `test_what_counts_as_needing_resolution`), and `_missing_loader` → `False` (before `test_the_loader_rule_reports_a_missing_flag`). `test_the_sweep_finds_the_known_invocations` still asserts `db:migrate` is swept, so the exemption cannot hide the invocation.
- P7 applies — Node 22 `--experimental-strip-types` resolution rules are the subject: bare specifiers (`pg`) and `node:` builtins resolve without a loader, extensionless relative ones do not. `portal/tsconfig.json` `compilerOptions.paths` declares `@/*`, which the bare runner does not resolve either, so the premise test rejects it too.
- P8 n/a — no telemetry; `scripts/test/**` emits no spans.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — the test reads `portal/package.json` and `portal/scripts/migrate.ts`, both tracked files in this repository, with `json.loads` and a regex over text; nothing is executed and no input comes from outside the checkout.
- P12 n/a — no credentials; `DATABASE_URL` is read by `migrate.ts` at runtime, which this change does not touch.
- P13 applies — this weakens a guard in one place and strengthens it in another, so both directions are pinned. The exemption is a named exact string rather than a pattern (the same choice the file's existing `EXEMPT` set documents), covers one invocation, and is paired with a test that fails the moment its justification stops holding. The blanket rule now applies per invocation to all 29 others in `portal/package.json` — 29 separate assertions where there were 2 — and to `scripts/security/runners/_shared.py`, which the window sweep still covers unchanged.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains nothing (the file is already a `CodebaseFile` node); it is regenerated and re-pinned because a tracked file changes, and `agentsmith gate kg check` is the control.
- P15 applies — two ambiguous signals, both in `scripts/test/test_ts_runner_invocations.py`. "No loader flag" was read by the sweep as "the author forgot it" in every case, including the one where the flag cannot be there; the premise test now distinguishes them — exempt **and** nothing to resolve, or red. And "the flag appears in this script" was read as "every call in this script passes it", which for a twenty-link chain it is not; `_shell_invocations` removes the ambiguity by making the unit of the assertion the unit of the defect.
- P16 applies — the recovery path if the exemption turns out wrong is that `npm run db:migrate` fails in the image with `ERR_MODULE_NOT_FOUND`; `portal/test/runtimeImageScripts.test.ts` catches the mirror-image failure (a script naming a file the `runner` stage lacks), so both directions are covered by a test rather than by a container at migration time.

## Deviations

none

## Dependencies

None added.

## Levers

- `named-exemption-over-pattern` — one exact `where` string, not a glob over `package.json` scripts.
- `pin-the-premise` — an exemption granted for a reason gets a test on the reason, so it cannot outlive it.
- `test-that-cannot-fail` — a sweep over a clean tree cannot prove its own rule; each rule is a named predicate with a synthetic case either way.
- `two-guards-one-truth` — the Python sweep and `runtimeImageScripts.test.ts` now agree instead of contradicting; each catches the other's blind side.
