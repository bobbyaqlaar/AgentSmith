# Review — telemetry-contract (C5)

Design: `.agent-rfc/designs/telemetry-contract.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 7

Found while building, each verified before it was changed.

1. **The provider answered with a vendored tenant's CLI — a C1 defect, latent until now.** Verifying
   OTS's spans with `--emitter` from OTS's own directory ran OTS's two-month-old `runtime/cli.py`,
   which has no `conformance` command. `python -m` puts the working directory first on the module
   path, ahead of `PYTHONPATH`; the `agentsmith` shim the CI setup action writes, the test suite's
   shim and the weekly sync workflow all ran `python -m runtime.cli` inside the tenant. In OTS's CI,
   `agentsmith gate ci` would have reached a CLI with no `gate`, and the weekly sync would have run
   OTS's own stale `sync`. All three run `python -P` (3.11+); two tests build each shim — the
   action's own shell lines, executed — and call it from a directory holding a decoy `runtime/`;
   a third fails on any shipped `-m runtime.cli` without `-P` (`grep-for-siblings`). The installed
   console script was never affected. Design amended, with both files added to its scope.

2. **The design undercounted the instruments** — eight, not eleven: the three retrieval instruments
   were missed. The inventory test now counts them; the design says so.

3. **A pre-contract emitter was reported twice** — by its own check and again as a missing required
   Resource attribute. The required-attributes check now leaves the contract attribute to its own
   check: one finding, one failure (`one-verdict`).

4. **A case aimed at an instrument the fixture never records.** The wrong-unit case changed
   `agentsmith.llm.duration`, which the representative run does not emit, so it judged nothing and
   "passed" for the wrong reason. Retargeted at `agentsmith.llm.ttft`, and a test now requires every
   check to be failed by some case (`test-that-cannot-fail`).

5. **"Inside a run" was untested.** Every span in the fixture carries `run.id` itself, so a judge
   that ignored ancestry passed every case. A case drops `run.id` and `tenant.id` from the tool span
   under the step that keeps them; the mutation that stops walking parents is caught.

6. **Pillar 8's own words named `runtime/otlp.py` as the way to emit**, which OTS's design met as
   soon as it stopped importing that module. The question and rule now name the contract and the
   standard variables; the registry is regenerated from them.

7. **Pinned mypy (1.14.1) found four errors** in `runtime/telemetry_contract.py` — an `Optional`
   family lookup, a loop variable reassigned from an `Optional`, a name reused across two types;
   and one line past the limit in the mutation catalogue. Typed honestly, renamed; behaviour
   unchanged.

The portal is TypeScript, which `scripts/mutation_check.py` does not drive: mutated by hand — the
contract attribute removed from its Resource (2 of 3 portal contract tests fail), and a read
renamed in `promotions.ts` (1 fails) — each restored and compared.

OTS, under its own design and review (`telemetry-contract-tenant.md` there): its template CLI passes
the contract 9/9 on plain OpenTelemetry, run from AgentSmith's directory.

## Pass 2 — findings: 3

The full suite after pass 1: 3 failed, 2209 passed.

1. **`telemetry_cases` had no caller outside the tests.** Rather than wire it somewhere for the
   orphan check's sake, every telemetry conformance run now opens with "the judge decides the
   contract's own cases": a report from a judge that disagrees with the contract it names is not a
   verdict on the emitter, and this is what says which (`test-the-contract`).
2. **A test that depended on the machine.** `test_design_new_writes_the_skeleton_the_gate_asks_for`
   compares the skeleton with this checkout's registry, but `design_new` reads a stale
   `~/.agent-framework` first — so changing P8's question failed it here and would pass in CI, where
   no install exists. The fixture pins `AGENTSMITH_DIR` to the checkout (`environment-parity`).
3. **C4's pull request failed CI on two checks that read tracked files** — a hand-rolled script
   loader in `rules_port.py` and its test, and `rules_port.py` absent from the Repository Structure
   tree — which the local run could not see while the files were untracked. Fixed on C4's own branch
   (`fix(contract): rules port loads scripts the one shared way`, pushed to #33) and this branch
   rebased onto it; here, `runtime/telemetry_contract.py` is added to the same tree, and the tree
   check and every test that reads `git ls-files` were run on the **staged** tree.

Mutation runs: `telemetry_contract` 10/10 caught, including the two shim mutations and the two
whose targets the typing fix moved. The self-test's quick gates — py_compile, the tree check,
redaction, hooks, the knowledge graph, delivery evidence, the delivery-model unit tests, shell
syntax — pass locally.

## Pass 3 — findings: 0

The full suite on the staged tree: 2215 passed, 10 skipped. Re-read `protocol.md` against
`runtime/telemetry_contract.py` and the conformance runner — the Resource, identity inside a run and
its inheritance, kinds, conditionals, types, instruments, nothing-received, the loopback receiver's
caps — and the CHANGELOG, manual, README and DESIGN.md against the code. Every mutation target in
the catalogue matches. ruff clean; mypy 1.14.1: no issues in 48 files; the portal's `npm test` and
`tsc --noEmit` pass.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one catalogue; its schema generated from the model; the emitter inventory, the portal's two pins and the Wire Contract table pin all read the same file; the judge is the one implementation the conformance runner, the cases and the tests use.
Group 2 · Quality / safety — [x] checked — 38 tests in `test_telemetry_contract.py`, 3 portal tests; 15 contract cases decided as written, and each check failed by at least one; 10 mutations in `telemetry_contract`, all caught; two portal mutations by hand, caught.
Group 3 · Architecture / hygiene — [x] checked — no dependency added (the OTLP decoder ships with the exporter); the receiver binds loopback, caps every body and the run; the shims run `-P`, so a vendored tenant's `runtime/` never answers for the provider.
Group 4 · Process — [x] checked — design before code, amended for the shim defect and the instrument count; backlog C5 Built, C6 Next; archive entry; protocol declared as reference documentation; OTS's change under its own design and review there.
Group 5 · Intuitive UI — [x] checked — the report names each promise as a check, lists unknown names and payload attributes as notes, and says "nothing was judged" rather than passing an empty run.
Group 6 · Signal integrity — [x] checked — pre-contract, another contract, nothing received, not OTLP and the judge disagreeing with its contract are distinct results; a missing optional attribute is "not emitted", never a fault.
Group 7 · Auth & session integrity — [x] checked — no credential is read; `--emitter` removes the emitter's own destinations and headers, so nothing it emits leaves the machine during the run.

Tests added: `scripts/test/test_telemetry_contract.py` (38), `scripts/test/telemetry_emitter.py` (the reference emitter), `portal/test/telemetryContract.test.ts` (3); `test_cli_approve.py`'s fixture pinned to the checkout; `test_process_gate.py` unchanged.
Mutation-checked: `telemetry_contract` 10/10; portal by hand — the contract attribute and a read, each caught.
Fixtures re-pinned: `contract/telemetry/v1/fixture.json` generated new from the runtime library; `templates/governance.json` regenerated for P8; `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
Gates run: full `pytest` on the staged tree (2215 passed, 10 skipped); `ruff check .` (0.15.20); `mypy` (1.14.1); portal `npm test` and `npx tsc --noEmit`; the self-test's tree check and every test reading `git ls-files` on the staged tree; `agentsmith conformance --port telemetry --emitter` against the library, a plain-OpenTelemetry stub and OTS's template CLI; `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `single-source-of-truth`, `pin-unremovable-duplicates`, `declared-vs-enforced`, `denied-vs-missing`, `test-the-contract`, `guards-must-be-able-to-fail`, `validate-on-the-receiving-side`, `grep-for-siblings`, `one-verdict`, `test-that-cannot-fail`, `environment-parity`.

KG query: kg:7a6446eef194
