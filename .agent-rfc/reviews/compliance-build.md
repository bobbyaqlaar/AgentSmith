# Review — compliance-build

Scope: Phases 1 to 6 of `.agent-rfc/designs/compliance-readiness.md`. Worked against `docs/review-levers.md`, with each finding reproduced in code or by a test.

## Pass 1 — findings: 11

1. `failure-is-not-a-result` — **A resume deleted the stop flag before writing its record,** so a resume nobody could record still happened. **Fix:** record first; `test_a_resume_that_cannot_be_recorded_does_not_happen`.
2. `declared-vs-enforced` — **An image without `compliance.json` read as having no profile,** silently switching every duty off. **Fix:** `COMPLIANCE_PROFILE` makes a missing file an error; `OB-DEPLOYED` checks every Dockerfile.
3. `gate-integrity` — **A stopped app still answered from the idempotency cache.** **Fix:** the stop check runs before the cache; test added.
4. `implemented-not-invoked` — **The launcher's Python used a nested f-string that does not parse on 3.11,** so `process-gate compliance` would have crashed in CI. No test ran the launcher. **Fix:** rewritten; `test_the_launcher_reports_and_fails`.
5. `gate-integrity` — **Lockout was keyed on `X-Forwarded-For`,** which a caller sets. **Fix:** keyed by account.
6. `failure-is-not-a-result` — **A refused fallback leaked its budget reservation and surfaced as "all tiers exhausted".** **Fix:** guarded inside the ladder's `try`, re-raised as `ComplianceRefused`; `test_a_fallback_outside_the_boundary_is_refused_before_it_is_called`.
7. `guards-must-be-able-to-fail` — **The audit and access exports were not scoped to the caller's apps.** Caught by `authz.test.ts`. **Fix:** the audit export filters by app; the access export needs the organisation-wide role.
8. `guards-must-be-able-to-fail` — **I widened `hitl_reviewer` to `ops.read`.** Caught by `authz.test.ts`. **Fix:** reverted; `ops.hitl` already opens the Ops area.
9. `docs-match-behaviour` — **The plan said a developer cannot attest their own change.** Only the portal's role enforces separation; at a terminal the signer states a role. **Fix:** the plan says so.
10. `docs-match-behaviour` — **Eight passages still called named decisions or the stop control unbuilt** after they were built. **Fix:** each now says "on a compliance profile"; the Phase 0 CHANGELOG entry too.
11. `run-the-gates-ci-lists` — **`complete_stream` read `kwargs` after `del kwargs`.** Caught by mypy. **Fix:** read before the delete.

## Pass 2 — findings: 3

1. `minimal-host-dependency` — **The new supply-chain job found 39 advisories in the lock and 4 in the portal.** **Fix:** fixed releases of aiohttp, certifi, multidict, yarl, pyasn1, pyjwt, urllib3, the OpenTelemetry set, nanoid and source-map-js. **Left open and on the backlog, each a major upgrade:** Next.js, postcss through it, the LangChain and LangGraph family, cryptography, pytest.
2. `minimal-host-dependency` — **Bandit found three SQL strings built with f-strings in new code and nine older findings.** **Fix:** mine rewritten or annotated; each older one annotated with why it is safe.
3. `no-redundant-artifacts` — **`npm audit fix --omit=dev` pruned the portal's dev tools.** Environment only. **Fix:** reinstalled from the lock.

## Pass 3 — findings: 10

