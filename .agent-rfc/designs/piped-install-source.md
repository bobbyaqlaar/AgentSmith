---
status: done
scope:
  - install-ai-stack.sh
  - scripts/check_release_install.sh
  - scripts/mutation_check.py
  - scripts/test/test_release_install.py
  - .agent-rfc/fixtures/knowledge_graph.json
---
# A piped install installs the release it announces

## Problem

The owner ran the README's `curl … | bash` with the working directory in a checkout of AgentSmith at 3.0.0. It printed
`AgentSmith v4.0.0 installed successfully` and installed 3.0.0 from that checkout. Reproduced in an empty `HOME`.

- **The source is chosen from the working directory.** Piped, `BASH_SOURCE` is empty, so `${BASH_SOURCE[0]:-$0}` falls to
  `bash`, whose dirname is `.`. A directory holding the installer and the gate launcher is taken for the script's own checkout.
- **Step 9 printed the wrong version and passed,** because it checks that the command runs, not which version it is.
- **A failed verification exits 0.** The installer prints "completed with warnings", so nothing downstream can tell.
- **Nothing tested it.** The test for this uses a tenant that does not look like a checkout, and `scripts/check_release_install.sh`
  runs the installer as a file, not the way the README says.

Anyone working in a checkout is exposed: contributors, and the owner. A new user in an unrelated directory is not.

## Approach

- `install-ai-stack.sh`: piped, there is no script path, so there is no checkout. The working directory is never consulted.
- Step 9 requires `agentsmith version` to be `FRAMEWORK_VERSION`, allowing `+build` metadata.
- A failed verification exits 1, after printing what failed.
- `scripts/check_release_install.sh` pipes the installer as the README says, from a directory that looks like another checkout.
  It adds no install, so Self-Test takes no longer.

## Pillars

- P1 applies — `.agent-rfc/designs/piped-install-source.md` records the reproduction and its causes before the change.
- P2 n/a — no dependency or structural change.
- P3 n/a — the installer emits no spans, and no traced code changes.
- P4 applies — `scripts/test/test_release_install.py` holds the three behaviours, and `scripts/check_release_install.sh` runs the real path.
- P7 n/a — no stack-specific rule changes.
- P8 n/a — no telemetry wiring changes.
- P9 n/a — no agent code.
- P10 n/a — no model calls.
- P11 applies — `install-ai-stack.sh` stops trusting what the working directory contains when it chooses what to install.
- P12 n/a — no secret is read or written.
- P13 applies — `scripts/mutation_check.py` gains three mutations in `installed_machine`, one for each behaviour.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` gains this design's node.
- P15 applies — `install-ai-stack.sh` no longer reports success on a version it did not install, and its exit status now says so.
- P16 applies — `install-ai-stack.sh` exits 1 naming both versions, and re-running from the release repairs the install.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the banner declared a version nothing compared with what was installed.
- `environment-parity` — the release check now runs the install the way the README does.
- `when-the-fallback-fails` — a failed verification now reaches the exit status.
- `test-the-contract` — the existing test passed on a directory that could not trigger the defect.
