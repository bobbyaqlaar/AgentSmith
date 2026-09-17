# Review — governance enforcement, G2b (the shell surface)

Design: `.agent-rfc/designs/governance-enforcement.md` § G2, with the amendment written before
this code: deny-only, segment by segment, and the limit stated as carefully as the rule.

**Built evidence (2026-09-18):**

- **Failing tests first.** `scripts/test/test_gate_shell.py` (41) was written before
  `gate_shell.py`; 12 failed on the first run.
- **The rule caught its own author, twice.** Writing the tests, the gate refused *my* shell
  command: the fixtures contain `git commit --no-verify` inside quotes, and splitting the raw text
  on `&&` and `;` found a "command" inside a Python string literal. Then, mid-fix, a half-edited
  `gate_shell.py` made the pre-edit hook raise, and the gate failed closed on every Bash call
  until the file was whole again — which is the behaviour it is supposed to have, experienced
  from the other side.
- **Deny-only, deliberately.** The design's "warn when a shell command writes into a gated path"
  is deferred: there is no warn channel that works in more than one of the six IDEs, and the stop
  gate already catches that case at the end of the turn. Recorded in the design rather than
  invented per IDE.
- **Mutation checks (each reverted):** twelve — `--no-verify` allowed on commit and on push,
  `-c core.hooksPath` allowed, `git config` allowed to point anywhere, the whole line judged at
  once, a redirection to the gate allowed, a writer naming the gate allowed, reading the gate
  refused, `agentsmith approve` allowed, the gate never consulting the rule, and every shell
  command refused. Eleven caught. The twelfth — `posix=False` / `whitespace_split=False` on the
  lexer — is an **equivalent mutant**: quoting survives both, because what carries it is
  tokenising before segmenting, and that is killed by "the whole line is judged at once". Left
  equivalent rather than contorting a test to kill it.

## Pass 1 — findings: 3

- `test-the-contract` — **finding:** `_protects()` used `lstrip("./")` to drop a leading `./`.
  `lstrip` strips a SET of characters, so it ate the leading dot of every path it was asked
  about — `.githooks/commit-msg` became `githooks/commit-msg` and matched nothing. Every
  write-to-the-gate refusal was dead on arrival, and eight tests said so.
- `ambiguous-signals`, `intuitive-journey` — **finding:** splitting the raw command text refused
  quoted text that merely mentions a bypass — a test, an `echo`, a script passed to an
  interpreter. A gate that refuses people writing *about* it teaches them to turn it off. The line
  is tokenised with `shlex(posix=True, punctuation_chars=True)` now, which respects quotes and
  still breaks on `;` where `shlex.split` alone left `true;` glued to the next command — a
  separate hole the same fix closed, with a test for each.

- `test-that-cannot-fail` — **finding:** three tests read `hooks["PreToolUse"][0]`, so adding the
  Bash entry made them silently assert about the shell hook instead of the edit hook — including
  the one that proves the edit gate still denies when the launcher cannot run. They select by
  matcher now, which is the contract they meant.

## Pass 2 — findings: 0

Every lever over the final diff: the four refusals, the tokeniser, the protected list, the two
generated configs, and the wiring in `cmd_pre_edit`. Considered and declined: a marker comment
that would let a command opt out (`… # not-a-bypass`), the way the xref and secret rules allow an
example. On a shell line it would be trivially self-served and would gut the rule; quoting is the
honest distinction and it is the one a shell already makes.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen; the surface is a hook payload
Group 6 · Signal integrity            [x] checked
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session

Tests added/updated:      test_gate_shell.py (41); the fixture repo vendors scripts/gate_shell.py
Mutation-checked:          yes — twelve, each reverted; eleven caught, one equivalent and
                          named as such
Fixtures re-pinned:        yes — .claude/settings.json and .cursor/hooks.json regenerated
                          with the shell surface
Gates run locally:         ruff, the full pytest suite, `process_gate.py pillars`, the hook
                          config drift check
Declared gaps:             (1) it reads the command, not what the command does — a script, an
                              alias, a Makefile target or `bash -c "$(…)"` reaches git without
                              passing through. The sweep is the layer that catches those;
                          (2) only Claude Code and Cursor have a shell surface wired, because
                              they are the two whose config schema is verified (G2a);
                          (3) the "warn on a gated shell write" half is deferred — no
                              cross-IDE warn channel exists, and the stop gate covers it;
                          (4) an unbalanced quote falls back to a crude split, which is
                              best-effort by construction;
                          (5) the shell surface fails OPEN when the launcher cannot run, unlike
                              the edit gate: a broken gate that refuses every shell command
                              leaves no way to repair the install from inside the IDE. Stated
                              in the generated config, and the sweep holds behind it.
```