1. `minimal-host-dependency` — **Removing LangChain removed `pydantic`,** which had only arrived through it. A clean sync to the lock showed the gate could not start. **Fix:** a direct dependency; the suite now runs on a venv synced to the lock.
2. `implemented-not-invoked` — **The access review export read Basic users only,** so on the SSO-only profile it was empty. **Fix:** both sources; test added.
3. `failure-is-not-a-result` — **A gate that timed out stayed in the reviewers' queue forever,** and deciding it could only fail. **Fix:** a `hitl_timeout` record clears it.
4. `implemented-not-invoked` — **Closing an incident had an API and no button.** **Fix:** added.
5. `guards-must-be-able-to-fail` — **An attestation id was unique across tenants,** so one app could occupy another's. **Fix:** keyed per tenant.
6. `guards-must-be-able-to-fail` — **A signature could be given for an app that does not exist** under an all-apps grant. **Fix:** refused.
7. `docs-match-behaviour` — **The checklist did not show a signature made at a terminal,** where the role is self-stated. **Fix:** labelled.
8. `run-the-gates-ci-lists` — **The SBOM step named a program that does not exist,** so the job would have failed. Found by running it. **Fix:** the real entry point, in both workflows.
9. `run-the-gates-ci-lists` — **`cryptography` 49 still carried an advisory.** **Fix:** 50.
10. `test-that-cannot-fail` — **The status-report test could not fail:** its fake lacked `Timeout`, the call raised and was swallowed. A mutant survived. **Fix:** a complete fake.

## Pass 4 — findings: 5

1. `grep-for-siblings` — **Trace export could leave the boundary.** **Fix:** not exported outside it, and logged.
2. `grep-for-siblings` — **Slack and Teams notices could leave.** **Fix:** skipped outside it.
3. `grep-for-siblings` — **Ops reports, through both senders, could leave.** **Fix:** not sent outside it.
4. `grep-for-siblings` — **An embedding model downloaded from a public hub on first use.** **Fix:** on the profile it must already be on disk.
5. `docs-match-behaviour` — **ASI10 moved to Partial, and four places still said five and five.** **Fix:** six and four throughout.

## Pass 5 — findings: 2

1. `run-the-gates-ci-lists` — **The new contract's `protocol.md` was not registered as reference documentation,** so `process_gate.py artifacts` refused it. **Fix:** declared beside the other contracts.
2. `no-redundant-artifacts` — **Two shipped designs, `release-4-0-1` and `repo-review-and-archive`, were still active** and claimed files this change touches. **Fix:** marked done.

## Pass 6 — findings: 0

- **Every guard can fail.** Twenty hand mutants across the gateway, eval router, developer pipeline, stop flag, signatures, ratchet, wiring check and senders, all killed.
- **Clean environment.** A venv synced exactly to the lock, with no LangChain.
- **Portal on Next 16.** Every page 200, unauthenticated 401, wrong-app 403, security headers present; the production image builds; the schema applies twice to an empty database; `test:db` passes.
- **Scanners.** `pip-audit`: nothing except the one ignored test-only advisory. `npm audit`: none. Bandit exits 0. The SBOM command runs.

## Pass 7 — findings: 9

Close-out, against the code and a real scaffold.

1. `implemented-not-invoked` — **`agentsmith compliance` could not run from an install:** the installer copied neither the catalogue, the templates nor `contract/`. Only runs from a checkout had been tried. **Fix:** installed.
2. `implemented-not-invoked` — **`tenant init --profile` produced a first commit its own gate refused.** Profile files were written after the manifest, and the scaffold design answered no profile pillar. Found by building a real tenant. **Fix:** enabled before the manifest; the design and `design new` both ask them.
3. `implemented-not-invoked` — **CI never ran the compliance check;** only the production deploy did. **Fix:** a step in `eval-security.yml`, which passes when there is no profile.
4. `guards-must-be-able-to-fail` — **A gate could omit `requested_by`,** so nothing stopped a person approving their own request. **Fix:** refused, non-retryably.
5. `guards-must-be-able-to-fail` — **The audit views ignored scope** for a legacy per-app administrator. **Fix:** filtered in the list, page and export.
6. `failure-is-not-a-result` — **`security check` hung on an open pipe.** **Fix:** stops when nothing arrives.
7. `docs-match-behaviour` — **My scratch moderation hook returned a dict,** which passes the harness and fails at run time. Found only by a live call through the sidecar. **Fix:** the real result type.
8. `test-that-cannot-fail` — **`edgeSafety.test.ts` guarded a constraint that no longer exists** after the move to `proxy.ts`. **Fix:** removed.
9. `run-the-gates-ci-lists` — **`test_the_launcher_moves_past…` failed in a virtual environment,** so the local suite could not be clean. **Fix:** a wrapper, not a symlink.

