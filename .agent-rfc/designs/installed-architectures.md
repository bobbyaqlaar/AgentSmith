---
status: active
scope:
  - install-ai-stack.sh
  - runtime/cli.py
  - scripts/test/test_installer_templates.py
  - runtime/test/test_cli.py
  - runtime/adopt.py
  - scripts/test/test_tenant_adopt.py
  - .github/workflows/release.yml
  - scripts/test/test_release_artifact_contract.py
  - scripts/mutation_check.py
  - .agent-rfc/fixtures/knowledge_graph.json
---
# An installed machine has what `tenant init` and `tenant adopt` need

## Problem

`agentsmith tenant adopt ts-shop --architecture modular-monolith`, run from an installed machine
(not a checkout), fails with a traceback: `templates/architectures.yaml not found in
$AGENTSMITH_DIR, ~/.agent-framework or this checkout`. `install-ai-stack.sh` copies
`templates/agent-rules.yaml` and `templates/governance.json` into `~/.agent-framework/templates/`
by name, and `architectures.yaml` — added with `tenant init --architecture` — was never added to
that list.

So `--architecture` works only where `AGENTSMITH_DIR` points at a checkout, which is how every
test and every rehearsal ran it. It is broken for `tenant init` too, the command it was built for.
Found on the first run of `tenant adopt` from the installed CLI (2026-09-23).

The second half: the failure is a Python traceback. The command knows how to say what is missing —
`resolve_style` raises a `FileNotFoundError` naming the fix — and the CLI catches `ValueError` only.

### The gate hooks are not installed at all — so no tenant is gated

The same run, carried through: the adopted tenant's `.githooks/` was **empty**, `core.hooksPath`
pointed at it, and the next commit to gated code went in unchecked. `install-ai-stack.sh` writes
`hooks/` to `~/.git_templates/hooks`, and never copies `.githooks/` — the gate's own hooks —
anywhere; the release does not carry them either (`hooks.tar.gz` is `hooks/`). `install_gate_hooks`
copies each hook `if source.is_file()`, so with no source it copies nothing, arms
`core.hooksPath` regardless, and says nothing. The tenant then has neither the gates nor the
machine's hooks, because a hooks path overrides `.git/hooks`.

This has been true for every machine installed rather than run from a checkout since G7 armed
`.githooks`, for `tenant init` as much as for `tenant adopt`. Every rehearsal of both ran with
`AGENTSMITH_DIR` pointing at a checkout, which has `.githooks/` beside it.

## Approach

- **The installer copies `architectures.yaml`** beside `agent-rules.yaml` and `governance.json`,
  in the same block and with the same fallbacks, and says so in its message.
- **The installer copies `.githooks/`** into `~/.agent-framework/.githooks/`, as it copies
  `workflow-templates/`, and `release.yml` ships `githooks.tar.gz` so an install from a release
  has them too.
- **Nothing arms an empty hooks directory.** `install_gate_hooks` refuses when the framework has
  no `.githooks/` to copy: it leaves `core.hooksPath` alone and says which files are missing and
  how to fix it. `tenant adopt` checks before it writes anything, so a repository is never left
  half-adopted with its hooks disarmed.
- **`scripts/test/test_installer_templates.py`** reads every `templates/<name>.{yaml,json}` that
  `runtime/` and `scripts/` load by name, and fails when the installer does not copy it. The list
  is derived, not written down twice, so the next template added is covered by construction.
- **`tenant init` and `tenant adopt` catch `FileNotFoundError`** as they already catch `ValueError`
  and print `agentsmith: <what is missing and the fix>`, exiting 2 — no traceback.

### Vendored framework code is not the repository's to gate

The same run showed `tenant adopt` proposing `scripts/**` for a vendored tenant, where `scripts/`
is AgentSmith's own code copied in by `hooks/post-checkout`, not the tenant's. Gated, the next
re-vendoring would need a design and a review of framework code — the problem `tenant init`'s
vendoring fix was built to avoid. Detection skips a top-level directory that carries the
framework's own marker files (`scripts/run-security-checks.py`, `runtime/llm_gateway.py`, the
same markers the hook uses), and the plan says which directories it left out and why.

## Pillars

- P1 applies — this design precedes the fix; the defect and the run that found it are recorded in `.agent-rfc/designs/installed-architectures.md`.
- P2 n/a — no dependency added.
- P3 n/a — a local command with no service path.
- P4 applies — `scripts/test/test_installer_templates.py` derives the template list from the code that reads it, so it fails for the next one too; `test_vendored_framework_code_is_not_gated` covers the vendored tenant.
- P7 n/a — no model or typed boundary changes.
- P8 n/a — no telemetry.
- P9 n/a — no agent code.
- P10 n/a — no model call.
- P11 n/a — the installer copies files from its own checkout.
- P12 applies — nothing copied holds a credential; `templates/architectures.yaml` is a catalogue of styles, in `install-ai-stack.sh`.
- P13 applies — this is the gate's own arming: a hooks directory is armed only when the hooks are in it, and `install_gate_hooks` in `runtime/cli.py` refuses rather than pointing git at an empty one.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned with this change.
- P15 applies — a missing catalogue is reported as one line naming the file and the fix, not a traceback (`_cmd_tenant_adopt` in `runtime/cli.py`).
- P16 applies — the fix is re-runnable: `install-ai-stack.sh` copies the catalogue on every run, so an existing machine is repaired by re-running it (`test_the_installer_copies_every_template_the_code_reads`).

## Deviations

none

## Dependencies

None added.

## Levers

- `implemented-not-invoked` — a catalogue, and the gate hooks themselves, that the code reads but the installer never shipped; a hooks path armed over an empty directory.
- `environment-parity` — the tests ran against a checkout; the defect lives only on an installed machine, and the new test reads the installer rather than the checkout.
- `failure-is-not-a-result` — a missing file is a message with a fix, not a stack trace.
