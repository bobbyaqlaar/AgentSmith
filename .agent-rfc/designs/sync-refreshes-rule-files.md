---
status: active
scope:
  - agentsmith/sync.py
  - scripts/test/test_framework_sync.py
  - CHANGELOG.md
  - .agent-rfc/fixtures/knowledge_graph.json
---
# `sync` refreshes the rule files an older `tenant init` left unrecorded

## Problem

The tenant-upgrade check (`scripts/check_tenant_upgrade.sh`) failed on PR #113, the first
change to the rule text since that check landed. A tenant made by 4.0.1's `tenant init`,
synced to this tree, still holds 4.0.1's rule files, and `rules check` then calls six of
them drifted.

The cause: 4.0.1's `tenant init` wrote `.cursorrules`, `CLAUDE.md`, `AGENTS.md`,
`GEMINI.md`, `.github/copilot-instructions.md` and the `.agents/skills/` files whole,
but never recorded them in `.agenticframework/scaffold.json`. `sync`'s `ownership`
reads an unrecorded file as `theirs` and leaves it, silently. The rules port, meanwhile,
recognises those same files as its own whole render (the generated header, or a skill's
title line) and holds them to the render. So every 4.0.1 tenant would be stuck on 4.0.1's
rules, and red on `rules check` after its first sync. Block-placed rule files were never
affected: they are compared by text, not by the manifest.

## Approach

- `_shared_files` already asks the rules port for each file's placement. A file placed
  `whole` that exists is one the port recognises as its own; it goes in a new
  `Plan.generated` set.
- `plan_sync` reads an unrecorded (`theirs`) file in that set as `ours`, so it is
  refreshed when it differs from the render, recorded in the manifest, and carried in
  the printed commit, like any other refresh.
- An `edited` file (recorded, then changed) is still left alone with its note: the
  manifest's evidence of a tenant edit wins.

**Deliberately not done:** no change to which files the rules port calls its own, to
`ownership`, or to block placement; nothing new is added to a tenant that lacks a file.

## Pillars

- P1 applies — this design, before the commit; found by `scripts/check_tenant_upgrade.sh`
  on PR #113.
- P2 applies — the port's own placement (`rules_port.render`, `_ours`) is the signal;
  the change is one set on `Plan` and one condition in `plan_sync`. No dependency.
- P3 n/a — no new command, route, job or LLM call; sync's existing output names each
  refreshed file.
- P4 applies — `test_framework_sync.py`: an unrecorded generated rule file that differs
  is refreshed and recorded (fails before: left as it was); a recorded-then-edited one is
  still left with a note. The upgrade check runs in CI. Hand mutants on the new
  condition.
- P7 applies — Python stack rules in `agentsmith/sync.py`: `Plan.generated` is a typed `set[str]` field; no new `except`.
- P8 n/a — no telemetry change.
- P9 n/a — no orchestration.
- P10 n/a — no LLM call.
- P11 applies — the tenant's files are read as text and compared; the only decision
  taken from them is the port's existing header check, `_ours` in `scripts/rules_port.py`.
- P12 n/a — no credentials.
- P13 applies — nothing is weakened: a file is refreshed only when the port already
  holds it to the render, and a recorded edit is still protected
  (`test_a_recorded_rule_file_the_tenant_edited_is_still_left_alone`).
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` moves with the code. No golden changes.
- P15 applies — a file that was not refreshed still reads as drifted in `rules check`,
  never as current.
- P16 applies — if the render fails, `RulesUnavailable` adds its note and no rule file
  is touched, as before.

## Deviations

none

## Dependencies

none

## Levers

- `implemented-not-invoked` — the upgrade check exercises the real path: an old
  release's init, this tree's sync, then `rules check`.
- `test-that-cannot-fail` — the new test asserts the file changed and the manifest
  records it, and is run against the old code first.