## Pass 8 — findings: 0

- **Every guard can fail.** Thirty-two hand mutants in all, across both rounds, all killed.
- **A real tenant, built with `build.sh`:** the profile passes, and fails once its human gate is removed.
- **The sidecar, live against Falcon 3 and Postgres:** an answer with its signed mark, and a 403 naming `OB-RESIDENCY` once the boundary excludes the model. Conformance 6 of 6.
- **The developer pipeline ran a full graph** on LangGraph 1.x.
- **Portal in a browser on a production build:** checklist, signing, human decisions, incidents, stop and decision trail, in dark, light and phone widths, with no horizontal overflow.
- **`SEC-AUDIT-002`** passes against a live database and reads not applicable without one.
- **Whole suite on a venv synced to the lock:** 2601 passed, 10 skipped, 0 failed. Portal: 136 tests, 85 database tests, `tsc`, build. `pip-audit` on both locks, `npm audit` and Bandit are all clean.

## Pass 9 — findings: 10

1. `guards-must-be-able-to-fail` — **The production gate ran after the deploy,** so a failed obligation could not stop anything. **Fix:** moved ahead of build and deploy; a test pins the order.
2. `out-of-order-and-repeated` — **Through the sidecar, an old approval answered a new request** with different input on the same gate. **Fix:** a decision counts only if its digest matches the latest request.
3. `environment-parity` — **The sidecar built a gateway per request,** so an in-process budget never added up. **Fix:** one per app.
4. `failure-is-not-a-result` — **A moderation or prompt-guard block reached the caller as a server error.** **Fix:** a 422 that says it was blocked.
5. `grep-for-siblings` — **Signature exchange and CLI audit events ignored the boundary.** **Fix:** both check it.
6. `consistent-auth-gates` — **Under Basic auth a browser would send credentials on a cross-site POST** to the new routes. **Fix:** the proxy refuses cross-site writes.
7. `consistent-auth-gates` — **The decision trail showed the reviewed case to anyone with `compliance.read`.** **Fix:** only a reviewer sees the input.
8. `implemented-not-invoked` — **Nothing showed that an app had been stopped.** **Fix:** a status line on the app page.
9. `implemented-not-invoked` — **`agentsmith sync` dropped the compliance provider,** so the next CI run would have failed. Found by running a sync on a real tenant. **Fix:** kept, and the end-to-end test now syncs.
10. `docs-match-behaviour` — **Three places still said `python-fastapi` only.** **Fix:** corrected.

## Pass 10 — findings: 0

- **Every guard can fail.** Thirty-six hand mutants in all, each killed. One survived at first (signature exchange) and now has a test.
- **The environment CI really has.** The scratch tenant builds and judges correctly on Python 3.12 with only `requirements-gate.txt` installed.
- **A Go tenant on the profile:** goes on the sidecar, its first commit passes its own gate, and the check names what is left to fill in.
- **Portal, live:** a developer does not see the case and a reviewer does; a cross-site POST is refused and a same-origin one is not; a stopped app says so.
- **Deliberately left:** `send_dev_record` carries gate metadata and no application data, so it is not held to the boundary. The Stopped line shows stops given in the portal, not at a terminal.
- **Whole suite on a venv synced to the lock:** 2605 passed, 10 skipped, 0 failed. Portal: 136 tests, 85 database tests, `tsc`, production build.

## Pass 11 — findings: 3

Found by the commit gate, on the staged tree, which earlier passes had not put through it.

1. **`## Dependencies` was wrong.** It said no package was added, and named none of the entries `requirements-pipeline.lock` and `portal/package-lock.json` gain. Fixed: all 79 are named, `langchain-protocol` is stated as the one Python package new to the repository, compared against both locks at `d31ec79`.
2. **The new scratch tenant's route was synchronous** (`P7-async`). Fixed: `async def`.
3. **That route opened no span** (`P3-tracing`). Fixed with a real span, not an allowlist entry, which only the owner can grant. It uses `opentelemetry-api` directly, because a tenant's CI does not install `agentsmith`.

