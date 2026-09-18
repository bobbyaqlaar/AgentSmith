# Review — portal phase 1, S1: `process_gate.py ci --json`

Design: `.agent-rfc/designs/portal-phase1.md` (S1). The specification it serves:
`.agent-rfc/designs/portal-control-plane.md`, approved by the owner on 2026-09-18.

**Built evidence (2026-09-18):**

- **Failing tests first.** `scripts/test/test_dev_record.py` was written before the code; six of
  its first seven failed (the seventh — no flag, no file — is a guard that must hold before and
  after).
- **One resolution, not two.** The trailer-to-text lookup that `check_change` did inline twice
  (design, review) is now `record_text`, and both the verdict and the record use it: a record
  cannot describe a different document from the one the gate judged. The refactor was verified
  on its own first — `test_process_gate.py`, 107 passed — before anything was added to it.
- **Mutation checks (each reverted):** twelve — every commit passes, notes dropped on an ungated
  commit, `before_adoption` not recorded, the design never described, an unresolved record
  omitted, the deviation hash taken over the wrong text, repairs not recorded, the file written
  only on success, `signed_off` always true, passes not read, the deviation kind lost, the head
  not resolved to a hash. Ten caught on the first run; the two survivors are finding 3.

## Pass 1 — findings: 3

- `ambiguous-signals` — **finding:** `_verdict` returned `not_gated` for an ungated commit even
  when its pointers produced report-mode notes, so the one fact worth showing about that commit
  was recorded as nothing. A note now makes it `passed_with_notes`, gated or not; test
  `test_findings_on_an_ungated_commit_are_not_recorded_as_nothing`. `before_adoption` had no test
  either; `test_a_commit_without_the_config_is_recorded_as_before_adoption`.
- `one-catalog` — **finding:** `design_summary` read pillar answers with `gate_models`' private
  `_ANSWER` pattern — a second reader of a format `check_pillars` owns. The parse is now
  `gm.pillar_kinds`, beside `check_pillars`, and reads with the same pattern.
- `test-that-cannot-fail` — **finding:** two mutations survived: `signed_off` forced true, and a
  deviation answer recorded as `applies`. Every fixture review was signed off and every fixture
  pillar applied, so neither value was ever tested against its other case.
  `test_an_incomplete_sign_off_is_recorded_as_not_signed_off` and
  `test_every_pillar_kind_is_recorded_as_answered`.

## Pass 2 — findings: 0

Every lever over the final diff. Considered and declined:

- A separate `dev-record` subcommand. It would run the gate a second time to describe what the
  first run decided — two runs can disagree (a force-push between them), and the design's point
  is that they cannot.
- Omitting author email from the record. It is in every commit already, and the portal needs it
  to say who authored a change and who approved a deviation.
- Recording the sweep's findings. CI checks every pushed commit, so an unrepaired bypass is a
  `failed` commit that no later `Repairs:` names; the portal can read that from these records.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen or control
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_dev_record.py (11)
Mutation-checked:          yes — twelve, each reverted; two survivors became finding 3
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:261b92bc87f4
Gates run locally:         ruff, the scripts suite (1086 passed)
Declared gaps:             nothing sends the record yet — S7
```
