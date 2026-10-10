# Review — security-contract (C7)

Design: `.agent-rfc/designs/security-contract.md`
Levers: `docs/review-levers.md`

## Pass 1 — findings: 6

Read over the whole diff after the build, each finding verified in code before it was changed.

1. **SEC-AGENCY-001 and SEC-TOOL-001 did not validate against the schemas the contract publishes**
   (`declared-vs-enforced`). The protocol says each file "matches its schema"; the agency runner
   read keys loosely and the allowlist runner used `load_allowlist`, which skips a row it cannot
   read — a malformed row would be a tool quietly left off the list. The allowlist runner now
   validates with `gm.ToolAllowlist` first; the agency runner with `gm.AgencyManifest`.

2. **A tenant's `org-owned` row with no suite failed** (`docs-match-behaviour`). `registry.schema.json`
   and the protocol say `gap` and `org-owned` rows need no suite, but `_checked` ran every tenant row
   as `tenant_suite`, which fails without one. An `org-owned` row without a suite is now
   `not_applicable`, evidenced outside the repository.

3. **A leaking emitter that then exited non-zero read `not_gradable`, not `fail`**
   (`failure-mode-visibility`). `security/redaction.py` checked the exit code before looking at what
   arrived; a probe that reached the wire is the stronger fact and is now reported first.

4. **The moderation runner parsed `tenant.yaml` twice** (`no-copy-paste`): once through
   `declared_choice`, once by hand for the hook. One reader, `declared_value`, now serves both.

5. **`evidence_pack` took a `request` it never read** (`every-line-earns-its-place`). Removed.

6. **Sibling, out of this slice's scope** (`grep-for-siblings`, `environment-parity`): the evals port
   clears its threshold variables but not `PROMPT_DENYLIST_PATH`, which `runtime.prompt_guard`
   reads before the repository's own denylist — so the environment of whoever runs
   `agentsmith evals run --suite adversarial` can change the score. The security port clears it
   (`POSTURE_ENV`) before its guard suites run. Logged on the backlog for the evals contract.

## Pass 2 — findings: 3

Over the fixes of pass 1 and the whole branch again, scoped by what CI checks (`review-the-branch`).

1. **The repository's interpreter inherited the provider's source** (`environment-parity`,
   `implemented-not-invoked` of the decoupling). The setup action runs the provider with its own
   checkout first on `PYTHONPATH`, and a tenant's suite and moderation hook inherited it — KYC's hook
   would have imported AgentSmith's `runtime` at the provider's version instead of the one KYC pins.
   `repository_env` removes the provider's root before either runs; a test plants the path and a
   mutation restores it.

2. **Two behaviours pass 1 fixed were AgentSmith's, not the contract's** (`test-the-contract`): an
   `org-owned` tenant row without a suite, and a leak from an emitter that then exits badly. Both are
   promises of the protocol, so both are now conformance cases (33) — another provider is held to
   them — and the protocol states them.

3. **The moderation runner imported the provider's moderation API for a tenant run, where it does not
   run** (`every-line-earns-its-place`). Imported only where it is used.

## Pass 3 — findings: 3

Over pass 2's fixes, following the data rather than the files (`grep-for-siblings`).

1. **The emitter is the repository's code too, and still inherited the provider's source.** Pass 2
   kept AgentSmith's checkout off `PYTHONPATH` for the tenant's suite and hook, not for the
   redaction emitter — KYC's `telemetry_smoke.py` would have exported through the provider's
   `runtime.tracing`, not the version KYC pins. `repository_env` now takes the install root and
   serves all three; a test plants the path for the emitter.

2. **The suite needed a `watch` list only because its slowest test ran first**
   (`test_only_the_slow_suite_is_narrowed` failed on the staged tree). Every mutation but one is
   caught by a unit test in seconds; the minute-long conformance run now comes last in the file, and
   a unit test catches a registry that redefines a provider's control, the one mutation only
   conformance caught. No `watch`: the suite runs on every change, as every suite but
   `tenant_adopt` does.

3. **`contract/security/v1/protocol.md` was not declared reference documentation** (the artifacts
   gate). Declared in `extends.artifacts.reference`, as every other contract's protocol is;
   `.agenticframework/process-gates.json` added to the design's scope.

## Pass 4 — findings: 1

Over pass 3's fixes: the emitter's environment, the reordered tests, the declaration.

