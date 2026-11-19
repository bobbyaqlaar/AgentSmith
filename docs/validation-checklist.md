# Validation & test checklist — after the build, before merge

**Phase:** post-build, pre-merge. Run this once the change works, before
opening a PR or claiming a slice done. Its design-phase counterpart is
[`design-review-checklist.md`](./design-review-checklist.md) — that one is
read going in so fewer findings reach this stage; this one is the gate
everything still has to clear.

## What this is, in industry terms

This is AgentSmith's **Definition of Done** — the code-review and test
sign-off checklist most engineering orgs keep, scoped to this framework's own
earned rules rather than generic boilerplate. It has four steps, in order.
Steps 1 and 4 point at [`review-levers.md`](./review-levers.md) rather than
restating it: the levers are the canonical rule set, and this document does
not keep a second copy of them — the same `single-source-of-truth` lever it
asks you to check elsewhere.

---

## Step 1 — Work down `review-levers.md`, group by group

Open [`review-levers.md`](./review-levers.md) and go through every lever that
bears on the branch, in order, against the CHANGE — not against the files you
happened to edit (`review-the-branch`). For each lever: does it apply here,
and if so, does the change satisfy it? A lever that doesn't apply is skipped,
not silently passed — say so if you're reporting findings.

Two levers govern HOW you run this step, not just what it checks:

- `grep-for-siblings` — when a lever finds something, search for the same
  pattern elsewhere before calling the pass done. The sibling that gets
  missed is the one in another package, another language, or another repo.
- `expect-re-review` — a second pass, or a pass by someone who didn't write
  the change, catches what the first one's familiarity hides. If the user
  asks for multiple passes, keep going until a pass finds nothing new — that
  is the actual stopping condition, not a fixed count.

If the change touches a screen or a control, Group 5 (Intuitive UI) is not
optional — walk every lever in it against the actual rendered screen, not
just the component source. If the change touches a cookie, bearer token, or
any client/server session, Group 7 (Auth & session integrity) is equally not
optional.

If the change takes outside input, holds a secret, runs a program or changes a
build, Group 8 (Security engineering) is walked. If it stores personal or
government data, makes an AI judgement or produces audit evidence, Group 9
(Regulation & compliance) is walked. If it adds a path whose size grows with
use, Group 10 (Code optimisation) is walked.

## Step 2 — Testing obligations

Pillar 4 (Testing Guardrails) and Pillar 14 (Fixture and Baseline Drift) in
`templates/agent-rules.yaml` are the standing rules; this step is how to
discharge them concretely:

1. **Every logical change has a test.** Not a smoke test that imports the
   module — a test that would fail if the change were reverted. See
   `test-that-cannot-fail` and `test-the-contract` in Group 6: a test that
   passed before the fix existed is not evidence of anything.
2. **Mutation-check anything load-bearing.** Revert the fix in a scratch copy
   and confirm the new test fails. If it doesn't, the test isn't pinning the
   defect — it's pinning something adjacent.
3. **A deliberate behaviour change re-pins its fixtures in the same commit**
   (`Fixture and Baseline Drift`, Pillar 14) — check WHICH projection of the
   output each fixture holds before regenerating; different suites can pin
   different views of the same result.
4. **UI changes get the mechanical Group 5 levers checked as tests where a
   test can check them, and a manual verification note where it can't:**
   - `no-double-submit` — a test that fires the action twice in quick
     succession and asserts one effect, not two.
   - `denied-vs-missing` — a test per role/tenant combination asserting the
     two screens are actually different, not the same string twice.
   - `failure-is-not-a-result` — a test for each of empty / unavailable /
     zero, asserting three different renderings.
   - `keyboard-and-screen-reader-operable`, `works-at-real-viewport-sizes`,
     `matches-the-existing-component-language` — these are usually not
     mechanically testable from this repo's tooling. Say so explicitly in
     the sign-off below rather than silently skipping them: an unchecked
     lever and a satisfied one must not read the same way
     (`ambiguous-signals`, Group 6, applied to this checklist itself).
