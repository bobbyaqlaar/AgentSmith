# Review — gate-local-events (C2)

Design: `.agent-rfc/designs/gate-local-events.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 9

1. **The slice broke the gate's own launcher and locked everyone out.** A comment and a message inside
   `.githooks/process-gate`'s single-quoted inline Python each held an apostrophe (`machine's`,
   `repository's`); the first ended bash's quote, and the launcher stopped parsing. Every hook runs it,
   so every edit, every turn end and every commit failed closed at once — and nothing inside the
   session could repair it, since the repair is itself an edit the broken gate refuses. The owner
   fixed it from a terminal; my first suggested fix caught only one of the two apostrophes. Now
   pinned twice: `test_every_gate_hook_parses` (`bash -n` on every hook) and
   `test_the_launchers_inline_python_is_quoted_whole_and_compiles` (each block closes on a line of
   its own and compiles) — the second shown to catch the original text. One block that closed
   mid-line legitimately was moved to the convention rather than the check weakened.

2. **The provider answered with a tenant's vendored copy of the gate.** `agentsmith gate` looked for
   `./scripts/process_gate.py` before its own installation, so a vendored tenant on contract 2 or 3 was
   judged by the 1,318-lines-stale framework code it holds — the coupling, reversed. Design amended
   first; the provider now runs its own gate and uses a repository's `scripts/` only when the
   repository is AgentSmith. Mutation-checked.

3. **`nargs=REMAINDER` for the `kg` verbs would have swallowed `--ide claude`** from every IDE hook's
   `gate pre-edit --ide claude`, silently answering in the wrong dialect. Caught before it ran; the
   `kg` options are declared explicitly, and `stop --ide claude` was checked to still answer Claude's
   shape.

4. **The push conformance cases depended on AgentSmith's sweep semantics.** Its first sweep records
   existing history without judging it, so the fixture's tagged undesigned commit was never flagged;
   a provider that sweeps everything reachable would have read the same fixture the other way. The v3
   cases now drop those tags first and make a fresh ungated commit for the `deny` case, so both
   readings agree on every case.

5. **The conformance runner set `core.hooksPath=/dev/null`** to make its ungated commit — a pattern
   this repository's rules forbid. Unneeded (the fixture is built with `--template=` and has no
   `.githooks/`), and removed.

6. **The tests asked the machine's installed provider.** At contract 3 a tenant's commit asks
   `agentsmith gate`; on this machine that is 2.0.0, which does not know `commit`, and in CI there is
   none — 9 failures and 22 errors. `scripts/test/provider_shim.py` puts this checkout's `agentsmith`
   on PATH for both test trees, as the setup action does in CI. It also exposed a real message gap:
   exit 2 (a usage error) now reads as "older than the gate contract this repository declares",
   with the fix.

7. **An existing mutation's target went stale again** (`GATE_CONTRACT = 2`), the failure that cost C1
   a 36-minute CI run. Re-pointed and caught; every target in the catalogue was counted before any
   push.

8. **A test I described as written was not in the file.** The too-old-provider test was appended by a
   command the broken launcher blocked; the summary said it existed. Found when its wording needed
   updating; written and run.

9. **Nothing asserted that `kg impact` scopes the staged change.** Swapping back to the working-tree
   diff passed every test. A test with an unstaged edit now pins it, and a mutation proves the test.

## Pass 2 — findings: 2

The full suite, after pass 1's fixes: 6 failed, 2108 passed.

1. **The test shim crashed every tenant's security harness.** `runtime/test/conftest.py` is vendored
   into tenants, whose `runtime/test/` the harness runs; the pass-1 shim loaded
   `scripts/test/provider_shim.py` unconditionally, and a tenant has no `scripts/test/` — pytest died
   at configure time and four `SEC-*` controls failed in all five scratch tenants. The shim loads only
   where the file exists: a framework checkout. Nothing in a tenant's `runtime/test/` commits, so it
   needs none. `test_scratch_tenants.py` — the offline build of every app — is what caught it, and
   stays the guard: 39 passed after the fix.

2. **The manual's `agentsmith gate` row did not list `--staged`.** `test_cli_install.py`'s
   reference-row check refused it; the row now names `kg build|impact [--staged|--base REF]`.

