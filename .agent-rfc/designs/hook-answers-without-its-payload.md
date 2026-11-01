---
status: active
scope:
  - scripts/process_gate.py
  - scripts/test/test_process_gate.py
  - scripts/mutation_check.py
---
# A hook answers whether or not its payload arrives

## Problem

`scripts/process_gate.py` reads its hook payload with

    raw = sys.stdin.read() if not sys.stdin.isatty() else ""

`sys.stdin.read()` returns at **EOF**. A caller that spawns the hook and does not
close stdin never sends one, so the gate waits for as long as that caller lives.

Measured today against `scripts/process_gate.py stop` on an otherwise clean tree:

| stdin | wall time |
|---|---|
| `/dev/null` (EOF at once) | 0.76 s |
| the real payload, then close | 0.61 s |
| a pipe held open for 8 s, nothing written | **8.49 s** |

The runtime is not the gate's work — it is the writer's lifetime. Three runs in
this session sat at **8, 11 and 25 minutes** and ended only when killed, every one
of them invoked from a shell whose stdin outlived the command. Nothing was slow:
the gate had not started.

This was diagnosed three times wrongly first — a shell stuck in a heredoc, then
`scripts/map_codebase.py`, then CPU contention from the mutation harness. Each was
checked and ruled out; `scripts/gate_tracing.py::ship` was ruled out too, since it
bounds itself to one 1-second timeout and returns on the first failure. What
settled it was `ps` showing an 11-minute-old `process_gate.py stop`, which is the
signature of a wait, not of work.

**Why this matters beyond my own invocations.** The same `main` serves
`session-start`, `pre-edit` and `stop`, and its own exception handler says *"a hook
must answer, whatever broke"* — then fails closed for `pre-edit`, denying the edit,
precisely so a gate that cannot evaluate does not silently stop gating. A hook that
blocks forever on stdin defeats both halves: it never answers, and it never denies.
Any host that spawns these hooks with an inherited pipe hangs the editor's turn
rather than the gate. `scripts/test/test_process_gate.py::_fake_interpreter`
already documents that a real interpreter "drains stdin (as a real one would
before failing)" — the repository knew the input mattered and still read it
unbounded.

## Approach

Replace all three unbounded reads with `_payload_text(stream, deadline)`: read
what is available until EOF **or** until a deadline, and return what arrived.

- A TTY still yields `""` at once — `isatty()` stays, because an interactive run
  has no payload to wait for and should not pause.
- `select.select` on the stream's file descriptor waits only for the time left.
  Nothing readable before the deadline → `""`, which is the empty-payload path the
  gate already has.
- A writer that sends the JSON and closes gives data then EOF: unchanged, and the
  common case.
- A writer that sends the JSON and **holds the pipe open** now yields that JSON at
  the deadline instead of hanging forever. Strictly better than today.
- `stream.fileno()` raising (a `StringIO`, an in-process test double) falls back to
  `stream.read()`, which cannot block on an in-memory buffer.

`_STDIN_DEADLINE = 2.0` seconds, named rather than inline. A hook payload is a few
hundred bytes written at once; two seconds is far beyond any real write and far
below a turn boundary anyone would notice.

**The timeout is reported, not swallowed.** Expiring with **no bytes at all** is a
different event from being handed nothing, so it prints one line to stderr naming
the deadline. `/dev/null` and a closed pipe stay silent, because they answered.
Without that, the fix would turn a visible hang into an invisible degradation —
the gate deciding on a payload it never received, saying nothing.

Stdout is untouched: it carries the hook protocol, and for `pre-edit` a stray line
there is a malformed decision.

All three reads go through the helper. The first draft of this design excluded
the two `--decision` paths on the grounds that a contract caller closes its pipe —
which is an assumption about someone else's client, not a property of this code,
and the two paths that decide whether a **commit** and a **push** may proceed are
the last place to rely on one. `sweep` takes arguments and reads no payload, so it
is untouched.

## Pillars

- P1 applies — this design; `scripts/process_gate.py` is the one non-test file,
  and the scope names the test file and the catalogue.
- P2 applies — searched `scripts/process_gate.py` for `sys.stdin.read()` and found
  **three** identical unbounded reads, not one: the hook events, contract 3's
  `commit` (`commit-msg --decision`) and contract 2's `range` (`ci --decision`).
  My first read of the file counted one and this design said so; the count was
  wrong and all three are fixed. One helper, three call sites.
  `scripts/test/test_process_gate.py::_fake_interpreter` already drains stdin
  deliberately. No dependency: `select` and `time` are stdlib, `os` was imported.
- P3 n/a — adds no command, route, job or model call. `_traced` still wraps the
  same subcommands and emits the same span.
- P4 applies — `scripts/test/test_process_gate.py` gets the three stdin shapes
  driven through the real entry point as subprocesses, including a writer that
  holds the pipe open, which fails against the current code by never returning.
  Curated mutations go in `scripts/mutation_check.py` so the deadline cannot be
  removed unnoticed.
- P7 applies — Python, `from __future__ import annotations` already at the top of
  `scripts/process_gate.py`; a module-level constant and one annotated helper.
- P8 n/a — emits no telemetry of its own.
- P9 n/a — no orchestration.
- P10 n/a — calls no LLM.
- P11 applies — `scripts/process_gate.py` reads the payload as **data**: this
  changes only how long it will wait for it. The bytes still go to `json.loads`
  inside the existing `try`, and a payload that is not JSON still lands in the
  handler that answers rather than raising. Decoding is `errors="replace"`, so a
  truncated multi-byte write cannot raise on the way in.
- P12 n/a — touches no credential. A payload is not logged; only the deadline is
  named in the stderr line.
- P13 applies — `scripts/process_gate.py` keeps every check it has; nothing is
  weakened. The honest risk is the opposite of a weakening and is stated: deciding
  on an **empty** payload where it used to block means `cwd` comes from the
  process's own directory instead of the hook's. That is the path the gate already
  takes for `{}` today, and the stderr line says when it was taken.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned for the two
  new rfc documents. No golden or baseline changes; the IDE golden payloads in
  `scripts/test/test_gate_ides.py` are unaffected, because a closed pipe behaves
  exactly as before.
- P15 applies — `scripts/process_gate.py` prints the deadline line only when the
  wait expired with nothing read, so "no payload offered" and "payload never
  arrived" do not read alike. The existing decision output is unchanged.
- P16 applies — `scripts/process_gate.py` loses its worst recovery path, which was
  no recovery: the deadline is the rung below a writer that never closes, and below
  that the `{}` path and the existing exception handler still answer.

## Deviations

none

## Dependencies

none

## Levers

- `when-the-fallback-fails` — there was no rung below "the writer never closes".
  Now there is, and it is bounded.
- `failure-mode-visibility` — a hang is visible as a hang; an empty payload is not.
  The stderr line is what keeps the fix from hiding the condition.
- `ambiguous-signals` — "handed nothing" and "waited and got nothing" are two
  events, and only the second prints.
- `guards-must-be-able-to-fail` — a gate that never returns never denies either;
  `pre-edit` fails closed on purpose and could not reach that code.
- `gate-integrity` — the gate must be able to answer before it can be trusted to
  refuse.
- `test-that-pins-a-defect` — the held-open-pipe test does not return at all
  against the current code, which is the defect itself rather than a proxy for it.
- `grep-for-siblings` — swept every `stdin` read in the file; the `commit-msg
  --decision` path is named and deliberately left to its own slice.
- `minimal-host-dependency` — `select` on a pipe, nothing added to the machine.