5. **Tests stay off live targets.** Test set-up refuses to start unless every
   connection setting the code might read points at a test target, including
   the one the application prefers (`tests-cannot-touch-live`, Group 6).
6. **Reliability, as tests** (Groups 2 and 6):
   - Make the save fail after the action is prepared, then assert that no mail,
     no success response and no file was produced.
   - Deliver one request twice and out of order, then assert a single effect.
   - Make a dependency answer for some items only, and another that is down.
     The first must end partial or failed; the second must record "could not
     determine", never a result.
7. **Security, as tests** (Group 8):
   - Send oversize, wrong-type, encrypted, malformed and control-character
     inputs through every route the input can arrive by.
   - Check that the application's database account is refused destructive
     statements, and that a child process gets no secrets and is killed at its
     time limit.
   - Compare timing and messages for known and unknown usernames.
   - Run the hostile-document suite against the real model on a schedule, not
     only against a stand-in.
8. **Compliance, as tests** (Group 9):
   - Attempt to update, delete, truncate, shorten or reset the audit anchor, and
     assert refusal or detection. Plant a gap in the chain and assert the
     integrity check fails.
   - Request a non-permitted endpoint and assert refusal unless the override is
     set; setting it must write an audit record.
   - Assert that expired items are actually removed by the scheduled routine,
     and that no result reaches a customer without an approval.
   - Restore a backup taken before the latest schema change and confirm the
     audit check still passes.
9. **Performance, as measurements** (Group 10): time each changed path at a
   realistic volume, record before and after with the date, and count queries
   where the tooling allows.
10. **Manual-only levers.** Anything above that cannot be automated here is
    listed in the sign-off with how it was checked.

## Step 3 — Run the gates CI lists, against the state CI will see

`run-the-gates-ci-lists` (Group 4): run the list CI actually has, not the
subset you remember, and not against a working tree that differs from what CI
will check out. One command runs it:

```bash
agentsmith gates run
```

It reads the steps tagged `# agentsmith:gate` in `.github/workflows/`, runs
each one here, and prints three counts — passed, failed and **skipped**, with
the reason for every skip (a tool that is not installed, a service container CI
starts, an expression only CI can answer). A skipped gate is never reported as
a passed one. `agentsmith gates list` shows the table below without running
anything, and `--only <text>` runs the ones whose name matches.

It runs each step's script with bash in your working tree: it does not
reproduce the runner image, the setup steps before it, or a service container.
It answers "does this gate pass here", which is the question before a push —
CI stays the authority.

<!-- BEGIN agentsmith:gates -->

<!-- Generated by scripts/generate-ide-config.py --gates from the `# agentsmith:gate` tags. Do not edit by hand. -->

