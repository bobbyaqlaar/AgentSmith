# Review — the front door describes the architecture that shipped

Design: `.agent-rfc/designs/public-front-door.md`. Owner, 2026-09-25/26: "Is documentation current?
Should we run one more review pass?" — then, on the answer, "rewrite the front door".

**Both questions had checkable answers, and both were no/yes.** The currency pass found four things
before any editing began; the rewrite then found three more in its own work, two of them live
defects that had nothing to do with documentation.

## Pass 1 — findings: 4

The currency pass, before any editing.

1. `grep-for-siblings` — **three surviving copies of a note about to become false.** `README.md:141`,
   `docs/UserManual.md:59` and `:1341` all said *"While this repository is private (until it is
   product-ready) the release URL below returns 404"*. The `public-provider-checkout` slice fixed a
   fourth at `:791` and missed these because its sweep grepped `AgentSmith is private` and these say
   `this repository is private`. A sweep that could not match its own siblings.
2. `declared-vs-enforced` — **going public unblocks the enforcement the gates have never had.**
   `docs/process-gates.md` stated as current fact that a private repository on a free plan has no
   branch protection, and `docs/PRODUCT_BACKLOG.md` carried "the process gates report a bad push;
   they cannot refuse one", trigger *"upgrading to Pro or making the repo public"*. Corrected, and
   the item marked **fired** with the action and whose call it is.
3. `docs-match-behaviour` — **`providers.json` appeared in no user-facing document.** The centre of
   the architecture closed out the day before, documented only in `contract/gate/v1/protocol.md` and
   in design records. Added to `docs/DESIGN.md`'s config table and the manual's adopt section, with
   `scaffold.json` beside it for the same reason.
4. `intuitive-journey` — **`README.md` documented only the vendored path**: `git init` → `touch
   .agenticframework/enabled` → `git checkout`. `tenant adopt`, `sync`, `gate` and `conformance`
   appeared nowhere in 306 lines. A visitor with an existing repository was told the wrong thing by
   omission.

## Pass 2 — findings: 3

The first two are on the README I had just written; the third is the one that mattered.

1. `ambiguous-signals` — I wrote "the git hooks **and the CI workflow** ask *that*". False, and it
   contradicted my own ports table two paragraphs below: `agentsmith-gates.yml` runs
   `process_gate.py ci` directly and resolves no provider. Replaced with an explicit paragraph
   saying the commit, push and CI gates are not in the contract.
2. `docs-match-behaviour` — the `providers.json` example was a fabricated simplification with `//`
   comments in a block tagged `json`. Replaced with what `providers_declaration()` actually writes,
   `_about` key included.
3. **`provenance-and-precedence` — a template fixed in the checkout did not reach a tenant.** I
   verified the README's Quick Start by *adopting a throwaway repository* rather than re-reading the
   templates, and the adopted repo's `agentsmith-gates.yml` carried the **bare** token while
   `agentsmith-sync.yml` carried the fallback. Cause: `_templates_dir()` prefers
   `~/.agent-framework/workflow-templates` over the checkout — under a docstring saying "the
   installed location first, then the checkout — **so a developer running from a clone gets their
   own templates rather than the machine's stale copy**", which is the reverse of what the code did.
   The install had a stale `agentsmith-gates.yml` and no `agentsmith-sync.yml`, which is exactly why
   one file got the fix and the other did not.

   `test-the-contract` compounds it: the emitted-artifact test existed —
   `test_the_gates_workflow_runs_the_gate_from_a_framework_checkout` — but asserted
   `"secrets.AGENTSMITH_READ_TOKEN" in workflow`, which the bare form satisfies. Strengthened to
   require the fallback.

## Pass 3 — findings: 2

1. `test-that-cannot-fail` — **the strengthened assertion could not fire.** The `legacy` fixture
   points `HOME` at an empty directory, so `~/.agent-framework` never exists and every adopt test
   resolves from the checkout whatever the order is. The suite was structurally blind to the defect.
   Replaced with a test that builds the condition the fixture removes — a HOME that *does* hold a
   stale install — and confirmed to fail against the old order.
2. `grep-for-siblings` — **`_actions_dir()` had the identical bug**, under a docstring saying "the
   same order, for the same reason, as `_templates_dir`", so fixing one would have left the
   cross-reference lying. And it was live rather than latent: on this machine the installed
   `github-actions/` held **three of five** composite actions — `install-python-deps` and
   `rollback-notify` were added to the checkout and never re-installed — so a tenant adopted here
   received workflows calling two actions that were never copied in. GitHub rejects the whole
   workflow at the first `uses:`, not the step. CI never saw it because the scratch tenants run
   `install-ai-stack.sh` first, so their install is never stale. Both resolvers fixed; the test is
   parametrised over both.

## Pass 4 — findings: 0

- Adopted a second throwaway repository: the tenant now receives the fallback and no "AgentSmith is
  private" line; both resolvers return the checkout's directories and all five composite actions.
- Removed the single-resolver precedence test the parametrised one made redundant (27 lines), folding
  the prose it uniquely carried into the survivor — `every-line-earns-its-place`, applied to my own
  Pass 3 work.
- Every claim in the new README section checked against the code rather than the design: the three
  contract events, the four `Decision` values, five conformance cases, `--provider` and `--yes` flag
  names, and that adopt writes no `scripts/` or `runtime/` into a tenant.
- ruff, mypy, the adopt/wiring/sync/cli suites (107), and the doc tests: green.

## Stated limits

- **The two flip-tied documentation fixes are verified; the flip is not done.** Closing
  `docs/PRODUCT_BACKLOG.md`'s release-download item needs an anonymous check (`curl -sI` a release
  asset with no credential) after the repository is public. It is annotated, not closed.
- **Requiring `process-gates` on `main` is the owner's action** and changes how this repository is
  worked in. Named, not switched on.
- **The stale-install defect had a second victim nobody has checked.** `install-ai-stack.sh` is what
  refreshes `~/.agent-framework`; anything else resolved from there has the same exposure, and this
  slice fixed the two resolvers it found rather than sweeping every reader of that directory.
- **README claims one thing no test can check**: that `agentsmith conformance` lets another platform
  self-certify. The suite runs and AgentSmith passes it; no third party has used it.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — one parametrised precedence test for two
                                          resolvers; the redundant one removed
Group 2 · Quality / safety            [x] checked — a stale machine install can no longer decide
                                          what a tenant receives
Group 3 · Architecture / hygiene      [x] checked — two docstrings that described the opposite of
                                          their code now match it
Group 4 · Process                     [x] checked — four passes; passes 2 and 3 found defects in
                                          the work of passes 1 and 2
Group 5 · Intuitive UI                [x] checked — the front door leads with the path most
                                          visitors need, and states the contract's boundary
Group 6 · Signal integrity            [x] checked — the ports table separates "resolved" from "a
                                          contract in place"
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_tenant_adopt.py — test_this_checkouts_copies_beat_the_
                          machines_installed_ones (2 cases, confirmed failing against the old
                          order), and the emitted-workflow assertion strengthened
Mutation-checked:          the precedence change was verified by reverting it and watching the test
                          fail, and end to end by adopting throwaway repositories before and after
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:ad5df03c6dc2
Gates run locally:         ruff, mypy in a clean environment, `agentsmith gates run` (13 passed,
                          0 failed, 6 need services), the full Python suite, and the doc suites
Declared gaps:             (1) the flip and the anonymous-download check are the owner's; (2) branch
                              protection is named, not enabled; (3) other readers of
                              ~/.agent-framework are not swept; (4) no third party has run the
                              conformance suite
```
