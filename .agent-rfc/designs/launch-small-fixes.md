---
status: done
scope:
  - docker-compose.yml
  - install-ai-stack.sh
  - portal/components/DlqEntryCard.tsx
  - scripts/evals_port.py
  - scripts/mutation_check.py
  - scripts/test/test_cli_install.py
  - scripts/test/test_evals_contract.py
  - scripts/test/test_launch_small_fixes.py
  - templates/in-app-widget/README.md
  - templates/in-app-widget/react/AgentStatus.tsx
  - templates/in-app-widget/widget.js
  - templates/shell/ai-compat.sh
  - .agent-rfc/fixtures/knowledge_graph.json
---
# Small fixes before going public

## Problem

Backlog Stage 1 step 8. Each is small, and a first reader or user can hit each one.

- **The evals score depends on the caller's environment.** `scripts/evals_port.py` clears its thresholds but not
  `PROMPT_DENYLIST_PATH`, so whoever runs the adversarial suite can change its score. The security port already clears it.
- **Discard acts on one click.** `portal/components/DlqEntryCard.tsx` discards a dead-letter entry with no confirmation, beside Replay.
- **Phoenix floats.** `docker-compose.yml` runs `arizephoenix/phoenix:latest`, so two installs can differ and one can break on any day.
- **The widget's default URL is dead.** `AgentStatus` defaults to `cdn.agenticframework.io`, which was never a hosted domain, so a
  caller who omits the prop silently gets no widget.
- **`ai-compat.sh` is a leftover.** The `ai-*` names were retired, and the wrappers keep them alive with a line in every install.
- **Live docs name an archived repository.** `docs/DESIGN.md` cites `bobbyaqlaar/oil-price-demo` as if current.

## Approach

- Clear `PROMPT_DENYLIST_PATH` with the thresholds.
- Discard asks first, naming the entry. `window.confirm`: the portal has no dialog component, and this is one action.
- Pin Phoenix by digest to the image this machine has been running.
- `widgetScriptUrl` becomes required, and the comment shows a self-hosted path.
- Delete `ai-compat.sh`, its copy step and its test. A copy already on a machine is left alone, so a profile that sources it keeps working.
- `docs/DESIGN.md` says the repository is archived. The manual's tutorial keeps `oil-price-demo` as a tenant name the reader
  creates, because it is built from `examples/oil-price-agent`, which exists.

## Pillars

- P1 applies — `.agent-rfc/designs/launch-small-fixes.md` lists each defect before its fix.
- P2 n/a — no dependency is added; the Phoenix pin names the image already in use.
- P3 n/a — no traced code path changes.
- P4 applies — `scripts/test/test_evals_contract.py` and `scripts/test/test_launch_small_fixes.py` hold each behaviour.
- P7 n/a — no stack-specific rule changes.
- P8 applies — `docker-compose.yml` pins the collector the telemetry wire reaches, without changing the wire.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 n/a — no untrusted content is read differently.
- P12 n/a — no secret is read or written.
- P13 applies — `scripts/evals_port.py` closes a way for the caller to change a graded score, and `scripts/mutation_check.py` holds it.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` follows the deleted file and this design.
- P15 applies — `templates/in-app-widget/react/AgentStatus.tsx` fails at compile time rather than silently loading nothing.
- P16 applies — `portal/components/DlqEntryCard.tsx` puts a stop before an action the portal cannot undo.

## Deviations

none

## Dependencies

none

## Levers

- `environment-parity` — the same suite scored differently by caller, and the same compose file ran different images.
- `when-the-fallback-fails` — a default URL that cannot load fell back to nothing.
- `every-line-earns-its-place` — the compat wrappers and their copy step had no remaining purpose.
