---
status: active
scope:
  - scripts/compliance_checks.py
  - scripts/test/test_compliance_checks.py
  - agentsmith/mcp_pin.py
---
# The declaration check reads the image's last stage, and MCP pinning reads what agents read

From the 4.1.0 review's second pass (the owner's local `review-4.1.0-pass2.md`): P2-R10 and P2-R11, two minors the
owner asked for before the release. Follows `.agent-rfc/designs/compliance-profile-holds.md` (R18, R26).

## Problem

- **P2-R10.** `declaration_deployed` looks for `COPY . .` anywhere in a Dockerfile. In a multi-stage build that is
  usually the builder stage, and the final stage copies only build output, so the running image has no declaration and,
  with no `COMPLIANCE_PROFILE`, every duty is off, while the check says "the declaration ships with the image". The
  other way round, `COPY --chown=app:app . /app` and `COPY ./ /app/` ship it and fail. And the code's comment says
  `ENV COMPLIANCE_PROFILE` means "the profile is on without the file", when `compliance._find` raises then: the image
  refuses to run unless the file is mounted.
- **P2-R11.** `.vscode/mcp.json` is JSONC (VS Code allows comments); one comment makes `static_problems` raise, the
  obligation fail as "could not run", and `mcp-pin` unable to pin. A tool's `title`, `annotations` (such as
  `readOnlyHint`) and `outputSchema` are not in its hash, so a server can change them and `mcp-verify` passes. And
  Codex, one of the six agents the gates support, keeps project servers in `.codex/config.toml`, which is not read.

## Approach

- **P2-R10.** The Dockerfile is read as stages (each `FROM` starts one) and only the last is judged. In it, a
  `COPY` or `ADD` (any flags, but not `--from=` another stage) of the context root (`.`, `./`) or of
  `.agenticframework` ships the declaration, unless `.dockerignore` keeps it out. `ENV COMPLIANCE_PROFILE` in the last
  stage without such a copy passes only as "must be mounted at run time", and the pass message says so for each such
  image; the comment says what really happens (the app refuses to run without the file).
- **P2-R11.** Server files are read with comments and trailing commas stripped (outside strings), so a JSONC file
  parses; a file that still cannot be read is named in the problem, not raised. The tool hash covers `name`, `title`,
  `description`, `inputSchema`, `outputSchema` and `annotations`. `.codex/config.toml` joins the files read, its servers
  under `mcp_servers`. The profile ships for the first time in 4.1.0, so no tenant holds pins made with the narrower
  hash.

## Pillars

- P1 applies — P2-R10 and P2-R11 are the requirement; `.agent-rfc/designs/image-final-stage-and-mcp-reads.md` is the plan.
- P2 applies — `scripts/compliance_checks.py` (`_ships_declaration`) and `agentsmith/mcp_pin.py` change in place; `tomllib` is in the standard library.
- P3 n/a — no spans or evaluations.
- P4 applies — `scripts/test/test_compliance_checks.py` holds each Dockerfile shape and each MCP case; hand mutants after.
- P7 applies — `agentsmith/mcp_pin.py`: the config files of the agents the gates support, Codex included.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no routing.
- P11 applies — `agentsmith/mcp_pin.py`: a tool definition a server can change is pinned whole.
- P12 n/a — environment values are still left out of the server's hash; only names are kept.
- P13 applies — `scripts/compliance_checks.py`: the image that runs is the one judged.
- P14 n/a — no fixture or baseline (no pins exist before 4.1.0).
- P15 applies — `scripts/compliance_checks.py` and `agentsmith/mcp_pin.py`: "could not read" names the file; "set but not copied" says it must be mounted.
- P16 applies — `CHANGELOG.md`: a multi-stage image that never copied the declaration now fails; pins made by a pre-release build must be re-made.

## Deviations

none

## Dependencies

none

## Levers

- `gate-integrity` — the stage that runs is the one judged (P2-R10).
- `aggregates-name-their-scope` — the files read, and what a pin covers (P2-R11).
- `grep-for-siblings` — `title` and `annotations` beside `description`; Codex beside the other agents.
- `docs-match-behaviour` — the comment about `ENV COMPLIANCE_PROFILE`.
- `test-that-cannot-fail` — hand mutants, including the `.dockerignore` negation the second pass found untested.
