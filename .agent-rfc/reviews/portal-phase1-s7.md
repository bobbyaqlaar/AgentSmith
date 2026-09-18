# Review — portal phase 1, S7: CI sends the gate's record

Design: `.agent-rfc/designs/portal-phase1.md` (S7, corrected while building — see finding 1).

**Built evidence (2026-09-18):**

- **Failing tests first.** `scripts/test/test_send_dev_record.py` (8) was written before
  `scripts/send_dev_record.py`, against a local HTTP server standing in for the portal.
- **End to end over HTTP.** `process_gate.py ci --json` on AgentSmith's last three commits, then
  `send_dev_record.py` against the running dev portal with a real ingest token: "3 commit(s)
  stored", exit 0. The same record with a wrong token: "the portal refused the gate's record
  (401): unknown or revoked ingest token", exit 1.
- **Self-Test** writes the record and sends it after the gate, whatever the gate decided. The
  gates table in `docs/validation-checklist.md`, generated from the workflow tags, was regenerated
  for the new gate command; the gate falls back to `/tmp` for the record where `$RUNNER_TEMP` is
  not set, so `agentsmith gates run` still runs it locally.
- **Mutation checks (each reverted):** eight — an unconfigured repository failing the build, a
  refusal only warning, an outage failing the build, plain `http` allowed, no chunking, designs
  sent with every part, the token printed in the refusal message, no run link. Seven caught on
  the first run; the survivor is finding 3.

## Pass 1 — findings: 3

- `declared-vs-enforced` — **finding, in the design:** S7 said to add the send step to "the
  process-gates job in `workflow-templates/`". There is no such job — tenant CI templates do not
  run the process gate at all; only repositories that adopted it by hand do. Adding one changes
  every tenant's CI, the scratch tenants' included, whose generated commits carry no design
  trailers. The design is corrected, the sender is a script any gate job can call, the manual
  gives the two lines to add, and the template job is a backlog item with its own design to come.
- `environment-parity` — **finding:** the first cut wrote the record to `"$RUNNER_TEMP/…"`. The
  gate step is tagged for `agentsmith gates run`, which runs it on a laptop where `$RUNNER_TEMP`
  is unset — the record would have gone to `/dev-record.json` and the gate would have crashed on
  a permission error. `${RUNNER_TEMP:-/tmp}`.
- `test-that-cannot-fail` — **finding:** mutation "token printed" survived. The plain-`http`
  refusal is the one message that mentions the token's destination, and only the success test
  checked the output for the token. The refusal test checks it now.

## Pass 2 — findings: 0

Every lever over the final diff, the manual's new section and the regenerated gates table.
Considered and declined:

- Sending from KYC Sentinel and OTS now. Each runs its own gate job and would need its own design
  and its secrets set by the owner; the manual's two lines are what they would add.
- Retrying a failed send. The next push sends the range again, and the ingest is an upsert on
  (app, commit); a retry loop inside a CI step would add minutes for nothing the next run does
  not do.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen in this slice
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] checked

Tests added/updated:      scripts/test/test_send_dev_record.py (8)
Mutation-checked:          yes — eight, each reverted; one survivor became finding 3
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json; the gates table in
                          docs/validation-checklist.md
KG query:                 kg:f209e4592560
Gates run locally:         ruff, the sender tests, test_gate_steps.py, the end-to-end send
Declared gaps:             the tenant CI templates run no process-gates job — backlog
```
