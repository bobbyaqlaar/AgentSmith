---
status: active
scope:
  - pyproject.toml
  - scripts/**
  - agentsmith/**
  - examples/**
  - templates/**
---
# Ruff's flake8-bandit rules (`S`) in the lint gate

## Problem

The lint gate (`ruff check .` in `.github/workflows/self-test.yml`) selects E, F, N, B, RUF and PLW1510. Security static analysis runs only as `bandit -ll` in `supply-chain.yml`, which reports medium severity and above, so the low-severity families — `subprocess` with a variable argv, partial executable paths, swallowed exceptions, `assert` in shipped code — are checked by nothing.

`pyproject.toml` recorded an earlier decision against `S`: 1429 findings, "almost all of it every subprocess call and every assert". That count included the test tree. Outside it, `S` raises 217 findings in the code the gate lints (S603 85, S607 55, S110 38, S310 14, S105 12, S101 5, S104 3, S608 2, S107 1, S112 1, S311 1). The owner has asked for the rules now, with every finding triaged.

## Approach

1. **Select `S`.** Test code (`agentsmith/test/**`, `scripts/test/**`, the scratch tenants' `tests/`) is exempt from S101 (assert is how pytest asserts), S603/S607 (the tests drive git and Python CLIs: that is what is under test), and S105/S106/S107 (fake tokens are fixtures). The six other test findings (S108, S310, S606) get inline reasons rather than a wider exemption.
2. **Triage every production finding, one at a time.** A `# noqa` is kept only where the finding is a false positive in this threat model, and it carries a one-line reason on the same line. The trust root is the operator: a value from the operator's own command line, environment or repository config gives them nothing they could not already do in their shell. A value from the network, a downloaded file or another tenant is not in that root.
3. **Fix the findings that are real.**
   - *Argument injection into git (CWE-88).* `gate_kg.changed_files` passes `--base REF` straight to `git diff`, so a ref spelled `--output=<path>` makes git write a file. The same shape is in `process_gate` (`git show REV:PATH`, `git cat-file -e BASE`) and `mutation_check.changed_files`. Each gets `--end-of-options` before the ref: valid refs behave the same, and an option-shaped ref is read as a ref and refused.
   - *URL schemes not restricted (S310), and tokens in clear text.* Operator-configured URLs reach `urlopen`, which also serves `file:` and `ftp:`, and plain http to another host carries the bearer token in clear. One helper, `compliance.is_web_url`, allows https to any host and plain http only to `localhost`, `127.0.0.1` and `::1` (owner's decision, 2026-11-19). It guards the audit write, the notifier webhook, `gate_tracing.ship` and the conformance receivers. `outbound_allowed` is unchanged: its callers report a refusal as "outside the declared boundary", which would misname a scheme refusal. `verify_sovereign_endpoint.py` runs without the runtime package, so it spells the same rule inline.
   - *`assert` in shipped code (S101).* Five asserts narrow types or state an invariant. Under `python -O` they vanish; each becomes an explicit check that raises.
4. **Owner's decision, 2026-11-19:** plain http to a non-loopback host is refused on these paths. This is a behaviour change for an operator whose portal, webhook, collector or model server is reached over plain http on a LAN: it now needs https (a TLS-terminating proxy will do). CHANGELOG says so. `agentsmith/intake.py` and `scripts/send_dev_record.py` already had their own https-or-localhost rule (without `::1`) and are left as they were.

## Pillars

- P1 applies — this design, written before the code; scope is `pyproject.toml` (the lint config) and the files the findings sit in, checked by `ruff check .` in `.github/workflows/self-test.yml`.
- P2 applies — ruff 0.15.20 is already pinned in `requirements-lint.txt`; the scheme helper extends `agentsmith/compliance.py`'s existing outbound guard rather than adding a module. No dependency added.
- P3 n/a — no new execution path; the fixes refuse inputs earlier on paths that already exist and are already traced where they were.
- P4 applies — `scripts/test/test_bandit_findings.py` holds each fixed defect: it fails on the tree before the fix and passes after; each fix mutation-checked by hand.
- P7 applies — Python only; no new models. The explicit checks replacing asserts keep mypy's narrowing, as in `agentsmith/compliance.py` (`is_web_url`).
- P8 n/a — the telemetry wire is untouched; `gate_tracing.ship` refuses a non-http(s) endpoint and says so in its result.
- P9 n/a — no orchestration change.
- P10 n/a — no model call added or rerouted.
- P11 applies — the triage is the untrusted-input review: each subprocess argument and URL is classified by where it comes from, and the reason is written next to the call. Outbound URLs go through `compliance.is_web_url` in `agentsmith/otlp.py`, `agentsmith/intake.py` and `scripts/send_dev_record.py`, pinned by `agentsmith/test/test_https_only_egress.py`.
- P12 applies — no credential moves, but a bearer token is no longer sent over plain http to another host: `scripts/send_dev_record.py` and `agentsmith/intake.py` refuse it before the token is attached; S105/S107 hits are environment-variable NAMES and fixture tokens, recorded as such in `scripts/test/test_bandit_findings.py`.
- P13 applies — the gate gets stricter, not weaker: a new rule family (`[tool.ruff.lint]` in `pyproject.toml`), test exemptions limited to the rules tests need (`per-file-ignores` in the same file), and every production waiver inline with its reason. RUF100 keeps each one honest.
- P14 n/a — no baseline, golden or fixture pins a projection this changes.
- P15 applies — a refused scheme is reported as refused (`ShipResult.errors`, `outbound_allowed` False, a raised error in the harness), never as a send that succeeded.
- P16 applies — `machine/policy.py`'s audit write already falls back to the local audit log when `outbound_allowed` is False; a refused scheme takes that path, so the event is kept.

## Deviations

none

## Dependencies

none

## Levers

- `security-gates-in-ci` — the low-severity bandit families enter the gate CI already runs.
- `no-query-from-a-value` — argv and SQL built from values are classified; the git ref case is fixed.
- `validate-on-the-receiving-side` — the scheme is checked where the URL is opened.
- `guards-must-be-able-to-fail` — asserts that vanish under `-O` become checks that cannot.
- `fix-the-class-not-the-case` — the git ref fix and the scheme fix are applied to every sibling the triage found.
- `prove-it-fails-first` — each fix has a test that fails on the old code.