| Gate | Workflow · job | Runs | Locally |
|---|---|---|---|
| Every gated commit has a design and a clean review | `.github/workflows/self-test.yml` · Process gates (design + review) | `python3 scripts/process_gate.py ci --base "$BASE" --head "$HEAD_SHA" --json "${RUNNER_TEMP:-/tmp}/dev-record.json"` | yes |
| mutation_check.py (curated — the properties we chose to defend) | `.github/workflows/self-test.yml` · Curated mutations (shard ${{ matrix.shard }}/4) | (script) | yes |
| ruff (lint config lives in pyproject.toml) | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | (script) | yes |
| mypy (shipped runtime only — see pyproject.toml for the scope) | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | (script) | yes |
| py_compile sweep | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | `find scripts agentsmith examples -name "*.py" -print0 \| xargs -0 -n1 python3 -m py_compile` | yes |
| docs/DESIGN.md repo-tree drift check (top level + key sub-trees) | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | `pytest scripts/test/test_design_tree_drift.py -q` | yes |
| Redaction compliance (staging + production profiles) | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | (script) | yes |
| Commit guardrails / enterprise RFC checks, through the gate | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | `python3 scripts/verify_system.py --check-hooks` | yes |
| verify_system.py --check-kg (Knowledge Graph, docs/PRODUCT_ARCHIVE.md P10a) | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | `python3 scripts/verify_system.py --check-kg` | yes |
| On-prem deploy template (Compose + Helm syntax) | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | `python3 scripts/verify_system.py --check-onprem-deploy` | needs helm |
| The release installs, and its first commits pass | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | (script) | yes |
| A tenant on the last release upgrades to this commit | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | `bash scripts/check_tenant_upgrade.sh` | yes |
| Delivery evidence pack script | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | `python3 scripts/delivery_evidence.py` | yes |
| Unit tests — delivery model + fairness + input guardrail | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | (script) | yes |
| Every curated-mutation shard passed | `.github/workflows/self-test.yml` · Python scripts/runtime/examples | (script) | yes |
| pytest (agentsmith/test/) | `.github/workflows/self-test.yml` · Python runtime behaviour tests (Postgres-backed) | `pytest agentsmith/test/ -v` | needs services |
| pytest (scripts/test/ — shadow eval sampling) | `.github/workflows/self-test.yml` · Python runtime behaviour tests (Postgres-backed) | `pytest scripts/test/ -v` | needs services |
| verify_system.py --check-idempotency | `.github/workflows/self-test.yml` · Python runtime behaviour tests (Postgres-backed) | `python3 scripts/verify_system.py --check-idempotency` | needs services |
| verify_system.py --check-dlq | `.github/workflows/self-test.yml` · Python runtime behaviour tests (Postgres-backed) | `python3 scripts/verify_system.py --check-dlq` | needs services |
| bash -n / zsh -n syntax check | `.github/workflows/self-test.yml` · Shell scripts | (script) | yes |
| npx tsc --noEmit — the portal type-checks | `.github/workflows/self-test.yml` · Ops Portal (Next.js) | `npx tsc --noEmit` | yes |
| npm test — cross-tenant isolation (no DB required) | `.github/workflows/self-test.yml` · Ops Portal (Next.js) | `npm test` | yes |
| npm run test:db — audit log HMAC sign/verify + tamper detection | `.github/workflows/self-test.yml` · Ops Portal (Next.js) | `npm run test:db` | needs services |
| npm run build — the portal builds | `.github/workflows/self-test.yml` · Ops Portal (Next.js) | `npm run build` | needs services |
| The Ops contract, receiver side (against the live portal above) | `.github/workflows/self-test.yml` · Ops Portal (Next.js) | `python3 -m agentsmith.cli conformance --port ops --receiver http://localhost:3000/api/ops/ingest` | needs services |
| npm test — the in-app widget | `.github/workflows/self-test.yml` · In-App Widget | `npm test` | needs npm |
<!-- END agentsmith:gates -->

For a tenant repo, the equivalent is `make test`, the F-scenario drivers, the
security harness in `--strict` mode, and whichever judged eval suites the
branch's changes touch — see the tenant's own `README.md` for what runs on a
push versus what's gated behind a cron or `workflow_dispatch`.

Regenerate the Knowledge Graph (`--check-kg`) whenever the change adds or
removes a top-level symbol — a stale graph fails the same gate CI enforces,
and it is cheaper to catch here than in a second round-trip through CI.

### Release and handover readiness (when the change ships)

- The handover package holds only what an explicit include list names. No
  settings files, keys, data, undo copies or commercial documents unless named
  (Group 8, `handover-contains-only-the-program`).
- Every runnable instruction in the README and handover notes was run as
  printed on a clean machine (`runnable-docs`).
- Screenshots and manual text match the build (`docs-match-behaviour`).
- Defaults are secure: HTTPS on, a second factor on for privileged
  capabilities, no published default passwords, and a first-admin password that
  must change.
- The compliance register, model cards and DPIA reflect this release. Until an
  independent assessment is done, the assurance claim is "built to these
  controls, not yet audited against them" (Group 9, `honest-assurance`).
