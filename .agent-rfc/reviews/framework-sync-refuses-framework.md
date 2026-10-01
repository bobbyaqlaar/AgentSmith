# Review — framework-sync-refuses-framework

Design: `.agent-rfc/designs/framework-sync-refuses-framework.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 2

1. **The guard's realistic near-miss was untested.** The tests proved the guard
   fires on a framework and on this very checkout, but nothing proved it stays
   quiet in a *vendored tenant* — the one kind of repository that holds copies of
   framework directories. `upgrade` vendors `templates/`, which carries
   `templates/agent-rules.yaml`: one of the four markers. A later change that
   vendored a second (`workflow-templates/`, the installer) would make `sync` and
   `upgrade` refuse in every vendored tenant, and the suite would stay green.
   Added a test that gives the adopted tenant a vendored tree, the marker
   included, and asserts it still plans a sync — and that `looks_like_framework`
   finds exactly that one marker in it.

2. **`docs/process-gates.md` named where `sync` will not write and left this out.**
   Its sync section said an adopted repository is never vendored into; it said
   nothing about the framework's checkout. One sentence added beside it.

## Pass 2 — findings: 2

1. **Pass 1's near-miss test could not fail for the reason it gave.** It wrote the
   vendored layout by hand, so if `upgrade` began copying `workflow-templates/` or
   the installer, the test would have kept passing — a `test-that-cannot-fail`.
   Rewritten to vendor for real: `upgrade` runs from an install that carries every
   marker (asserted, so the premise cannot rot) into a vendored tenant, which must
   then carry `templates/agent-rules.yaml` and still not look like the framework.
   Proved by hand: with `upgrade` made to vendor `workflow-templates/` too, it fails
   on `looks_like_framework(root) is None`.

2. **Blank-line spacing around that test** — three before, one after. Fixed with the
   rewrite.

## Pass 3 — findings: 0

Re-read `runtime/sync.py`, `runtime/machine/upgrade.py`, the five tests, the two
mutations and every doc line against the levers.

- Each guard runs before anything is read beyond the markers, and before the
  prompt: nothing to undo when it fires.
- The CLI path is proved, not just the function: `agentsmith sync --yes --root`
  exits 2, says why on stderr, and the tree is byte-identical.
- The real checkout is recognised (`test_sync_recognises_this_very_checkout`), and
  only through `plan_sync`, which writes nothing — `upgrade` is never pointed at
  `REPO`, because without its guard it would write there.
- `upgrade`'s stand-in carries a `tenant.yaml` and an install to copy from, so the
  mutation that removes its guard writes — and is caught.
- The four existing callers of `looks_like_framework` are unchanged; the two-marker
  rule is unchanged.
- 184 tests across every suite that calls `upgrade` or `sync` pass, including
  `test_ai_stack_upgrade.py`, whose tenants were the ones the new guard could have
  broken.

## Sign-off

Group 1 · DRY & shared code — [x] checked — `looks_like_framework` reused as the single definition of "this is the framework"; no second marker list.
Group 2 · Quality / safety — [x] checked — five tests, including the near-miss that vendors for real; two mutations in `framework_sync`, all 13 caught; the near-miss test proved by hand.
Group 3 · Architecture / hygiene — [x] checked — the refusal lives in `plan_sync` and `upgrade`, the two entry points, not in the CLI wrappers, so every caller is covered.
Group 4 · Process — [x] checked — backlog row opened before the design, design before code, the row archived with this change; the exit-code row stays open.
Group 5 · Intuitive UI — [x] checked — both messages name what was recognised and what to do instead; no flag to learn.
Group 6 · Signal integrity — [x] checked — a refusal is exit 2 (`sync`) or 1 (`upgrade`) with its reason, never "Nothing to do.".
Group 7 · Auth & session integrity — [x] checked — no credentials, sessions or tokens touched.

Tests added: `scripts/test/test_framework_sync.py` — `test_sync_refuses_the_frameworks_own_checkout`, `test_the_sync_command_exits_2_and_writes_nothing`, `test_sync_recognises_this_very_checkout`, `test_what_upgrade_vendors_does_not_make_a_tenant_look_like_the_framework`, `test_upgrade_refuses_the_frameworks_own_checkout`.
Mutation-checked: `python3 scripts/mutation_check.py framework_sync` — 13 mutations, all caught, the two new guards included; the near-miss test by hand.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` rebuilt with `scripts/map_codebase.py`.
Gates run: `pytest` over test_framework_sync, test_ai_stack_upgrade, test_tenant_adopt, test_cli_install, test_ci_package_managers, runtime/test/test_cli and test_machine (184 passed); `ruff check .` (0.15.20); `mypy` (1.14.1); `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `grep-for-siblings`, `guards-must-be-able-to-fail`, `test-that-cannot-fail`, `failure-is-not-a-result`, `declared-vs-enforced`, `docs-match-behaviour`, `backlog-discipline`, `early-exit-keeps-the-record`.

KG query: kg:4ff19ae01394
