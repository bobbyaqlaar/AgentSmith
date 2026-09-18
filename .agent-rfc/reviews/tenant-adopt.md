# Review — an existing repository comes under the gates without losing what it has

Design: `.agent-rfc/designs/tenant-adopt.md`. Owner request, 2026-09-18: "tenant adopt", with the
vendoring fix proposed alongside it.

**Built evidence (2026-09-19):**

- **Failing tests first.** `scripts/test/test_hook_chain.py` and `scripts/test/test_tenant_adopt.py`
  were written before `runtime/adopt.py` and `.githooks/chain`; the first run failed on the
  missing chain script.
- **Two defects found while building, both now in the design:**
  - the vendoring test found that a vendored copy of the gate resolved `@framework/` to the
    tenant's own repository and refused the first commit for a missing registry — latent since
    G7, because no tenant had been both vendored and gated;
  - the end-to-end run below found that adopt chained the machine's `post-checkout` and
    `post-commit`: a `git checkout -- <file>` vendored 44 scripts and seven workflows into the
    adopted repository, and every commit re-mapped the graph. Adopt now leaves those two out
    and says so in the plan; `test_the_machines_provisioning_hooks_are_not_chained_into_an_adopted_repository`.
- **The journey, with the real CLI**, in a scratch repository created by this Mac's own `git init`
  (the machine's hooks in `.git/hooks`): the plan printed and nothing written without `--yes`;
  adopt with `--architecture clean`; the printed commit went in on a non-root commit with
  `ℹ️ Review: n/a: generated scaffold — 9 gated file(s) match .agenticframework/scaffold.json, as
  agentsmith tenant adopt wrote them`; a checkout left the tree clean; the next change to
  `shop/cart.py` was refused for a missing `Design:`.

## Pass 1 — findings: 8

- `failure-mode-visibility` — **finding:** the plan did not list everything adopt writes:
  `.agents/skills/*/skill.md` and `.agent-history.log` appeared only in the result.
- `failure-mode-visibility` — **finding:** an adoption that stopped partway could not be re-run — the
  refusal for an already-adopted repository cannot tell an uncommitted `process-gates.json` from
  a committed one, and says to change it under a design.
- `ambiguous-signals` — **finding:** a `core.hooksPath` naming a directory that does not exist was
  reported as prior hooks "kept running behind the gates".
- `one-catalog` — **finding:** a rule file AgentSmith generated earlier (the old opt-in path writes
  them) would get the same rules appended a second time inside the block.
- `gate-integrity` — **finding:** `tenant init` ran whatever `post-checkout` the prior directory
  held and had the manifest vouch for everything it created; the design says the machine's hook.
- `merge-the-right-copy` — **finding:** an `.agent-rfc/designs/adoption.md` the repository
  already has would be overwritten, though the plan says `create`.
- `docs-match-behaviour` — **finding:** the per-clone setup in `docs/process-gates.md` did not say a
  clone must name `agentsmith.chainHooksPath` again — it is local configuration.
- `validate-on-the-receiving-side` — **finding:** a malformed existing `.claude/settings.json` crashed adopt after
  it had written the config and the hooks, leaving a half-adopted repository.

Fixed: the plan lists `.agent-history.log` and every skill file; an uncommitted
`process-gates.json` is told it looks like an unfinished adoption and how to clear it; a hooks
path that does not exist is not prior hooks; a rule file whose own opening lines say AgentSmith
generated it is regenerated whole (`regenerate` in the plan) instead of merged into; `tenant init`
runs the prior `post-checkout` only when it is the machine's (`is_machine_hook`); an existing
`adoption.md` and a malformed `.claude/settings.json` or `.cursor/hooks.json` are refused in the
plan, before anything is written; the per-clone setup names `agentsmith.chainHooksPath`.
**These fixes were written before their tests** — the tests came after, so each fix was also added
to the `tenant_adopt` suite in `scripts/mutation_check.py` to show its test can fail.

**Mutation checks** (`python3 scripts/mutation_check.py tenant_adopt`, the curated catalogue, so
the evidence stays runnable): first run, 13 mutations, 12 caught. The survivor — `|| exit $?`
removed after the gate in `.githooks/commit-msg` — is an equivalent mutation: the hook runs under
`set -e`, so a failing gate exits anyway. It was replaced by the real break, the chain running
before the gate, which `test_a_message_the_process_gate_refuses_never_reaches_the_prior_commit_msg`
(written for it: a well-formed subject the gate itself refuses) must catch.

## Pass 2 — findings: 3

Every lever over the final diff, `docs/process-gates.md`, the manual's tenant sections, the
CHANGELOG, and the gates CI runs (`run-the-gates-ci-lists`).

- `run-the-gates-ci-lists` — **finding:** the repository-tree check in Self-Test fails on
  `runtime/architectures.py`, added by the previous slice (`a618e46`, not yet pushed), and would
  fail on `runtime/adopt.py` once tracked. Both are now in `docs/DESIGN.md`'s tree; the check,
  run locally from the workflow, passes.
- `single-source-of-truth` — **finding:** the gate's hook names were a tuple in both
  `runtime/cli.py` and `runtime/adopt.py`.
- `test-that-pins-a-defect` — **finding:** a `tenant init --force` re-run stopped vouching for
  files an earlier run wrote and it now skips because they exist — vendored code, and the
  composite actions under `.github/**` — so that repository's first commit would be refused for
  its own scaffold.

Fixed: `GATE_HOOKS` lives in `runtime/cli.py` only, and `runtime/adopt.py` imports it. A re-run's
manifest keeps every file an earlier manifest listed while it is byte-for-byte what was recorded —
`test_a_forced_rerun_still_vouches_for_what_the_first_run_wrote`, which failed before the fix (the
composite actions dropped out of the manifest; the defect predates this slice).

**Final mutation run:** 18 mutations in the `tenant_adopt` suite, all caught — the pass-1 and pass-2
fixes included, each shown able to fail its test.

## Pass 3 — findings: 0

The pass-2 fixes and everything they touch. Considered and declined:

- The carry-forward vouching for a file an earlier run wrote that the user has since deleted and
  recreated identically. Identical bytes are what the hash vouches for; how they got there does
  not change what is committed.
- Committing `.githooks/chain` with its executable bit. My shell guard refuses `chmod` on the
  gate's own files; every caller runs it with `bash`, and `tenant init`/`adopt` copy it with
  mode 755. It works either way, which is why the callers were written that way.
- A separate audit event for adoption. `tenant_created` carries `"adopted": true`; a new event
  type touches the portal's event list for no reader who needs the difference yet.

**Stated limits:**

- the adoption manifest is not signed — the same limit as the scaffold's, now on the commit that
  arms the gates rather than the root commit;
- `agentsmith.chainHooksPath` is local configuration: each clone sets it again (`docs/process-gates.md`
  › Setup, once per clone);
- husky re-points `core.hooksPath` on install — warned, backlogged;
- the gates workflow's default ref, `v1.3.0`, predates the arming rule, so an adopted repository's
  first CI run fails the adoption commit until a release carries it — backlogged as **Now**.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — a command-line change; the plan and results were read end to end
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_tenant_adopt.py (20), scripts/test/test_hook_chain.py (11),
                          scripts/test/test_scaffold_review.py (+3), scripts/test/test_installed_runtime_tenant.py (+1),
                          runtime/test/test_architectures.py (+3), scripts/test/test_process_gate.py (1 re-pinned)
Mutation-checked:          yes — `scripts/mutation_check.py tenant_adopt`, 18 mutations, all caught
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:9a7dfb919371
Gates run locally:         ruff, the suites above, the repo-tree check from Self-Test, the full pytest run
                          (1844 passed, 10 skipped), the end-to-end journey with the real CLI
Declared gaps:             (1) the adoption manifest is not signed; (2) the gates workflow's default ref
                              predates the arming rule until the next release; (3) husky re-points
                              core.hooksPath on install
```
