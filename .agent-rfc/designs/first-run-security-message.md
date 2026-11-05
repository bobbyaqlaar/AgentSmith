---
status: active
scope:
  - agentsmith/cli.py
  - fixtures/security/templates/risk_register.yaml
  - fixtures/security/templates/agency_manifest.yaml
  - fixtures/security/templates/nist_profile.yaml
  - fixtures/security/templates/tool_allowlist.yaml
  - scripts/security/runners/_shared.py
  - scripts/security/runners/delegating.py
  - scripts/security/runners/risk_register.py
  - scripts/mutation_check.py
  - scripts/test/test_security_first_run.py
  - .agent-rfc/fixtures/knowledge_graph.json
---
# A new repository's red security job says it is expected, and what to write

## Problem

A repository from `agentsmith tenant init` fails its Security job on the first push, by design: its risk register and agency
manifest are placeholders. Reproduced on 4.0.0, the job says:

- `risk register still contains un-edited template entries (RISK-EXAMPLE-001) — replace them with organisation-owned risks`
- `agency manifest still contains the shipped placeholder (1 entry/entries) — nothing has been declared`

Neither names the file, says a new repository starts here, or says what to write. `tenant init` does warn, but above a list of
about 30 files, and the closing lines are about the commit. The templates' comments still say "Copy to", though `tenant init`
has already copied them.

The way to green is short. In a throwaway repository, replacing both files made `security check` exit 0, and a plain commit took
them with no design, because `.agent-rfc/security/` is not gated.

## Approach

The control still fails. Only a pass passes; this changes what the failure tells you.

- Each message names the file relative to the repository, says a new repository starts here, and lists the fields to write.
- The templates say what to write, and that the check reads the declaration, not whether the approval really happens.
  The other two templates lose the same stale "Copy to" line.
- `tenant init` moves its warning to the closing lines, after the commit command, with the local check command. It prints only
  when the placeholders were written by this run.

Existing tenants' files are never overwritten, so only new repositories get the new comments. The messages reach everyone.

## Pillars

- P1 applies — `.agent-rfc/designs/first-run-security-message.md` records the reproduced messages and the tested way to green.
- P2 n/a — no dependency or structural change.
- P3 n/a — no traced code path changes; only message text.
- P4 applies — `scripts/test/test_security_first_run.py` asserts each message, that the shipped templates still fail, and that the closing note follows what was written.
- P7 n/a — no stack-specific rule changes.
- P8 n/a — no telemetry wiring changes.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — the messages show a path this code built and an id already reported; `.githooks/process-gate` flattens the line for annotations as before.
- P12 n/a — no secret is read or written.
- P13 applies — `scripts/mutation_check.py` gains five mutations in `security_contract`, covering the messages, the path shown and the closing note.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node; `fixtures/security/templates/risk_register.yaml` keeps its sentinel id, so detection does not move.
- P15 applies — `scripts/security/runners/delegating.py` and `scripts/security/runners/risk_register.py` still return fail: "expected" explains a red job and never turns it green.
- P16 applies — `agentsmith/cli.py` prints the files to edit and the command that checks them locally, so the repair is known before the first push.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the template now says the check reads the declaration and does not enforce the approval.
- `test-the-contract` — the test runs the real controls on the real shipped templates, not a copy of the text.
- `when-the-fallback-fails` — a path outside the repository is shown whole rather than raising.