## Pass 12 — findings: 0

Over the fixes of Pass 11 only; the code behind them is unchanged since Pass 10.

- The commit gate's checks of the staged tree report nothing but this record's own open pass: every lock entry is named, and no route is synchronous or spanless.
- The tenant app's test passes in an environment holding only its `requirements.txt`, so the new import resolves where the tenant's CI runs it. `scripts/test/test_scratch_tenants.py`: 21 passed.
- `agentsmith gates run` on the staged tree: 15 passed, 8 need services or CI context. Two cannot judge an uncommitted tree: the process gate reads the committed config, and the mutation harness refuses uncommitted files. Both are run against the commit before it is pushed.

## Pass 13 — findings: 1

The curated mutation harness against the commit, which it refuses to run on an uncommitted tree.

1. **A curated mutation had a stale target.** The call that renders a scaffold design was reformatted when a profile's pillars were added, so `a scaffold design leaves out the manifest committed beside it` no longer matched `agentsmith/cli.py`. CI fails on a stale target. Fixed: re-pointed at the current line in `scripts/mutation_check.py`, not removed.

Not findings, and recorded so they are not mistaken for passes: the first run lost 21 suites when files under `/private/tmp` disappeared from the scratch environment mid-run, and `hook_payload` then failed on an absolute `PYTHONPATH` exported by hand, which let a throwaway repository import AgentSmith from this checkout. CI sets neither. The environment was rebuilt from the lock and those suites run again.

## Pass 14 — findings: 0

Over the re-pointed mutation, and the harness as a whole.

- The new target matches exactly once in `agentsmith/cli.py`, and the mutant is caught by `framework_sync`.
- `scripts/mutation_check.py`: all 270 mutations across 37 suites caught, none survived, none stale. The tree returned clean after each run.
- `process_gate.py ci` over the pushed range passes.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one catalogue generates the manual table and portal copy; `test_generated_copies_match_the_catalogue` holds them.
Group 2 · Quality / safety — [x] checked — models at every boundary; an unreadable declaration fails rather than reading as no profile.
Group 3 · Architecture / hygiene — [x] checked — a port like the security port; no new service; every runtime branch sits behind `profile_active()`.
Group 4 · Process — [x] checked — one design for the owner's one-PR instruction; CHANGELOG, backlog and manual updated; no release.
Group 5 · Intuitive UI — [x] checked — checklist, decision queue, trail, incidents and stop rendered and driven against a throwaway database; seen in a browser on a production build, in both themes and at phone width.
Group 6 · Signal integrity — [x] checked — thirty-six hand mutants of the guards all killed; a gap is a failure on the profile, and an unreachable portal signs nothing.
Group 7 · Auth & session integrity — [x] checked — idle and absolute limits, jti kept across refresh, MFA claim, lockout, session actor only.

Tests added: `scripts/test/test_compliance_port.py`, `scripts/test/test_compliance_checks.py`, `agentsmith/test/test_compliance_runtime.py`, `portal/test/complianceState.test.ts`, `portal/test/signInPolicy.test.ts`.
Mutation-checked: yes, by hand; thirty-six mutants of the guards, all killed.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`, `templates/governance.json`, `THIRD_PARTY_LICENSES.md`.
Gates run: ruff; mypy (locked lint set); py_compile; the repo-tree check; `process_gate.py artifacts`; the whole of `scripts/test` and `agentsmith/test` on a venv synced to the lock against a real Postgres: 2605 passed, 10 skipped; portal `tsc`, `npm test` (136), `test:db` (85), production build; `pip-audit`, `npm audit`, Bandit.

Levers reviewed: `declared-vs-enforced`, `implemented-not-invoked`, `single-source-of-truth`, `gate-integrity`, `failure-is-not-a-result`.

KG query: kg:e03eeede85c0