## Pass 3 — findings: 1

The full suite after pass 2: 2114 passed, 10 skipped. Then a re-read of the hooks as a whole.

1. **`commit-msg` could drop the subject rule silently.** It asked the launcher for the contract and
   compared with `-lt 3`; a launcher too old to know `declared-contract` answers with text, the test
   errors, `if` reads the error as false — and the rule was skipped. That is a tenant whose
   `commit-msg` is newer than its launcher: a hand copy, a half-applied sync. The rule is now dropped
   only for a plain number of 3 or more; anything else keeps it.
   `test_a_launcher_too_old_to_name_the_contract_keeps_the_subject_rule` stands a launcher that
   answers `usage:` in front of the hook and expects the refusal. The mutation that keeps the rule at 3
   was re-pointed at the new `case` and is caught.

## Pass 4 — findings: 0

Re-ran every suite that commits through the hooks (228 passed: hooks, chain, first commit, sync,
adopt, scaffold, process gate, the five scratch tenants), `bash -n` on every hook, every mutation
target in the catalogue counted, and `gate_contract_v3`'s seven mutations — all caught. Re-read the
CHANGELOG, protocol and manual against the code: the too-old message, the `--staged` default, and
what at contract 3 is the provider's rather than the hook's all read as the code behaves.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one commit verdict (`commit_verdict`) behind the hook and the `commit` answer; one `ask_provider` behind `ci`, `commit` and `push`; the subject rule in two places only because below contract 3 the hook keeps it, and a test pins the two equal; one test shim (`provider_shim.py`) for both test trees.
Group 2 · Quality / safety — [x] checked — 29 tests in `test_gate_contract_v3.py` with real `git commit` and `git push` through the hooks; 7 mutations in `gate_contract_v3` and the re-pointed `framework_sync` one, all caught; conformance 5/5, 10/10, 15/15; full suite 2114 passed.
Group 3 · Architecture / hygiene — [x] checked — the hooks hold no policy at contract 3; the provider runs its own gate; the vendored `runtime/test/conftest.py` stays loadable in a tenant (scratch tenants green).
Group 4 · Process — [x] checked — the design was amended before the provider-runs-its-own-gate change; the slice's lockout of its own launcher is recorded as finding 1 with the owner's repair, and guarded by two tests.
Group 5 · Intuitive UI — [x] checked — a refused commit says why in the provider's words; a too-old provider is named with the fix; `pre-push` no longer names AgentSmith's sweep as the only possible refuser.
Group 6 · Signal integrity — [x] checked — refused, no decision (by kind) and too old read differently; an unreadable contract keeps the subject rule rather than dropping it.
Group 7 · Auth & session integrity — [x] checked — the commit message is encoded by an interpreter, never spliced into JSON; refs are validated; no credentials in these events.

Tests added: `scripts/test/test_gate_contract_v3.py` (29, including `test_every_gate_hook_parses` and `test_the_launchers_inline_python_is_quoted_whole_and_compiles`); `scripts/test/provider_shim.py` wired into both conftests; updated `test_gate_contract_v2.py`, `test_tenant_adopt.py`, `test_framework_sync.py`.
Mutation-checked: `python3 scripts/mutation_check.py gate_contract_v3` — 7 caught (run three times, the last after pass 3); the re-pointed `framework_sync` mutation through `mutation_check.run_suite` — caught; every target in the catalogue counted.
Fixtures re-pinned: `contract/gate/v3/` written new (v1, v2 untouched); `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
Gates run: full `pytest` (2114 passed, 10 skipped) and, after pass 3, every hook-exercising suite (228 passed); `ruff check .` (0.15.20); `mypy` (1.14.1); `agentsmith conformance --contract 1|2|3`; `bash -n` on every hook; `agentsmith gate kg impact` against this commit (agrees with the hash below); `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `gate-integrity`, `declared-vs-enforced`, `single-source-of-truth`, `pin-unremovable-duplicates`, `test-the-contract`, `test-that-cannot-fail`, `two-owners-two-cadences`, `failure-mode-visibility`, `implemented-not-invoked`, `docs-match-behaviour`.

KG query: kg:4b2b0732dd5c
