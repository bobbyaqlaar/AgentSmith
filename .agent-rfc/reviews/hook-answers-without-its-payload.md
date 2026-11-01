# Review — a hook answers whether or not its payload arrives

Design: `.agent-rfc/designs/hook-answers-without-its-payload.md`. Raised by the
owner: *"fix the stop gate slowness."* It was not slowness.

**What it actually was.** `scripts/process_gate.py` read its payload with
`sys.stdin.read()`, which returns at **EOF**. A caller that spawns the gate and
does not close stdin never sends one, so the gate ran for as long as that caller
lived rather than for as long as its own work took.

| stdin | before | after |
|---|---|---|
| `/dev/null` (EOF at once) | 0.76 s | 0.82 s |
| the payload, then close | 0.61 s | 0.62 s |
| a pipe held open by a live writer | **never returns** | **2.81 s** |

Three runs this session sat at 8, 11 and 25 minutes and ended only when killed.

**Diagnosed wrongly three times first**, and each wrong answer was stated to the
owner before being checked: a shell stuck in a heredoc, then
`scripts/map_codebase.py`, then CPU contention from the mutation harness. All
three were then ruled out by measurement — a clean-tree run at 0.96 s, a
gated-change run at 1.24 s under `cProfile`, and three runs at 0.66–0.93 s with
the harness deliberately running. `scripts/gate_tracing.py::ship` was ruled out by
reading it: one 1-second timeout, and it returns on the first failure rather than
paying it per batch. What settled it was `ps` showing an 11-minute-old
`process_gate.py stop` — the signature of a wait, not of work. **The lesson is in
the order:** three guesses were voiced before the first measurement.

**Three call sites, not one.** `grep` for `sys.stdin.read()` found the hook events,
gate contract 3's `commit` and contract 2's `range`. The design's first draft
counted one and excluded the two `--decision` paths, reasoning that a contract
client closes its pipe — an assumption about someone else's code, not a property
of this one, and those two decide whether a **commit** and a **push** may proceed.
All three now go through `_payload_text`. The design was corrected rather than left
describing something else.

**Built evidence (2026-11-01):**

- 6 tests through the real entry point as subprocesses. **4 do not return at all
  against the old read** — `TimeoutExpired` after the 20-second hold, which is the
  defect itself rather than a proxy. Confirmed by restoring `HEAD`'s
  `scripts/process_gate.py`: `4 failed, 1 passed in 92.08s`.
- `hook_payload` curated suite, **5 mutations, all caught** (one survived first — see
  Pass 1).
- `ruff` clean on both changed files.

## Pass 1 — findings: 3

- `test-that-cannot-fail` — **a mutation survived, and it survived for an
  instructive reason.** `EOF is not noticed` (`if not piece:` → `if False:`) left
  the suite green. With EOF undetected, `os.read` returns `b""` forever and
  `chunks.append(piece)` appended it, so `if not chunks:` went **false** and the
  "no payload" line was suppressed: a gate busy-looping for the whole deadline
  looked exactly like one that had been handed its payload. The guard coupled "did
  anything arrive" to a list that can hold empty elements. It is a `bytearray`
  length now — `data += piece`, `if not data:` — which reads better and makes the
  mutant catchable. Found by the harness, not by reading the diff.
- `test-that-cannot-fail` — **one of my own tests was vacuous.**
  `test_a_payload_that_arrives_is_used_whoever_holds_the_pipe` asserted
  `"could not run" in err or proc.returncode == 0` against `stop`, and `stop` exits
  0 whether or not it used the payload, so the second clause carried it. Measured
  what the gate really does with `cwd=/`: **no stdout and no stderr at all**, so
  the first clause was never true either. Rewritten against `session-start`, whose
  output depends only on the payload's `cwd` — empty when pointed outside an
  adopting repository, the instructions block when pointed at this one — plus a
  control asserting the no-payload case *does* answer, so the assertion fails when
  the payload is ignored rather than when it is read.
- `docs-match-behaviour` — `_payload_text` reads the **file descriptor**, which is
  what makes a deadline possible and what constrains its caller: bytes already
  pulled into the stream's own text buffer are invisible to `os.read`. Nothing
  triggers it (its one caller reads stdin nowhere else), and a helper carrying a
  silent precondition is how the next caller breaks. Stated in the docstring.

## Pass 2 — findings: 2

- `grep-for-siblings` — swept `sys.stdin.read()` across `scripts`, `runtime`,
  `.githooks`, `hooks` and `enterprise`, following the data rather than the
  directory, and found **nine more** of the identical line:
  `scripts/rules_port.py:211`, `scripts/security_port.py:234`,
  `scripts/evals_port.py:235`, `runtime/cli.py:1025,1075,1094,1154` and
  `.githooks/process-gate:221,409` (inline `python3 -`). Each waits for an EOF its
  caller may never send.

  **Declared, not fixed, with the reason stated rather than implied.** None is
  known to hang today: the three ports are contract endpoints the launcher invokes
  with a pipe it closes, and the `runtime/cli.py` reads are `conformance` and the
  CLI's own. That is a statement about this repository's callers, not about the
  code — which is precisely the reasoning this slice retracted for the gate's two
  `--decision` paths, so it is recorded as a weak argument, not a clean one. The
  fix is not a line-for-line copy either: `_payload_text` lives in
  `scripts/process_gate.py`, and the gate deliberately does not import its own
  modules, so sharing it means a shared module and a held-open-pipe test per
  caller. Backlogged with the file:line list, and the owner was told.
