# Review — rules-contract (C4)

Design: `.agent-rfc/designs/rules-contract.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 7

Found while building, each verified in the code before it was changed.

1. **The design would have weakened the gate.** It said `adopt` would stop writing `registry`,
   `levers_doc` and `design_checklist`, and `sync` would drop them, because "absent, `registry`
   already means the provider's own". It does not: `Config.registry_declared` reads an absent
   `registry` as a config that **predates** the pillar and sign-off requirements, and `ci` then
   judges every commit by the older rules; an absent `levers_doc` is a repository path besides. The
   keys now take the value `"provider"` — the gate provider's own document, named without its path —
   which `process_gate.py` reads as the `@framework/` path it stands for. Design amended in place,
   with the reason (`gate-integrity`).

2. **Render and check could read the stack from different places.** The first cut read the stack
   from the scaffold manifest, which `tenant init` and `tenant adopt` write *after* rendering — so a
   repository's files were rendered by detection and checked by the manifest, and any difference
   was drift nobody made. Both now detect it from the files the repository commits, as the existing
   drift check always did; the pre-write that papered over it in `adopt` is gone
   (`environment-parity`).

3. **The provider's CI setup could not render.** `scripts/requirements-gate.txt` — what
   `setup-agentsmith` installs — had no YAML reader, and the catalogue is YAML: the new CI step would
   have answered "cannot run here" in every tenant. `pyyaml` added (already a framework dependency,
   so nothing new in the lock), and the test that pins that list now names it
   (`implemented-not-invoked`).

4. **`adopt` stopped seeding `.agent-history.log`.** It had come along as a side effect: the old
   render ran the generator's default mode in a scratch directory and copied back everything it
   wrote. The contract's render returns rule files only, so the log — which pillar 5 tells every
   agent to read — was silently no longer created, though the plan still said `create`. Seeding is
   now one function in the generator, called by its default mode and by `adopt`; a test asserts the
   file exists after adoption (`early-exit-keeps-the-record`).

5. **Two callers split the declared command differently.** `sync` used `shlex.split`, the launcher
   splits on whitespace — a quoted command would work in a sync and fail in CI. One reading now
   (whitespace, no quoting, as the gate's command already is), stated in the protocol
   (`single-source-of-truth`).

6. **Five mutation targets moved under this change** — three the design anticipated (the rules
   block, the generated-file test, sync's rule-file write) and two it did not: the launcher's gate
   lookup now appears twice, and sync's region test changed shape. All re-pointed at the code that
   now carries each property; the catalogue's every target counted before any run (`test-that-pins-a-defect`).

7. **`tenant adopt` still dropped the keys** after the design was amended — the first edit predated
   the amendment. Caught by the adopt and sync suites (the adoption commit was refused for citing no
   lever, its levers document now a missing repository path); `adopt` writes `"provider"`.

## Pass 2 — findings: 1

The full suite after pass 1: 5 failed, 2118 passed. Two were the command-reference rows, written
while that run was already past them; two pinned values this change replaced on purpose — the
`@framework/` registry an adopted config carried, and the wording that names a provider's document
("the gate provider's docs/…", not "your AgentSmith checkout") — and were re-pinned to the new ones,
not loosened. One was a defect:

1. **`generated_by_agentsmith` in `runtime/adopt.py` was left with no caller.** Placement moved into
   the contract's module and the plan now reads placement from the render itself, so the wrapper
   kept for it was dead. Removed (`every-line-earns-its-place`); `test_no_orphaned_entrypoints`
   is what caught it.

Mutation runs: `rules_contract` 7/7 caught; the moved `gate_contract` target caught.

## Pass 3 — findings: 1

Re-read the whole diff against the levers; ran the gates CI runs.

1. **mypy at the pinned version (1.14.1, the `lint` requirements) found five errors in
   `runtime/adopt.py`.** The candidate list mixed `Path` with an optional install, the module loader's
   spec was used without checking it exists, and `declared_rules` was typed `object` though it only
   ever returns a command or `"none"`. Typed honestly, and a spec that cannot load now raises
   `RulesUnavailable` — the same answer as a missing file — instead of an `AttributeError`. mypy: no
   issues in 47 files.

Mutation runs: the moved `tenant_adopt` and `framework_sync` targets — 4/4 caught. Conformance:
gate 5/5, 10/10, 15/15; rules 11/11. `ruff check .` clean.

## Pass 4 — findings: 0

The full suite after pass 3: 2178 passed, 10 skipped; the adopt, sync, scaffold and rules suites
again in full after the typing fix: 122 passed. Re-read `protocol.md` against `rules_port.py`, the
launcher and `sync` — the markers on their own lines, the two placements, the path rule (model and
schema refuse the same 17 paths and accept the same 7), absent-is-not-drift, the three launcher
outcomes, the whitespace split — and the CHANGELOG, manual, `process-gates.md` and README against
the code. Every mutation target in the catalogue matches.

## Pass 5 — findings: 2

CI on the pull request failed where the local full suite had passed — both checks read **tracked**
files, and the new ones were untracked when the suite ran.

1. **Two hand-rolled script loaders.** `scripts/rules_port.py` and `test_rules_contract.py` loaded
   `generate-ide-config.py` with their own four lines of `importlib`; the repository keeps one,
   `_shared.load_script`, and `test_scripts_has_exactly_one_script_loader` holds it to that. Both
   use it now.
2. **`scripts/rules_port.py` was missing from the Repository Structure tree** in `docs/DESIGN.md`,
   which the self-test's tree drift check compares with `git ls-files`. Listed.

Both checks were run here on the staged tree before this commit — the order that would have caught
them the first time.

## Pass 6 — findings: 0

`test_security_registry.py`, `test_rules_contract.py` (63 passed) and the self-test's tree check,
lifted from the workflow and run on the staged tree: 33 top-level and 115 second-level entries match.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one renderer behind the generator's flags, the port and `sync`; one placement module for adopt, sync, `--write` and the conformance runner; schemas generated from the models; the path rule is one rule in the model and the published pattern, pinned by a test that runs both.
Group 2 · Quality / safety — [x] checked — 53 tests in `test_rules_contract.py` plus adopt and sync tests (the plan's promises kept, a legacy config moved to `"provider"` and accepted by the tenant's own gate); 7 mutations in `rules_contract` and 5 re-pointed, all caught; conformance: AgentSmith 11/11, providers that ignore the notes or read the environment fail.
Group 3 · Architecture / hygiene — [x] checked — the provider runs its own scripts, never a tenant's vendored copy; the caller validates every path before writing any; `pyyaml` added only to the provider's CI install, already a framework dependency.
Group 4 · Process — [x] checked — design before code, amended in place where building proved it wrong (the registry); backlog row Built and C5 Next; archive entry; the protocol declared as reference documentation.
Group 5 · Intuitive UI — [x] checked — the CI step says which file drifted with a diff, how a provider gave no answer, or that none is declared; the deny names `agentsmith sync`.
Group 6 · Signal integrity — [x] checked — absent, drifted, not declared, declared none and no answer are five results; a render that fails is never an empty one; the gate keeps `registry` declared, so no tenant is judged by the older rules.
Group 7 · Auth & session integrity — [x] checked — no credential is read or written; a rules provider cannot write hooks, declarations or CI.

Tests added: `scripts/test/test_rules_contract.py` (53); `test_adopt_writes_every_file_its_plan_promises` in `test_tenant_adopt.py`; `test_an_adopted_config_naming_this_installs_paths_is_moved_to_provider_and_still_passes` in `test_framework_sync.py`; re-pinned `test_governed_tenant.py`, `test_process_gate.py` (registry value, the provider's document wording, `pyyaml` in the gate requirements).
Mutation-checked: `rules_contract` 7/7; re-pointed `tenant_adopt` 2, `framework_sync` 2, `gate_contract` 1 — all caught.
Fixtures re-pinned: `contract/rules/v1/` written new; `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
Gates run: full `pytest` (2178 passed, 10 skipped) — and, after CI found two misses on tracked files, the security registry, rules and tree-drift checks on the staged tree; `ruff check .` (0.15.20); `mypy` (1.14.1, pinned); `agentsmith conformance --contract 1|2|3` and `--port rules`; `python3 scripts/process_gate.py ci --base origin/main --head HEAD` before pushing.

Levers reviewed: `single-source-of-truth`, `environment-parity`, `two-owners-two-cadences`, `validate-on-the-receiving-side`, `denied-vs-missing`, `guards-must-be-able-to-fail`, `test-the-contract`, `declared-vs-enforced`, `gate-integrity`, `implemented-not-invoked`, `early-exit-keeps-the-record`, `every-line-earns-its-place`.

KG query: kg:04752d3b8956
