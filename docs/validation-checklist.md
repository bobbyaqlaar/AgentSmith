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

## Step 3 — Run the gates CI lists, against the state CI will see

`run-the-gates-ci-lists` (Group 4): enumerate the actual steps in
`self-test.yml` (framework) or the tenant's own `ci.yml`, and run that list —
not the subset you remember, and not against a working tree that differs from
what CI will check out. At minimum, for this framework:

```bash
python3 -m pytest -q                              # full suite
ruff check scripts/ runtime/                       # lint
mypy                                                # type check — CI pins python_version;
                                                     # if local mypy disagrees, check that first
python3 scripts/verify_system.py --check-kg        # Knowledge Graph freshness
```

For a tenant repo, the equivalent is `make test`, the F-scenario drivers, the
security harness in `--strict` mode, and whichever judged eval suites the
branch's changes touch — see the tenant's own `README.md` for what runs on a
push versus what's gated behind a cron or `workflow_dispatch`.

Regenerate the Knowledge Graph (`--check-kg`) whenever the change adds or
removes a top-level symbol — a stale graph fails the same gate CI enforces,
and it is cheaper to catch here than in a second round-trip through CI.

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

Tests added/updated:      ____
Mutation-checked:          yes / no — why not, if not
Fixtures re-pinned:        yes / no / n/a
Gates run locally:         list them, and confirm the tree matches what CI sees
```

A gap declared here and never revisited is `backlog-discipline`'s job to
catch, not this document's — file it, with the trigger that would bring
someone back to it.
