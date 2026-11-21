---
status: active
scope:
  - pyproject.toml
  - scripts/**
  - agentsmith/**
  - examples/**
  - templates/**
  - docker-compose.yml
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
   - *URL schemes not restricted (S310), and tokens in clear text.* Operator-configured URLs reach `urlopen`, which also serves `file:` and `ftp:`, and plain http to another host carries the bearer token in clear. One helper, `compliance.is_web_url`, allows https to any host and plain http only to `localhost`, `127.0.0.1` and `::1` (owner's decision, 2026-11-19). It guards the audit write, the notifier webhook, `gate_tracing.ship` and the conformance receivers. `outbound_allowed` is unchanged: its callers report a refusal as "outside the declared boundary", which would misname a scheme refusal. `verify_sovereign_endpoint.py` runs without the runtime package, so it uses `scripts/_shared.py`'s copy, pinned by `agentsmith/test/test_https_only_egress.py` (Pass 7).
   - *`assert` in shipped code (S101).* Five asserts narrow types or state an invariant. Under `python -O` they vanish; each becomes an explicit check that raises.
4. **Owner's decision, 2026-11-19:** plain http to a non-loopback host is refused on these paths. This is a behaviour change for an operator whose portal, webhook, collector or model server is reached over plain http on a LAN: it now needs https (a TLS-terminating proxy will do). CHANGELOG says so. Pass 5 extended the rule to the OTLP exporter (`agentsmith/otlp.py`), and `agentsmith/intake.py` now calls `is_web_url`; `scripts/send_dev_record.py` keeps a stdlib-only copy that now also accepts `::1` (Pass 7 moves it to `scripts/_shared.py`).

## Pass 6 fixes

Defect class (`fix-the-class-not-the-case`): the URL-scheme rule accepts inputs it should refuse — unparsed (a malformed address such as `http://[::1:6006` raises `ValueError` out of `urlparse` instead of being refused), hostless (`https://`, `https:evil.com` pass with no host), or unguarded at the caller (shipped config and docs still name plain http to another host, which the exporter now refuses).

- `compliance.is_web_url` returns False when the address does not parse and requires a non-empty host for both schemes. Every caller that checks it first (`agentsmith/otlp.py`, `agentsmith/intake.py`, `agentsmith/machine/policy.py`, `agentsmith/conformance.py`, `scripts/notifier.py`, `scripts/gate_tracing.py`) inherits the fix, so the OTLP path logs its refusal instead of crashing tracer set-up.
- `scripts/send_dev_record.py`'s inline copy does the same and returns exit 1 (a refusal) rather than raising. Parity across the new cases is pinned by `agentsmith/test/test_https_only_egress.py`.
- Shipped config and docs move the OTLP/Phoenix collector address to https placeholders and say the collector must serve TLS: `templates/uae-sovereign/env.example`, `docs/team-observability.md`, `docs/UserManual.md`, and the comment in `docker-compose.yml` (not its Node-portal setting, which does not go through `agentsmith/otlp.py`).
- Routes checked: grep for `is_web_url`, `safe_portal_url`, `urlparse`, `urllib.request.Request`, `OTEL_EXPORTER_OTLP` over `agentsmith/` and `scripts/`, tests excluded.

Not covered by this fix: the token-sending sites with no scheme guard (`ops_contract.py`, `llm_gateway.py`, `compliance_port.py`, `dead_letter.py`, `cost_router.py`, `verify_ttft.py`), reported separately; `scripts/verify_sovereign_endpoint.py`'s inline copy, left as is (Pass 7 corrects this bullet: the copy does not refuse a hostless address — `https://` and `https:evil.com` reach `urlopen` — and a malformed one raises `Invalid IPv6 URL` rather than the rule's refusal; Pass 7 fixes it); `scripts/compliance_checks.py`'s `urlparse(...).hostname` on a declared endpoint, a gate check rather than a send.

## Pass 7 fixes

Owner decisions: Q2 (fix the TLS-front proxy target in this change) — yes. Q1 (does the https-or-loopback rule extend to model calls?) — **strict**: the full https-or-loopback rule everywhere, no narrower credential-keyed variant. In this change that reaches the sovereign probe and the shipped template; the gateway's own model path does not yet enforce it (deferred, below).

Defect classes (`fix-the-class-not-the-case`):

- **A.** A secret (bearer token or secret webhook URL) is sent to an operator-configured address whose only gate is `compliance.outbound_allowed`, a residency check that allows everything with no profile. Nothing refuses plain http to another host.
- **C.** `urlparse(x).hostname` read without catching `ValueError`: a malformed declared endpoint turns a verdict into an exception.
- **D.** A documented reverse proxy points past the auth layer (Phoenix's 6006 instead of the sidecar's 6007), so following the doc publishes Phoenix unauthenticated.
- **E.** One contract (the `send_dev_record` URL rule) pinned twice, with diverging case lists.
- **B.** Pass 6's class in the last unfixed copy: `scripts/verify_sovereign_endpoint.py`'s inline rule let a hostless address (`https://`, `https:evil.com`) reach `urlopen`, and a malformed one raised `Invalid IPv6 URL`, naming no setting. The shipped `templates/uae-sovereign/env.example` set `OLLAMA_BASE_URL` to plain http on another host, which that same rule refuses.

Routes checked:

- A: `grep -rnE 'Bearer |"Authorization"|WEBHOOK_URL|x-api-key'`, `grep -rnE 'httpx\.(post|get|put|stream|Client|AsyncClient)\(|client\.(post|stream|get)\(|urlopen\(|requests\.(post|get)\('` and `grep -n 'is_web_url'` over `agentsmith/` and `scripts/`, tests excluded. Found beyond the first list: `agentsmith/conformance.py::run_runtime`, `agentsmith/mcp_pin.py::_fetch_http`, `agentsmith/provider_dispatch.py` (Vertex, Huawei).
- B: `grep -rnE '\.hostname\b'` and `grep -rn 'LOOPBACK\|"localhost", "127.0.0.1"'` over `agentsmith/` and `scripts/` — the rule lived in `compliance.is_web_url` and in inline copies in `scripts/send_dev_record.py` and `scripts/verify_sovereign_endpoint.py`; `grep -rn 'ollama.uae.internal'` — one shipped value.
- C: `grep -rnE 'urlparse\([^)]*\)\.(hostname|port)'` — three sites; `grep -rnE '\.hostname\b'` — the two-step forms are already in a try.
- D: `grep -n '6007\|6006\|reverse_proxy\|proxy_pass' docs/team-observability.md docs/UserManual.md caddy/Caddyfile docker-compose*.yml` — the Nginx block in §4 has the same fault.
- E: `grep -rn 'test_https_only_egress\|the_portal_address_rule'` over `agentsmith scripts docs .agent-rfc CHANGELOG.md`.

Fixed:

- A-i `agentsmith/ops_contract.py::send`, A-ii `agentsmith/llm_gateway.py::_report_run_status` (legacy route), A-iii `scripts/compliance_port.py::exchange`, A-iv `agentsmith/dead_letter.py::_notify`, A-v `agentsmith/conformance.py::run_runtime` call `compliance.is_web_url` before `outbound_allowed`, and say the refusal once, naming the setting. The dead-letter refusal names the variable, never the URL (the URL is the secret). `agentsmith/dead_letter.py::_report` inherits A-i. `agentsmith/test/test_context_propagation.py` moves its portal to https.
- C: one helper, `compliance.url_host`, used by `compliance.require_inside_boundary`, `compliance.guard_model_call` and `scripts/compliance_checks.py::residency`. A malformed endpoint is a named `fail` and a `ComplianceRefused("OB-RESIDENCY")`, not a `ValueError`.
- D: `docs/team-observability.md` › Caddyfile and › Nginx Alternative proxy `localhost:6007`, with one sentence under › TLS / HTTPS saying why.
- B: one stdlib copy, `scripts/_shared.py::is_web_url` (the `agentsmith/` ↔ `scripts/` boundary is real, so two copies remain: it and `compliance.is_web_url`), used by `scripts/verify_sovereign_endpoint.py::_chat` and `scripts/send_dev_record.py`, and pinned to the runtime rule by `agentsmith/test/test_https_only_egress.py::test_scripts_shared_rule_matches_the_one_rule`; `test_shared_imports_only_stdlib` keeps `_shared` free of third-party imports. The probe's refusal names `OLLAMA_BASE_URL` / `HF_BASE_URL`. `templates/uae-sovereign/env.example` now ships `OLLAMA_BASE_URL=https://ollama.uae.internal`, with a comment that a TLS-terminating proxy must front Ollama; `scripts/test/test_bandit_findings.py::test_the_shipped_sovereign_template_passes_the_probe_rule` holds it.
- E: `agentsmith/test/test_https_only_egress.py` keeps the one parity test, with the five cases only the intake copy had; the copy in `agentsmith/test/test_intake.py` is deleted; the `agentsmith/intake.py::safe_portal_url` docstring names the one pin.

Deferred under Q1 strict: the gateway's model path does not yet enforce the same rule — `agentsmith/llm_gateway.py` model calls (`_resolve_endpoint`), `scripts/cost_router.py`, `agentsmith/provider_dispatch.py` Vertex and Huawei. httpx already refuses non-web schemes there; what is missing is the refusal of plain http to another host. Backlog row in `docs/PRODUCT_BACKLOG.md`, trigger: a sovereign tenant puts a credential-bearing model server on another host, or before `encrypted-in-transit` is claimed for the model path. Until then the probe and the gateway disagree on a plain-http LAN `OLLAMA_BASE_URL`: the probe refuses it, the gateway serves it.

Not covered: `agentsmith/mcp_pin.py::_fetch_http` (MCP headers can carry a credential, but loopback http MCP servers are common and need a narrower rule — backlog row); the legacy route's existing silent `outbound_allowed` refusal in `_report_run_status` (pre-existing — backlog row); `docker-compose.auth.yml`'s all-interfaces bind of the auth sidecar (pre-existing — backlog row); unclassified model calls under a profile with a malformed endpoint (httpx refuses them with `InvalidURL`); `scripts/verify_ttft.py` (sends no secret, and httpx refuses non-web schemes).

## Pass 7 follow-ups

Two items found while testing the Pass 7 fixes, finished before the independent review.

- **F. `sys.path` leak.** `agentsmith/cli.py::gate_ides_module`, `agentsmith/sync.py::_shared_files` and `agentsmith/adopt.py::adopt` insert `<framework>/scripts` at `sys.path[0]` and never remove it. When the framework is the machine's installed copy (`~/.agent-framework`, chosen by `cli._framework_dir` when `AGENTSMITH_DIR` is unset), every later `import notifier`, `import _shared` and so on in the same process resolves to that stale copy: in a test run the bandit webhook and probe tests then test the wrong file. Defect class (`fix-the-class-not-the-case`): a process-global path mutated for one import and left behind. One context manager, `cli.framework_scripts_on_path(framework)`, inserts the entry only if absent and removes what it inserted in a `finally`; all three sites use it. `gate_ides_module` returns a module object: `gate_ides` imports `gate_models` at module scope only, so nothing it needs later resolves through the path once the block exits. `agentsmith/test/conftest.py` gets an autouse fixture that pins `AGENTSMITH_DIR` to this checkout (a test that wants another framework still sets it itself) and restores `sys.path` after each test. Test first: `agentsmith/test/test_framework_scripts_path.py` fails on the old code (the entry is left on `sys.path`). The helper also removes copies of the entry added inside the block. Routes checked: `grep -rn 'path.insert\|path.append\|sys.path\['` over `agentsmith/` and `scripts/`, tests excluded. Left as they are, on purpose:
  - `agentsmith/machine/governance.py::_gate_module` inserts only if absent and keeps the entry, because `gate_steps.run` imports `gate_history` when it is called. Removing the entry would make the gates-run record fail silently (that import is fail-open). The reason is now a comment at the site.
  - `scripts/rules_port.py` inserts its own directory at module scope, and `_generator` and `_traced` import `_shared` and `gate_tracing` when called. So `adopt.rules_port` executing it leaves one entry for the framework it loaded. The test loads it first, so it measures only the three sites above.
  - `agentsmith/machine/ops.py::_shared` inserts only if absent. What leaks there is `sys.modules["_shared"]`, not the path: it prefers `~/.agent-framework` over `AGENTSMITH_DIR`, so a run that reaches it caches the install's `_shared`. Removing the path would not undo that. Backlog row.
  - `agentsmith/moderation.py` inserts only if absent, process-wide on purpose. `agentsmith/replay_webhook_server.py` and the `scripts/` entry points insert their own directory once at module scope.
  - The `sys.modules` cache in general: `gate_ides_module(framework)` returns whichever `gate_ides` the process imported first. The CLI uses one framework per process, so that is acceptable there.
- **G. `docs/team-observability.md` › Update developer endpoints** set the collector endpoint behind the auth sidecar but gave no credential, so an export following it is refused with 401. It now shows `OTEL_EXPORTER_OTLP_HEADERS` with a basic-auth placeholder, and §2.2 points to it.

## Pass 8 fixes

Independent review (Pass 8), seven findings, each confirmed in code before fixing.

- **H. A redirect carries the token past the rule** (`encrypted-in-transit-and-at-rest`, `fix-the-class-not-the-case`). `agentsmith/machine/policy.py::audit_log_event` and `scripts/verify_sovereign_endpoint.py::_chat` check the configured URL, then open it with plain `urlopen`. That follows a 3xx and copies `Authorization` onto the next request. One handler that does not follow, `compliance.NoRedirect`, with a stdlib copy `scripts/_shared.py::NoRedirect` for the standalone probe. A redirect then answers as its own status (`HTTPError`): the audit event falls back with `ops_portal_write_failed`, and the probe fails. The existing handlers in `intake`, `send_dev_record` and `conformance` stay as they are: the first two raise an error naming their variable, and curated mutations pin their openers. Routes checked: `grep -rn 'urlopen(' agentsmith scripts` (tests excluded), keeping the calls that attach a credential. `notifier` and `gate_tracing.ship` attach none, and urllib drops the POST body on a 302. The httpx callers do not follow by default, and `ops_contract`/`compliance_port` say so explicitly.
- **I. An operator URL is printed with its userinfo** (`secrets-have-one-home`). The docs tell operators to put the sidecar password in `AGENT_PHOENIX_ENDPOINT` (`https://ops:<password>@host`), and refusal and status messages printed the URL whole. One helper, `compliance.display_url` (stdlib copy `scripts/_shared.py::display_url`, pinned for parity), keeps scheme, host, port and path and drops userinfo, query and fragment. It is used in every message that names an operator-configured URL in the files this change touches:
  - `agentsmith/otlp.py`: scheme, boundary and not-installed messages;
  - `scripts/gate_tracing.py`: refusal, connection error, and the status line;
  - `agentsmith/machine/ops.py`: the status line;
  - `agentsmith/compliance.py`: the two `ComplianceRefused` messages;
  - `agentsmith/conformance.py`;
  - `agentsmith/ops_contract.py`;
  - `scripts/compliance_checks.py`: residency;
  - `scripts/verify_sovereign_endpoint.py`.

  `ShipResult.endpoint` keeps the real URL, because it is what `ship` sends to. Only its rendering is changed.
- **J. §3.3's header reaches only the SDK exporter.** `scripts/gate_tracing.py::ship` sends no `OTEL_EXPORTER_OTLP_HEADERS`, so behind the auth sidecar gate spans are kept, not shipped. This was already the case before: the old documented `http://ops:<pw>@host:6007` failed in urllib too. §3.3 and the CHANGELOG now say what the header covers. Sending the header from `ship` is a backlog row, because it needs the no-redirect opener and a header parser of its own. §8's `px.Client` example moves to https and says the client must send the sidecar's credential.
- **K. The notifier drops a refused webhook without a word** (`failure-mode-visibility`). `scripts/notifier.py::_send_webhook` now writes one stderr line naming `AGENT_NOTIFY_WEBHOOK`, never the URL (the URL is the secret), for a scheme refusal and for a boundary refusal.
- **L. A boundary refusal of the audit write is recorded as `ops_portal_not_configured`** (`ambiguous-signals`). It is now `ops_portal_outside_boundary`, in `agentsmith/machine/policy.py` and `docs/DESIGN.md`.
- **M. The adopt/sync `sys.path` test could not catch an insert-if-absent leak**, because `pytest.ini`'s `pythonpath` already holds `scripts/`. The test now takes the framework's `scripts/` off `sys.path` before measuring.
- **N. A wrong noqa reason**: `agentsmith/machine/ops.py::_http_ok` is passed the operator's `AGENT_PHOENIX_ENDPOINT`, not only this module's own local URLs. The reason now says so: a GET that carries no credential. That health check reports a userinfo URL or an auth-sidecar URL as offline. That was already the case before this change, and it is a backlog row.

## Pass 9 fixes

Same independent reviewer, five findings, each confirmed before fixing.

- **O. A `user:password` in the address crashes urllib with the password in the error** (`secrets-have-one-home`, `test-the-contract`). The docs prescribed `AGENT_PHOENIX_ENDPOINT=https://ops:<password>@<phoenix-host>`, which passes `is_web_url`. urllib then raises `http.client.InvalidURL("nonnumeric port: '<password>@host'")`. That is neither `URLError` nor `OSError`, so `gate_tracing.ship` let it out of session start, with the password in stderr. The same holds for `intake._call`, `send_dev_record`, `conformance._post_status` and `verify_sovereign_endpoint._chat`. Two fixes:
  - Each of those urllib sites catches `http.client.InvalidURL` and reports it with `display_url`. The report says that a credential in the address cannot be sent this way, and names `OTEL_EXPORTER_OTLP_HEADERS` where it applies.
  - The docs stop prescribing userinfo: `docs/team-observability.md` › Configure each developer and › Configure CI, and `docs/UserManual.md`. They give the header instead.

  The ship test now runs real urllib against that address. Routes checked: `grep -rn 'except (urllib.error.URLError, OSError)'` over `agentsmith/` and `scripts/`, tests excluded, kept where an operator address reaches urllib. `policy`, `notifier` and `machine/ops._http_ok` already catch `Exception`. httpx accepts userinfo.
- **P. The intake refusal still printed the raw URL.** `agentsmith/intake.py::fetch` now uses `display_url`.
- **Q. `agentsmith/machine/ops.py` imported `compliance`, and so pydantic, at module scope.** `agentsmith/machine/` is import-light by its own `__init__` and `docs/DESIGN.md`. It now imports `display_url` inside `_shown`, as `policy` does. A test holds the package import-light.
- **R. `display_url` showed a password containing `/`, `?` or `#`.** `urlparse` ends the netloc at the first of these, so `https://ops:123/s3cr3t@host` read as host `ops`, port 123. The rule now: an `@` anywhere after the netloc, or an `@` with no host, gives a placeholder, because the userinfo cannot be told apart from the rest.
- **S. The hostless placeholder dropped the only clue** (`phoenix:6006`, a compose name with no scheme). A hostless address with no `@` in it is now shown as written, without query or fragment. It carries no userinfo to drop.

## Pass 10 fixes

Same independent reviewer, three findings, each confirmed before fixing.

- **T. `conformance.run_record_receiver` was missed by O**, and the ops harness read an unopenable address as "answered 0" (`fix-the-class-not-the-case`, `outage-is-not-a-finding`). Both now raise a `ValueError` that names the problem, as their scheme refusals already do. `run_record_receiver`'s report target is `display_url(url)`. The CLI's record and ops conformance handlers catch `ValueError` and print it, exit 2, instead of a traceback. That also covers the existing scheme refusal. Routes checked: `grep -n 'except (urllib.error.URLError, OSError)' agentsmith/conformance.py`, all three sites.
- **U. A bad port passed the rule, then was reported as a password problem** (`screens-tell-the-truth`). Examples: `:6006x`, `:99999`, `:-1`. Two fixes:
  - `is_web_url` reads `.port` inside its `try` (both copies, parity-pinned), so the rule refuses a bad port.
  - One message helper, `unopenable(url, hint)` (`compliance.unopenable`, stdlib copy in `scripts/_shared.py`), names a user:password, with the site's credential hint, only when the address holds an `@`. Otherwise it says a control character. Used at the six `InvalidURL` sites.

  `display_url` shows an address that does not parse, but holds no `@`, as written without query or fragment, the same rule as the hostless case. So the value a typo is in stays visible.

## Pass 11 fixes

Same independent reviewer, two findings, both confirmed before fixing.

- **V. A bad port is refused as a scheme problem** (`screens-tell-the-truth`). Since U, `http://localhost:600600` is refused, with "must be https, or http to this machine", which is false. One phrase helper, `web_url_refusal(url)` (`compliance`, stdlib copy in `scripts/_shared.py`, parity-pinned), returns the rule's phrase, or "has a port that is not one (0–65535)" when only the port fails. It replaces the hand-written phrase at every `is_web_url` refusal message: `intake`, `otlp`, `llm_gateway` (legacy route), `ops_contract`, `conformance` ×3, `dead_letter`, `notifier`, `gate_tracing`, `compliance_port`, the probe and `send_dev_record`. The otlp messages move from "is not https (or http to this machine)" to the one phrase, and the two egress tests that filter on it move with them. `machine/policy`'s reason code stays `ops_portal_url_not_https`: a reason code names the rule that refused, not the cause, and `docs/DESIGN.md` lists it that way. Routes checked: `grep -rnE 'must be https|is not https|not an https'` over `agentsmith/` and `scripts/`, tests excluded. `ops_contract`'s `hitl.replay_webhook_url` note is a different check (`startswith("https://")` on a committed tenant value, no port read), left as is.
- **W. The conformance CLI's `ValueError` catch swallowed harness bugs** (`failure-mode-visibility`). It now catches only `conformance.ReceiverRefused` (a `ValueError`), raised by the receiver-address refusals: the scheme refusal, `unopenable`, and so the bad port too, in `run_record_receiver` and `_post_status`. A harness or contract bug traces back as before. Test: a patched `ops_case_message` that raises `ValueError` still raises out of `cli.main`.

## Pass 12 fixes

- **X. `web_url_refusal` had no "no host" cause, and the probe appended ", with a host"** (`screens-tell-the-truth`). `https://` was refused with "must be https", which is false, and the probe said "has a port that is not one, with a host". The helper now names the first thing the operator must change, in this order:
  1. "does not parse as an address";
  2. the rule, for a scheme that is neither https nor http;
  3. "has no host";
  4. the rule, for plain http to another host;
  5. the bad port.

  So `ftp://host:99999` and `http://10.0.0.5:99999` are told the rule first. The port is said only once the rest would pass. The probe no longer appends to the phrase. The parity test now holds each case to its expected cause, not two buckets. Tests that matched "must be https" for a hostless or unparseable address now match the cause they get.

## Pillars

- P1 applies — this design, written before the code; scope is `pyproject.toml` (the lint config) and the files the findings sit in, checked by `ruff check .` in `.github/workflows/self-test.yml`.
- P2 applies — ruff 0.15.20 is already pinned in `requirements-lint.txt`; the scheme helper extends `agentsmith/compliance.py`'s existing outbound guard rather than adding a module. No dependency added.
- P3 n/a — no new execution path; the fixes refuse inputs earlier on paths that already exist and are already traced where they were.
- P4 applies — `scripts/test/test_bandit_findings.py` holds each fixed defect: it fails on the tree before the fix and passes after; each fix mutation-checked by hand. Pass 7 adds the token-sending-site tests to `scripts/test/test_bandit_findings.py`, the TLS-front test to `agentsmith/test/test_https_only_egress.py`, and the malformed-endpoint tests to `scripts/test/test_compliance_checks.py` and `agentsmith/test/test_compliance_runtime.py`. The `sys.path` leak (F) is held by `agentsmith/test/test_framework_scripts_path.py`, and the suite is isolated from the machine's install by the autouse fixture in `agentsmith/test/conftest.py`.
- P7 applies — Python only; no new models. The explicit checks replacing asserts keep mypy's narrowing, as in `agentsmith/compliance.py` (`is_web_url`).
- P8 n/a — the telemetry wire is untouched; `gate_tracing.ship` refuses a non-http(s) endpoint and says so in its result.
- P9 n/a — no orchestration change.
- P10 applies — no model call added or rerouted, but the owner's Q1 (strict) puts the https-or-loopback rule on the model path: `scripts/verify_sovereign_endpoint.py` enforces it (`scripts/test/test_bandit_findings.py`) and `templates/uae-sovereign/env.example` ships an https model address; the gateway's own model calls do not yet enforce it, recorded in `docs/PRODUCT_BACKLOG.md`.
- P11 applies — the triage is the untrusted-input review: each subprocess argument and URL is classified by where it comes from, and the reason is written next to the call. Outbound URLs go through `compliance.is_web_url` in `agentsmith/otlp.py`, `agentsmith/intake.py`, `agentsmith/ops_contract.py`, `agentsmith/llm_gateway.py` (`_report_run_status`), `scripts/compliance_port.py`, `agentsmith/dead_letter.py` and `agentsmith/conformance.py` (`run_runtime`), and, through `scripts/_shared.py`'s stdlib copy, `scripts/send_dev_record.py` and `scripts/verify_sovereign_endpoint.py`, pinned by `agentsmith/test/test_https_only_egress.py`.
- P12 applies — no credential moves, but a bearer token is no longer sent over plain http to another host: `scripts/send_dev_record.py` and `agentsmith/intake.py` refuse it before the token is attached; S105/S107 hits are environment-variable NAMES and fixture tokens, recorded as such in `scripts/test/test_bandit_findings.py`. Pass 7: `OPS_PORTAL_TOKEN`, `OPS_PORTAL_SYNC_TOKEN`, `AGENTSMITH_RUNTIME_TOKEN` and the Slack/Teams webhook URLs are no longer sent over plain http to another host (`scripts/test/test_bandit_findings.py`); the dead-letter refusal names the variable, never the URL. Pass 8: the audit write and the sovereign probe no longer follow a redirect with the token (`compliance.NoRedirect`, `scripts/_shared.py::NoRedirect`); messages naming an operator address drop its userinfo (`compliance.display_url`), so a sidecar password in `AGENT_PHOENIX_ENDPOINT` reaches no log or session context (`agentsmith/test/test_https_only_egress.py`).
- P13 applies — the gate gets stricter, not weaker: a new rule family (`[tool.ruff.lint]` in `pyproject.toml`), test exemptions limited to the rules tests need (`per-file-ignores` in the same file), and every production waiver inline with its reason. RUF100 keeps each one honest.
- P14 n/a — no baseline, golden or fixture pins a projection this changes.
- P15 applies — a refused scheme is reported as refused (`ShipResult.errors`, `outbound_allowed` False, a raised error in the harness, the OTLP exporter's ERROR log asserted in `agentsmith/test/test_https_only_egress.py`), never as a send that succeeded; a malformed address is a refusal, not a crash. Pass 7: a malformed declared endpoint is a named `fail` (`scripts/test/test_compliance_checks.py::test_residency_names_an_endpoint_that_does_not_parse`) and a `ComplianceRefused`, not a `ValueError` (`agentsmith/test/test_compliance_runtime.py`).
  Pass 8: a refused `AGENT_NOTIFY_WEBHOOK` is said on stderr by variable name, and an audit write the boundary refused is recorded as `ops_portal_outside_boundary`, not `ops_portal_not_configured` (`scripts/test/test_bandit_findings.py`).
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
- `secrets-have-one-home` — the dead-letter refusal logs the variable name, never the webhook URL.
- `encrypted-in-transit-and-at-rest` — portal and webhook secrets no longer cross a network in clear text.
- `outage-is-not-a-finding` — an endpoint that does not parse is its own named problem, not "could not run".
- `pin-unremovable-duplicates` — `scripts/_shared.py::is_web_url` and `compliance.is_web_url` are pinned by one parity test.
- `consistent-auth-gates` — the documented TLS front reaches Phoenix only through the auth sidecar.
