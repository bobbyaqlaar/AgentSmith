# Review — governance enforcement, G7 (a tenant governed from its first commit)

Design: `.agent-rfc/designs/governance-enforcement.md` § G7, with the amendment written before
this code: the extra modes are provisioned `off`, arming is part of provisioning, and `--governed`
answers with a list rather than a boolean.

**Built evidence (2026-09-18):**

- **Failing tests first.** `scripts/test/test_governed_tenant.py` (23) was written before any of
  it; 17 failed on the first run, and the scaffolding fixture found three real gaps in the order
  it hit them: `generate-ide-config.py` was being run without `--rules-file`, so a tenant got no
  rule files; `map_codebase.py` wrote nothing in a repo with no code, so the "committed graph"
  was not committed; and the launcher could not be found from a tenant whose `HOME` has no
  framework install, which is what `AGENTSMITH_DIR` is for.
- **Provisioning is arming.** `core.hooksPath` is set by `tenant init`, because hooks that are
  present and unarmed are the failure this programme exists to end — and a mutation that copies
  the hooks without arming them is caught.
- **Pillar 5's log is written by the hook that has the fact.** The stop gate appends when it
  blocks; the sweep appends when it finds a commit that never met a gate. Unresolved `MAJOR` JSON
  lines, which is the shape `agentsmith check` and session start already read, so there is one
  reader.
- **Mutation checks (each reverted):** eleven — hooks copied but not armed, the config not
  written, a tenant starting at `enforce` everywhere, the scaffold overwriting a tenant's own
  file, a missing piece not reported, disarmed hooks passing, a gates run from another commit
  counted as evidence, never having run the gates passing, the history line arriving resolved, the
  same fact appended every turn, and the stop gate writing nothing. All eleven caught.

## Pass 1 — findings: 1

- `ambiguous-signals` — **finding:** the first `--governed` counted "never run the gates here"
  among the provisioning gaps, so a **freshly scaffolded tenant failed its own scaffolding check**
  with a list that mixed "this file is missing" and "nothing has been run yet". Those are
  different facts and they send someone to fix different things. The check now reports
  provisioning gaps and evidence gaps separately, and a new tenant reads "provisioned, not yet
  proven — the controls are in place and armed", with the command to run.

## Pass 2 — findings: 0

Every lever over the final diff: the provisioning list, the arming, the mode defaults, the
`--governed` output, the gates-run record and the history writer. Considered and declined: having
`tenant init` run the gate suite itself so a new tenant passes `--governed` immediately. It would
be slow, it would fail in a repo with no tests, and it would make the check's evidence something
the scaffold manufactured rather than something the tenant did.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen; the surface is a CLI and a check
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_governed_tenant.py (23); the fixture repo vendors
                          scripts/gate_history.py
Mutation-checked:          yes — eleven, each reverted, all caught
Fixtures re-pinned:        yes — .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:bb8dbc34e4f2
Gates run locally:         ruff, the full pytest suite, --check-kg, `process_gate.py pillars`,
                          the hook-config and gates-table drift checks
Declared gaps:             (1) only Claude Code's and Cursor's hook configs are provisioned —
                              the other four have no verified config schema (G2a);
                          (2) the extra modes are provisioned `off`, so a new tenant is
                              governed by the design and review gates and adopts the rest
                              deliberately;
                          (3) `--governed` checks that the controls are present, armed and
                              exercised; it does not re-derive whether each one is CORRECT —
                              that is what the gates themselves do;
                          (4) the security-posture placeholder check the design mentions is
                              left to `verify_system`'s existing security modes rather than
                              duplicated here.
```