- A backup, restore and audit check has been run on this release
  (`move-and-restore-are-features`).

### Security and supply-chain gate status

Status as read from `.github/workflows/` on 2026-11-19. A row marked "Not in
CI" is a declared gap, not a pass.

| Gate | Status in this repository | Blocks on |
|---|---|---|
| Secrets scan over the change and history | Not in CI. A full-history scan was run by hand on 2026-11-05 (backlog, Stage 1 step 9) | any finding |
| Static security analysis | Bandit 1.8.6 runs in `supply-chain.yml` on AgentSmith's own code, at medium severity and above, with no baseline. Semgrep and Ruff `S` rules are not in CI | medium and above (Bandit) |
| Dependency audit | `supply-chain.yml`: `pip-audit==2.9.0` over the two lock files, with no severity filter; `npm audit --omit=dev --audit-level=high` over `portal` only (production dependencies) | any finding (pip-audit); high (npm) |
| SBOM | CycloneDX over `requirements.lock` only, in `supply-chain.yml`. Not the pipeline lock or the portal's npm dependencies. Not produced per tenant | — |
| Container image scan (Trivy) | Not in CI | to be set when added |
| Project rules as code (custom Semgrep or equivalent) | Not in CI | to be set when added |
| Model fingerprint check | Not in CI | any mismatch |
| Hostile-input evaluation, scheduled | Not in this repository's CI | any unsupported verdict |
| Docs and diagram drift | Present: `self-test.yml` runs `test_design_tree_drift.py` | any drift |

Any of these that a change depends on is written in the sign-off as
`gap: <backlog id>`, with the trigger that brings it back.

## Step 4 — Sign off

State, per group, one of: **checked / not applicable / declared gap**. A
declared gap is honest and does not block (`declared-vs-enforced`,
`gate-integrity`); an unstated one is the failure this whole document exists
to prevent.

```
Group 1 · DRY & shared code           [ ] checked  [ ] n/a  [ ] gap: ____
Group 2 · Quality / safety            [ ] checked  [ ] n/a  [ ] gap: ____
Group 3 · Architecture / hygiene      [ ] checked  [ ] n/a  [ ] gap: ____
Group 4 · Process                     [ ] checked  [ ] n/a  [ ] gap: ____
Group 5 · Intuitive UI                [ ] checked  [ ] n/a  [ ] gap: ____
Group 6 · Signal integrity            [ ] checked  [ ] n/a  [ ] gap: ____
Group 7 · Auth & session integrity    [ ] checked  [ ] n/a  [ ] gap: ____
Group 8 · Security engineering        [ ] checked  [ ] n/a  [ ] gap: ____
Group 9 · Regulation & compliance     [ ] checked  [ ] n/a  [ ] gap: ____
Group 10 · Code optimisation          [ ] checked  [ ] n/a  [ ] gap: ____

Defect kind and siblings checked: ____ (what the fix does NOT cover: ____)
Tests added/updated:      ____
Reproduced before fixing:  yes / no / n/a
Mutation-checked:          yes / no — why not, if not
Fixtures re-pinned:        yes / no / n/a
Performance measured:      before ____ / after ____ at volume ____ on date ____ / n/a
Security gates:            the table above — result, or "not yet in CI"
Compliance evidence:       register / model card / DPIA / audit test — or n/a
Manual-only levers:        listed, and how each was checked
Gates run locally:         list them, and confirm the tree matches what CI sees
```

The gate checks only Groups 1–7, and only the fields `Tests added`,
`Mutation-checked`, `Fixtures re-pinned` and `Gates run`, as listed in
`templates/agent-rules.yaml`. Groups 8–10 and the other fields are not gate-checked
yet: the reviewer checks them and records the result here. That is a declared
gap until the registry is extended.

A gap declared here and never revisited is `backlog-discipline`'s job to
catch, not this document's — file it, with the trigger that would bring
someone back to it.