- `guards-must-be-able-to-fail` — `_payload_text(stream, …)` took an unannotated
  `stream` in a file whose other helpers annotate, and `scripts/**` is outside
  mypy's scope so nothing would ever have said so. Annotated `IO[str]`, which is
  what both branches need (`fileno()` on the fd path, `read()` on the fallback).

## Pass 3 — findings: 0

- `when-the-fallback-fails` — the rung that was missing is the slice: below "the
  writer never closes" there is now a deadline, below that the `{}` path the gate
  already had, and below that the exception handler that fails closed for
  `pre-edit`. Each one answers.
- `failure-mode-visibility` — the deadline prints, so the fix cannot turn a visible
  hang into an invisible decision. Checked that stderr is already the gate's
  channel for this kind of line (`"could not run"`, `"did not run"` are asserted on
  stderr by existing tests), so nothing new is being risked on the hook protocol —
  stdout is untouched.
- `ambiguous-signals` — three distinct events, three distinct behaviours: handed
  nothing (silent, at once), handed a payload (silent, used), waited and got
  nothing (one line naming the deadline). Two mutations pin the last two apart.
- `environment-parity` — the deadline is wall-clock and the same everywhere; no
  branch on CI, platform or interpreter. `select` on a pipe is POSIX, and the
  gate's own `UNUSABLE` check already requires a real Python.
- `every-line-earns-its-place` — the docstring is long, but it is defect history
  plus a precondition a future caller needs, over ~20 lines of code rather than
  the 5 that made the previous slice's `_answers` docstring a finding.
- `one-catalog` / `single-source-of-truth` — one `_STDIN_DEADLINE`, named, used by
  the helper's default and asserted against by the tests rather than re-typed as a
  number.
- `validate-on-the-receiving-side` — the bytes still reach `json.loads` inside the
  existing `try`, and decoding is `errors="replace"`, so a truncated multi-byte
  write cannot raise on the way in. The payload is still data.
- `test-the-contract` — the tests drive `scripts/process_gate.py` as a
  subprocess and assert on what it emitted and how long it took, not on
  `_payload_text` in isolation. The one unit test covers the no-fd fallback, which
  has no subprocess shape.
- Groups 5 and 7 n/a: no screen, no control, no cookie, bearer or session.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — one helper, three call sites that each had
                                          the same line. The nine siblings elsewhere are named
                                          in Pass 2 and backlogged, not quietly copied
Group 2 · Quality / safety            [x] checked — Pass 1 fixed a surviving mutant and a test
                                          that could not fail; Pass 2 annotated the helper
Group 3 · Architecture / hygiene      [x] checked — one module-level constant and one private
                                          helper in the file that owns the entry point; no new
                                          module, no new dependency (select, time are stdlib)
Group 4 · Process                     [x] checked — CHANGELOG entry under [Unreleased]
                                          (scripts/** requires one); two backlog items; the
                                          shipped answer-is-the-whole-answer design flipped to
                                          done, which the stop gate required
Group 5 · Intuitive UI                [x] n/a — no screen or control; the surfaces are the hook
                                          protocol on stdout (untouched) and one stderr line
Group 6 · Signal integrity            [x] checked — a gate that never returns never denies, and
                                          the deadline is reported rather than swallowed
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session. It does decide the
                                          commit and push contract paths, which is why both are
                                          fixed rather than assumed safe

Tests added/updated:      scripts/test/test_process_gate.py +6, driven through the real entry
                          point as subprocesses: the hook event, both contract --decision paths,
                          a closed pipe, a payload written-but-not-closed, and the no-fd
                          fallback. 4 of the 6 do NOT RETURN against the old read — confirmed by
                          restoring HEAD's copy: 4 failed, 1 passed in 92.08s.
Mutation-checked:         new suite `hook_payload`, 5 mutations, all caught. One survived the
                          first run — `chunks.append(b"")` made "something arrived" true — and
                          the guard became a bytearray length because of it.
Fixtures re-pinned:       .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:558552caf09e
Gates run locally:        pytest (test_process_gate.py, then the full suite), ruff,
                          mypy==1.14.1 from requirements-lint.txt, py_compile sweep,
                          mutation_check.py hook_payload, design-tree drift, agentsmith gate kg
                          check, --check-hooks, --check-redaction on both profiles, process gate
                          (design + review)
Declared gaps:            two. (1) Nine identical unbounded reads remain in three ports,
                          runtime/cli.py and the launcher's inline python — Pass 2 names every
                          file:line and says why the fix is a shared module rather than a copied
                          line. (2) _payload_text reads the file descriptor, so bytes already in
                          the stream's text buffer are invisible to it; its one caller reads
                          stdin nowhere else, and the docstring states the precondition.
```
