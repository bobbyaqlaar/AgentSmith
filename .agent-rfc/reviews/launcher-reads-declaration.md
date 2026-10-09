# Review — launcher-reads-declaration

Design: `.agent-rfc/designs/launcher-reads-declaration.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 2

1. **An existing test extracted one launcher function by line range** and ran it alone
   (`test_the_launcher_reads_each_port_apart`); `declared_port` now calls `decl_get`, so the test
   extracts both. Found by the contract test files, run before the full suite.
2. **A malformed `contract` value read as itself.** `declared_contract` now answers 1 for anything but
   a plain number — as an absent one does — so `"three"` cannot reach the callers' numeric tests.

## Pass 2 — findings: 0

Every caller of `declared_port` and `declared_contract` (session events, `ci`, `commit-msg` and
`sweep`, `rules check`, `evals run`, the `declared-contract` subcommand the commit hook asks) reads
the same values as before for every declaration without nested maps — AgentSmith's own (none), the
fixtures', KYC's and OTS's before their evals ports. With the maps, KYC and OTS read contract 3. The
reader handles strings with escaped quotes and braces, arrays, keys in any order and a missing file;
`awk` here is the BSD one, and the tests run the launcher itself, so CI's `mawk` exercises them too.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one reader, `decl_get`, behind both `declared_port` and `declared_contract`; no second parser.
Group 2 · Quality / safety — [x] checked — three tests on the shapes that broke (KYC's and OTS's evals port, keys in any order, an `_about` quoting `"gate": "none"`, escaped quotes, a missing or malformed contract); `launcher_declaration` mutations 3/3.
Group 3 · Architecture / hygiene — [x] checked — POSIX `awk`, no interpreter, as the launcher requires; every declaration without nested maps reads as before.
Group 4 · Process — [x] checked — design before the change; CHANGELOG under 2.2.3 with the hook-interface note; the release records name both fixes.
Group 5 · Intuitive UI — [x] n/a — no screen or control.
Group 6 · Signal integrity — [x] checked — a declared provider is no longer reported undeclared, and a declared contract no longer silently drops to 1.
Group 7 · Auth & session integrity — [x] n/a — no credentials or sessions.

Tests added: three in `scripts/test/test_gate_contract_v3.py`; `test_the_launcher_reads_each_port_apart` extracts the reader too.
Mutation-checked: `launcher_declaration` 3/3.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
Gates run: full `pytest` on the staged tree (2331 passed, 10 skipped); `ruff check .`; `bash -n` on the launcher; KYC's and OTS's declarations read as contract 3 by the new launcher (1 by the old); the self-test's knowledge-graph gate.

Levers reviewed: `declared-vs-enforced`, `validate-on-the-receiving-side`, `test-the-contract`, `grep-for-siblings`.

KG query: kg:e87475b5f3d3
