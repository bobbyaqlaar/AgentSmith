# Review — a sync refreshes what it owns, and never clobbers what it does not

Design: `.agent-rfc/designs/sync-merged-files.md`, fourth slice of
`.agent-rfc/designs/governance-providers.md`. Owner, 2026-09-24: "next slice".

**Built evidence (2026-09-24):**

- **Failing tests first.** Five new cases in `scripts/test/test_framework_sync.py` (15 in total)
  failed before `ownership` and the three refreshes existed.
- **Ownership is the manifest's answer, and it has three values**: refreshed, left alone and named,
  left alone silently. `test_a_file_the_tenant_edited_is_left_alone_and_named` proves the middle
  one, which is the case that would otherwise lose someone's work.
- **A tenant's own edits do not freeze their gate wiring:** the rules block and the `hooks` key in
  `.claude/settings.json` are regions the framework owns, refreshed whatever changed around them;
  `test_a_tenants_own_settings_do_not_freeze_their_gate_wiring`.
- **The gates workflow follows the framework**, `ref:` included, so an upgraded tenant runs the new
  provider in CI.
- **One renderer**: `generated_rules` in `runtime/adopt.py` is what both `adopt` and `sync` read, so
  they cannot disagree about what the rules say.
- **Mutation checks:** the `framework_sync` suite now carries 8, all caught.

## Pass 1 — findings: 3

All three were my tests being wrong about the world, and the system said so.

- `test-the-contract` — **finding:** my "older framework" fixtures staged their state with
  `git commit --no-verify`, and the sweep refused the next commit until the bypass was repaired —
  correctly. An older framework's state is staged by a commit that *passes*: the manifest vouching
  for what is there, which is exactly what its own sync commit looked like.
- `merge-the-right-copy` — **finding:** judging `.claude/settings.json` by its whole hash would
  freeze a tenant's gate wiring the moment they edited their own permissions. It is a file with a
  region we own, like the rule files, and is now treated that way. The mutation that removes the
  distinction is caught.
- `test-that-cannot-fail` — **finding:** the IDE-wiring test asserted a tenant's `permissions`
  survived a sync in a fixture that never had any. The fixture is now a repository that already
  uses Claude Code, which is the case that matters.

## Pass 2 — findings: 1

- `denied-vs-missing` — **finding:** the tenant's own edit in the `left alone` test was 23 gated
  lines, which the gate refused as too large for a plain `n/a` review — so the test was proving the
  size rule, not the ownership rule. Their edit is now one line, as a real tuning change would be,
  and the test proves what it claims.

## Pass 3 — findings: 0

Ownership, the three refreshes, the renderer extraction, and the docs. Considered and declined:

- Teaching `sync` to merge a tenant's edits with the framework's new version. A three-way merge of
  a file nobody asked us to merge is how work gets lost; naming it and letting the tenant decide is
  the honest answer.
- Refreshing a file the framework wrote that the tenant has since **deleted**. `ownership` writes it
  back, because the manifest says it is ours and a missing gate config is not a decision — that is
  the same reasoning as the hooks.

**Stated limits:**

- `.cursor/hooks.json` is rendered whole, so a tenant who edits it owns it from then on and their
  gate wiring there goes stale — named in the plan, but not merged;
- the manifest is still unsigned, as for the scaffold;
- a tenant runs `sync` itself; nothing opens a pull request for it.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — one renderer for the rule files, shared by
                                          adopt and sync
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — command-line output; the plan's wording was read
Group 6 · Signal integrity            [x] checked — three ownership answers stay distinct
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      scripts/test/test_framework_sync.py (15)
Mutation-checked:          yes — framework_sync, 8 mutations, all caught after two test fixes
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:54a99067e6b0
Gates run locally:         ruff, mypy in a clean environment, the sync, adopt, scaffold and gate
                          suites, and the full pytest run
Declared gaps:             (1) .cursor/hooks.json is all-or-nothing; (2) the manifest is unsigned;
                              (3) a tenant runs sync itself
```