1. **A leak followed by a hang still read `not_gradable`** (`failure-mode-visibility`, a sibling of
   pass 1's third finding). Pass 1 put what reached the wire before the exit code, but an emitter that
   leaked and then ran past the timeout raised `TimeoutExpired`, and the `except` returned before the
   collector's exports were looked at. The run's outcome is now kept and judged after the wire, for a
   non-zero exit, a timeout and a failure to start alike; a test leaks and then hangs.

## Pass 5 — findings: 0

Over pass 4's fix: the run's outcome is kept as a reason and read only after the wire; nothing reads
the completed process outside the `try`; a start failure, a timeout and a bad exit are each judged
after the leak check, and the "a leak is excused" mutation is re-pointed at the new condition. The
whole branch read once more against the levers — no further finding.

## Sign-off

Group 1 · DRY & shared code — [x] checked — one implementation: `security_port.py` runs the harness's runners under the contract's terms instead of a second copy; `declared_value` is the one reader of `tenant.yaml` posture, `repository_env` the one rule for the repository's interpreter (suite, hook, emitter); the OTLP destination list lives once in `runtime/telemetry_contract.py`; every published schema is generated from `gate_models.py` and held to it by a test.
Group 2 · Quality / safety — [x] checked — 57 tests in `test_security_contract.py`; 33 contract cases, AgentSmith 33/33 from a checkout and 31/31 in an environment holding only `requirements-gate.txt` (before the two cases pass 2 added); an always-pass provider and one that runs its own code for a tenant shown failing; 11 mutations in `security_contract`, all caught.
Group 3 · Architecture / hygiene — [x] checked — no dependency added, and the port no longer needs `jsonschema`; the repository's suite, hook and emitter run in its own interpreter with the provider's source off its path; the probes are not credentials and none matches the P12 shapes; `run-security-checks.py` and `--check-redaction` unchanged for this repository and vendored tenants.
Group 4 · Process — [x] checked — design before code, the owner's two decisions recorded, amended four times while building; five review passes; backlog C7 Built and the evals sibling logged; archive entry; CHANGELOG; README ports table; User Manual; protocol declared as reference documentation; C6's design marked done.
Group 5 · Intuitive UI — [x] checked — each failed control is its own CI annotation naming the control; a gap is a warning; the summary says how many repository controls held and that the rest are gaps or not applicable; a leak names its kind and the profile.
Group 6 · Signal integrity — [x] checked — pass, fail, gap and not applicable are four row results and the verdict is over what ran; no non-strict mode; a provider row never decides a tenant's verdict; a leak is a failure whatever the emitter did after; a clean wire with no probe span is not gradable, not a pass; the environment sets no posture.
Group 7 · Auth & session integrity — [x] checked — no credential in the contract; the emitter's collector credential is removed for the loopback run; tenant text reaches CI as one annotation line per control, so it cannot start a workflow command.

Tests added: `scripts/test/test_security_contract.py` (57); `test_telemetry_contract.py` inventories `security_port.py`.
Mutation-checked: `security_contract` 11/11.
Fixtures re-pinned: `contract/security/v1/` new (fixture, cases, controls, probes, schemas); `fixtures/security/control_registry.json` gains `subject`; `scripts/security/schemas/risk_register.schema.json` replaced by the generated contract schema; `.agent-rfc/fixtures/knowledge_graph.json` rebuilt.
Gates run: full `pytest` on the staged tree (2387 passed, 10 skipped) and the affected modules again after pass 4 (110 passed); `ruff check .`; `mypy` (1.14.1); `verify_system.py --check-kg`; `agentsmith conformance --port security` from a checkout and from a gate-only environment; the launcher's mapping by hand in a scratch tenant; the provider against KYC Sentinel and OTS read-only. The `docs/DESIGN.md` repo-tree check was missed and failed in CI on the pull request (`scripts/security_port.py` absent from the tree); the entry added, and the job's gates after it — py_compile, redaction for both profiles, `--check-hooks`, `--check-kg`, the delivery evidence pack, the tree check — run locally, all passing (`run-the-gates-ci-lists`).

Levers reviewed: `declared-vs-enforced`, `implemented-not-invoked`, `environment-parity`, `failure-is-not-a-result`, `failure-mode-visibility`, `test-the-contract`, `grep-for-siblings`, `single-source-of-truth`, `every-line-earns-its-place`, `minimal-host-dependency`, `review-the-branch`.

KG query: kg:82c57c57cf00
