# Review — governance enforcement, G2a (one gate, six dialects)

Design: `.agent-rfc/designs/governance-enforcement.md` § G2, with the amendment written before
this code: G2a is the adapter layer, G2b the shell pre-check, and what has been verified is
recorded rather than assumed.

**Built evidence (2026-09-17):**

- **Failing tests first.** `test_gate_ides.py` (64) was written before `gate_ides.py`; the module
  did not exist on the first run, and the registry and end-to-end pins stayed red until the `ides`
  section, the fixtures and `--ide` landed.
- **Cursor was re-read from the vendor's docs today, and it moved the design.** Cursor has **no
  before-edit hook** — `afterFileEdit` fires after the write and `beforeReadFile` is a read — so
  the edit gate is `preToolUse` with `matcher: "Write"`. `sessionStart` is fire-and-forget and
  cannot block, so Cursor's session line is advisory like Claude's. Confirmed as designed:
  `permission: deny` with `user_message`/`agent_message`, `followup_message` on `stop`,
  `additional_context` on `sessionStart`, `failClosed` per script. Also found: `stop` and
  `sessionStart` carry no `cwd` at all — the repo comes from `workspace_roots`, and a gate that
  cannot find the repo checks nothing.
- **What is NOT verified is said so, in three places** — the design, the registry's per-IDE
  `note`, and the docs table. Antigravity, Copilot, Gemini and Codex follow the design's pinned
  table (owner, 2026-09-15); their golden fixtures are where a real session's payload gets pinned.
- **A config is generated only where the schema is verified.** Claude Code's (by use) and Cursor's
  (by docs) are written and drift-tested; the other four are refused with a reason. A file in a
  shape nobody confirmed looks like enforcement and may be ignored in silence — which is worse
  than no file, and is exactly `declared-vs-enforced`.
- **Mutation checks (each reverted):** fourteen — an unreadable payload allowed through, the gate
  not failing closed on one, camelCase fields unread, a read counted as an edit, a shell command
  counted as an edit, `workspace_roots` ignored, a repeated stop blocking again, Cursor answered
  in Claude's dialect, the `--ide` flag ignored, an unknown IDE accepted, Cursor's `failClosed`
  turned off, Claude's deny fallback dropped, a config generated for an unverified schema, and the
  generated configs no longer checked. Eleven caught; the three survivors are pass 1.

## Pass 1 — findings: 4

Three mutations survived, and each was a test that asserted the outcome without asserting the
mechanism — the same failure three times, which is why they are listed separately. The fourth
finding is the gate's, not mine: it refused this slice's own commit.

- `test-that-cannot-fail` — **finding:** nothing ran an *unreadable* payload through the gate.
  `gi.parse` raising was tested; `cmd_pre_edit` turning that into a deny was not, so deleting the
  fail-closed branch changed nothing any test saw. Tested end to end now, per IDE.
- `test-that-cannot-fail` — **finding:** "a repeated stop never blocks twice" asserted only that
  the output held no `"block"` or `"deny"`. Cursor's repeat shape contains neither word either
  way, so the assertion passed with the repeat handling deleted. It now asserts the repeat differs
  from the first block, which is the actual property.
- `test-the-contract` — **finding:** the end-to-end deny test asserted "the path appears and it is
  JSON", which is true in every dialect — so ignoring `--ide` entirely and answering in Claude's
  shape passed six times over. It now compares the answer's keys against that IDE's own renderer.

- `gate-integrity` — **finding:** found by the gate refusing this slice's own commit. The new
  hook configs were **ungated**: `.cursor/**`, `.agents/hooks.json`, `.gemini/settings.json` and
  `.codex/hooks.json` were not in the repo's `gated` globs, so the one file that can switch an
  IDE's gate off needed no design to edit — the exact hole the design says these configs close.
  All four are gated now, with a test that every adapter's `config_path` is gated, so a seventh
  IDE cannot arrive ungated.

## Pass 2 — findings: 0

Every lever over the final diff: the event model, the six parsers and renderers, the fail-closed
path, the registry section, the generated configs, the fixtures, and the docs. Considered and
declined: generating the four unverified configs anyway "so every IDE has one" — a config that
may be silently ignored is a gate that is declared and not enforced, and the backlog carries the
trigger for confirming each schema instead.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen; the IDE surfaces are hook payloads
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_ides.py (65); the fixture repo vendors scripts/gate_ides.py,
                          and test_process_gate.py's Claude-settings contract now expects --ide
Mutation-checked:          yes — fourteen, each reverted; three survivors became pass 1
Fixtures re-pinned:        yes — 18 golden IDE payloads (new), templates/governance.json
                          (the `ides` section), .claude/settings.json regenerated
Gates run locally:         `agentsmith gates run`, ruff, the full pytest suite, the registry
                          and hook-config drift checks
Declared gaps:             (1) four IDEs' payload shapes come from the design's pinned table,
                              not from a live session — the fixtures are where that is fixed;
                          (2) four hook CONFIG schemas are unconfirmed, so those configs are
                              not generated at all;
                          (3) Cursor's `tool_input` for a Write tool is not documented field
                              by field — an unreadable payload denies and names its keys,
                              which is the fail-closed half of that gap;
                          (4) Antigravity and VS Code fail open by design: git and the sweep
                              are what hold there;
                          (5) the shell surface (`--no-verify`, `hooksPath`, `agentsmith
                              approve`) is G2b — today the sweep catches those after the fact.
```
