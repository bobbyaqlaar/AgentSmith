# Review — evals-contract (C6)

Design: `.agent-rfc/designs/evals-contract.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 6

Found while building, each verified before it was changed.

1. **`agentsmith evals` already existed** — HITL sync, then the scorecard. Registering the contract's
   `evals run` as a second subparser raised `conflicting subparser` at import, so every `agentsmith`
   command failed. One parser now: no verb keeps the old behaviour, `run` is the contract's verb,
   `--suite` without `run` is refused. Design amended.

2. **The judge's calibrated bar would have been dropped.** The design named three sources for a bar
   (request, `extends.evals`, the provider's default); KYC Sentinel declares its judge's `fail_below`
   per suite in `models.yaml` (0.95 for golden and fairness), calibrated for that grader. Dropping it
   would have loosened KYC's gate on the day it moved. It is a committed declaration, not the
   environment, so it stays — after `extends.evals`, before the default. Design amended; a test
   orders all four.

3. **A withdrawn judge model must not be maskable.** `run-evals.py` goes red when the configured
   model is no longer served, writing `no_verdict` and exiting 1. Read as `no_verdict`, a tenant's
   declared `no_verdict: warn` would turn a broken `models.yaml` green indefinitely. Mapped to `fail`
   with the reason, as are verdicts from more than one judge or rubric (exit 1, no result file).
   Design amended; a test per outcome of the scoring.

4. **`evals_port.py` emits span attributes and was not in the telemetry inventory**
   (`grep-for-siblings`): `test_every_name_the_framework_emits_is_catalogued` scans a fixed list of
   scripts. Added; `agent.evals.suite` falls under the catalogue's open `agent.` family and
   `agent.decision` is catalogued.

5. **A `fail` said only "see stderr"** (P15). The scorecard now names each bar missed and its
   number — the average under its floor, the worst pair parity, a same-text pair's spread, the
   hallucination flag rate, an unflagged planted control, the guard's miss rate. The conformance
   run's five failing cases each name the one bar their fixture breaks; the fairness case fails on
   spread alone, its average clearing the floor.

6. **The launcher put tenant-authored text into a workflow command** (P11). The reason quotes case
   ids and paths from the dataset; a newline in one would start a second `::` line of the tenant's
   choosing. `say` collapses the text to one line; a test plants `\n::warning::` in a reason.

Also while building: the conformance runner sends the fixture's absolute path as `cwd` (a relative
workdir resolved twice); a stale result file is removed before any verdict, not only before
scoring, so an ungradable suite never leaves last run's `pass` for the evidence pack.

## Pass 2 — findings: 3

1. **The stub judge's refusal was never exercised** (`test-that-cannot-fail`): AgentSmith's
   pre-check answers `no_verdict` for a missing key before calling the judge, so the 401 path the
   contract case relies on for other providers ran nowhere. A test calls the stub with and without
   its key.

2. **"Answered but exited non-zero" had no test.** The runner rejects a scorecard with a failing
   exit code, as the protocol says; a provider that prints a valid `pass` and exits 1 is now shown
   failing that case.

3. **The test file hand-rolled a script loader** (`single-source-of-truth`): the full suite's
   `test_scripts_has_exactly_one_script_loader` refused `importlib` in `test_evals_contract.py`.
   It loads the provider through `_shared.load_script`, once at import, so the tests that replace
   `load_script` for what the provider loads do not replace the provider itself.

## Pass 3 — findings: 0

Re-read against groups 1–7 after the fixes: the dataset schemas, scorecard and port are generated
from `gate_models.py` and held to it; the launcher's mapping, the provider's four verdicts, the bar
precedence and the environment's exclusion each have a test and a mutation; no further finding.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one scoring implementation: `evals_port.py` wraps `run-evals.py`'s `run_scorecard` and reads its result file, adding only the contract's terms; dataset, request, scorecard and port schemas generated from `gate_models.py` and held to it; `extends.evals` lives in the one `extends` schema the rules contract publishes; the provider loads through `_shared.load_script`.
Group 2 · Quality / safety — [x] checked — 68 tests in `test_evals_contract.py`; 17 contract cases, AgentSmith 17/17, an always-pass provider and one that exits 1 shown failing; 7 mutations in `evals_contract`, all caught.
Group 3 · Architecture / hygiene — [x] checked — no dependency added; the stub judge binds loopback and refuses a call without its key; a contract run judges the tenant's cases only and never generates an output; `run-evals.py` and the eval workflow templates unchanged.
Group 4 · Process — [x] checked — design before code, amended five times while building (the existing `evals` command, the judge's calibrated bar, a withdrawn model as `fail`, `extends` shared with the rules contract, scope); backlog C6 Built; archive entry; CHANGELOG; README ports table; protocol declared as reference documentation.
Group 5 · Intuitive UI — [x] checked — the scorecard's reason names each bar missed with its number, or why nothing was judged; the launcher says what to declare to let a suite warn, and a declared warning shows in CI as a warning that the suite proves nothing on the commit.
Group 6 · Signal integrity — [x] checked — pass, fail, no verdict and not gradable are four results; only a pass passes CI unless the tenant declared otherwise for that suite and verdict; a withdrawn judge model and mixed graders are failures no declaration hides; the environment sets no bar.
Group 7 · Auth & session integrity — [x] checked — the judge's credential is read by the variable `models.yaml` names and never enters the contract; the launcher's annotation is one line, so tenant text cannot start a workflow command.

Tests added: `scripts/test/test_evals_contract.py` (68); `test_telemetry_contract.py` inventories `evals_port.py`.
Mutation-checked: `evals_contract` 7/7.
Fixtures re-pinned: `contract/evals/v1/` new (fixture, cases, schemas); `contract/rules/v1/extends.schema.json` regenerated (the optional `evals` key); `.agent-rfc/fixtures/knowledge_graph.json` rebuilt, and again after rebasing onto main (#37, #38 and #39 merged), with the CHANGELOG entries of both kept.
Gates run: full `pytest` on the staged tree (2283 passed, 10 skipped); `ruff check .`; `mypy` (1.14.1); the self-test's tree check; `verify_system.py --check-kg`; `agentsmith conformance --port evals` against `agentsmith evals` and `scripts/evals_port.py`; the launcher's mapping exercised by hand in a scratch tenant.

Levers reviewed: `single-source-of-truth`, `declared-vs-enforced`, `failure-is-not-a-result`, `environment-parity`, `test-the-contract`, `test-that-cannot-fail`, `guards-must-be-able-to-fail`, `grep-for-siblings`, `one-verdict`.

KG query: kg:10f7a078a5c6
