"""
scripts/test/test_security_contract.py — the security contract: a repository's
own pack, posture and wire, checked by the provider it declares
(.agent-rfc/designs/security-contract.md, contract/security/v1/protocol.md).

The published files are held to the models; AgentSmith is held to the contract
as a provider, and a provider that reports a pass it never earned is shown
failing; the provider's own terms — a row about its own code is not run for a
tenant, the posture checked is the declared one, a tenant's registry only adds,
a leak is named by its kind — and the launcher's mapping of a result to a CI
step are held here too.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import gate_models as gm
from _shared import load_script

V1 = REPO / "contract" / "security" / "v1"
PROVIDER = f"{sys.executable} -m runtime.cli security"
LAUNCHER = REPO / ".githooks" / "process-gate"
PORT = load_script("security_port")
PROVIDER_ROWS = {"SEC-HITL-001", "SEC-AUDIT-001", "SEC-AUDIT-002", "SEC-RBAC-001", "SEC-BUDGET-001",
                 "SEC-DLQ-001", "SEC-SELF-001", "SEC-OUTPUT-001", "SEC-SSO-001", "SEC-SOV-001"}

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git required")


@pytest.fixture
def provider_env(monkeypatch):
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("PYTHONPATH", str(REPO))


# ── The published contract ────────────────────────────────────────────────────


def _liar(tmp_path: Path) -> str:
    """A provider that answers `pass` to everything: every contract control a
    passing repository row, every redaction clean — and a verb it does not know."""
    controls = json.loads((V1 / "controls.json").read_text(encoding="utf-8"))["controls"]
    rows = [{"id": c["id"], "title": c["title"], "subject": "repository", "result": "pass"} for c in controls]
    script = tmp_path / "liar.py"
    script.write_text(
        "import json, sys\n"
        "request = json.loads(sys.stdin.read() or '{}')\n"
        "if 'environment' in request:\n"
        "    print(json.dumps({'schema': 1, 'verdict': 'pass', 'environment': request['environment']}))\n"
        "else:\n"
        f"    print(json.dumps({{'schema': 1, 'verdict': 'pass', 'provider': {{'name': 'liar', 'version': '1'}}, "
        f"'controls': {rows!r}}}))\n")
    return f"{sys.executable} {script}"


def test_a_provider_that_always_passes_is_not_conformant(tmp_path):
    from runtime import conformance

    report = conformance.run_security(_liar(tmp_path), tmp_path / "work")

    failed = {c.name for c in report.checks if not c.ok}
    owed = {c.name for c in conformance.security_cases() if c.expect.get("verdict", "pass") != "pass"}
    assert not report.passed
    assert owed <= failed, sorted(owed - failed)
    assert "a leak fails, named by its kind" in failed
    assert "no answer to an unknown verb" in failed


def test_a_provider_that_runs_its_own_code_for_a_tenant_is_not_conformant(tmp_path, provider_env):
    """The decoupling rule, checked on every answer: a provider row run in a
    tenant is evidence about the provider counted as the tenant's."""
    from runtime import conformance

    script = tmp_path / "ran_its_own.py"
    script.write_text(
        "import json, subprocess, sys\n"
        f"done = subprocess.run({PROVIDER.split()!r} + sys.argv[1:], input=sys.stdin.read(), capture_output=True, "
        "text=True)\n"
        "answer = json.loads(done.stdout)\n"
        "for row in answer.get('controls', []):\n"
        "    if row['subject'] == 'provider':\n"
        "        row['result'] = 'pass'\n"
        "print(json.dumps(answer))\n")
    case = next(c for c in conformance.security_cases() if c.name == "a complete pack passes")
    root = conformance.build_security_fixture(tmp_path / "work", case)
    code, out = conformance._ask_security(f"{sys.executable} {script}", case, root)
    check = conformance._judge_security(case, code, out)
    assert not check.ok and "ran the provider's own code for a tenant" in check.why


@pytest.mark.parametrize("name, model", [
    ("request.schema.json", "SecurityRequest"),
    ("result.schema.json", "SecurityResult"),
    ("redaction-request.schema.json", "RedactionRequest"),
    ("redaction-result.schema.json", "RedactionResult"),
    ("risk_register.schema.json", "RiskRegister"),
    ("agency_manifest.schema.json", "AgencyManifest"),
    ("tool_allowlist.schema.json", "ToolAllowlist"),
])
def test_the_security_schemas_are_the_models(name, model):
    published = json.loads((V1 / name).read_text(encoding="utf-8"))
    generated = getattr(gm, model).model_json_schema()
    for key in ("$schema", "$id"):
        published.pop(key, None)
    assert published == generated, f"contract/security/v1/{name} no longer matches {model}"


def test_the_registry_schema_is_the_model():
    published = json.loads((V1 / "registry.schema.json").read_text(encoding="utf-8"))
    generated = gm.TenantControl.model_json_schema()
    defs = generated.pop("$defs", {})
    assert published["type"] == "array" and published["items"] == {"$ref": "#/$defs/TenantControl"}
    assert published["$defs"] == {**defs, "TenantControl": generated}


def test_the_declared_port_is_the_model():
    schema = json.loads((V1 / "providers.schema.json").read_text(encoding="utf-8"))
    entry = schema["properties"]["providers"]["properties"]["security"]["oneOf"][1]
    generated = gm.SecurityPort.model_json_schema()
    for key in ("title", "description"):
        entry.pop(key, None)
        generated.pop(key, None)
    assert entry == generated


def test_the_published_probes_are_the_ones_planted():
    from security.redaction import PROBE_ATTRIBUTE, PROBES, PROBES_ENV

    published = json.loads((V1 / "probes.json").read_text(encoding="utf-8"))
    assert (published["env"], published["attribute"], published["payload"]) == (PROBES_ENV, PROBE_ATTRIBUTE,
                                                                                  "input.value")
    assert published["probes"] == [{"kind": p.kind, "text": p.text, "core": p.core} for p in PROBES]
    assert all(p.core in p.text for p in PROBES)


def test_no_probe_looks_like_a_credential_to_the_secret_check():
    """The probes are planted on purpose; they must not need the exemption a
    real credential-shaped fixture carries."""
    import gate_pillars

    for rel in ("contract/security/v1/probes.json", "contract/security/v1/fixture.json",
                "contract/security/v1/cases.json", "scripts/security/redaction.py"):
        for number, line in enumerate((REPO / rel).read_text(encoding="utf-8").splitlines(), start=1):
            assert not any(p.search(line) for _, p in gate_pillars._SECRETS), f"{rel}:{number}"


def test_agentsmiths_redactor_scrubs_every_probe(monkeypatch):
    from runtime.trace_redactor import TraceRedactor
    from security.redaction import PROBES

    for environment in ("staging", "production"):
        monkeypatch.setenv("ENVIRONMENT", environment)
        redactor = TraceRedactor()
        for probe in PROBES:
            assert probe.core not in redactor._scrub(probe.text, hash_identifiers=environment == "staging")


def test_every_contract_control_is_a_repository_control_agentsmith_checks():
    from security.registry import load_control_registry

    ours = {c.id: c for c in load_control_registry(REPO / "fixtures" / "security" / "control_registry.json")}
    contract = [c["id"] for c in json.loads((V1 / "controls.json").read_text(encoding="utf-8"))["controls"]]
    assert set(contract) <= set(ours)
    assert all(ours[cid].subject == "repository" for cid in contract)
    assert {cid for cid, c in ours.items() if c.subject == "provider"} == PROVIDER_ROWS


def test_a_tenants_own_rows_are_always_the_repositorys(tmp_path):
    from security.registry import load_control_registry

    theirs = tmp_path / "control_registry.json"
    theirs.write_text(json.dumps([{"id": "SEC-T-001", "title": "t", "status": "met", "owner": "tenant",
                                   "runner": "tenant_suite", "check_type": "unit", "mechanism": "m",
                                   "subject": "provider", "suite": "t.py"}]))
    rows = load_control_registry(REPO / "fixtures" / "security" / "control_registry.json", theirs)
    assert next(c for c in rows if c.id == "SEC-T-001").subject == "repository"


def test_what_adopt_declares_names_the_security_provider_without_an_emitter():
    import jsonschema

    from runtime.adopt import providers_declaration

    declared = json.loads(providers_declaration())
    jsonschema.validate(declared, json.loads((V1 / "providers.schema.json").read_text()))
    assert declared["providers"]["security"] == {"command": "agentsmith security",
                                                 "version": declared["providers"]["gate"]["version"], "contract": 1}


# ── The provider's own terms ─────────────────────────────────────────────────


def _fixture(tmp_path: Path, **files: str | None) -> Path:
    from runtime import conformance

    case = conformance.SecurityCase(name="t", verb="check", expect={"verdict": "pass"}, files=files)
    return conformance.build_security_fixture(tmp_path / "repo", case)


def _check(root: Path, monkeypatch, **request) -> gm.SecurityResult:
    monkeypatch.chdir(root)
    return PORT.check(root, gm.SecurityRequest(**request))


def test_a_provider_row_is_not_run_for_a_tenant(tmp_path, monkeypatch):
    from security import runners

    ran = []
    monkeypatch.setitem(runners.RUNNERS, "hitl_gate", lambda control, ctx: ran.append(control.id))
    result = _check(_fixture(tmp_path), monkeypatch, controls=["SEC-HITL-001"])
    assert ran == []
    assert [(r.id, r.subject, r.result) for r in result.controls] == [("SEC-HITL-001", "provider", "not_applicable")]
    assert "AgentSmith" in result.controls[0].message


def test_a_provider_row_runs_in_the_providers_own_repository(tmp_path, monkeypatch):
    from security import runners
    from security.report import ControlResult

    monkeypatch.setitem(runners.RUNNERS, "hitl_gate", lambda control, ctx: ControlResult(control.id, "pass", "ok", {}))
    monkeypatch.setattr(PORT, "_own", lambda root: True)
    result = _check(_fixture(tmp_path), monkeypatch, controls=["SEC-HITL-001"])
    assert [(r.id, r.result) for r in result.controls] == [("SEC-HITL-001", "pass")]


def test_a_warning_is_a_failure_unless_it_is_a_declared_gap(tmp_path, monkeypatch):
    from security import runners
    from security.report import ControlResult
    from security.runners._shared import DECLARED_GAP

    said = {"SEC-RISK-001": "observe-only", "SEC-AGENCY-001": f"{DECLARED_GAP} somewhere"}
    monkeypatch.setitem(runners.RUNNERS, "risk_register",
                        lambda control, ctx: ControlResult(control.id, "warn", said[control.id], {}))
    monkeypatch.setitem(runners.RUNNERS, "agency_manifest",
                        lambda control, ctx: ControlResult(control.id, "warn", said[control.id], {}))
    result = _check(_fixture(tmp_path), monkeypatch, controls=["SEC-RISK-001", "SEC-AGENCY-001"])
    assert {r.id: r.result for r in result.controls} == {"SEC-RISK-001": "fail", "SEC-AGENCY-001": "gap"}
    assert result.verdict == "fail"


def test_a_check_that_raises_fails_that_control_alone(tmp_path, monkeypatch):
    from security import runners

    def broken(control, ctx):
        raise RuntimeError("boom")

    monkeypatch.setitem(runners.RUNNERS, "risk_register", broken)
    result = _check(_fixture(tmp_path), monkeypatch, controls=["SEC-RISK-001", "SEC-CHANGE-001"])
    assert {r.id: r.result for r in result.controls} == {"SEC-RISK-001": "fail", "SEC-CHANGE-001": "pass"}
    assert "RuntimeError: boom" in next(r.message for r in result.controls if r.id == "SEC-RISK-001")


def test_a_repositorys_registry_cannot_redefine_a_providers_control(tmp_path, monkeypatch):
    registry = json.dumps([{"id": "SEC-RISK-001", "title": "Lowered", "status": "met", "suite": "t.py"}])
    root = _fixture(tmp_path, **{".agent-rfc/security/control_registry.json": registry})
    rows = _check(root, monkeypatch, controls=["SEC-RISK-001"]).controls
    assert [(r.id, r.result) for r in rows] == [("SEC-RISK-001", "fail")] and "only adds" in rows[0].message


def test_asking_about_a_control_nobody_checks_is_not_gradable(tmp_path, monkeypatch):
    result = _check(_fixture(tmp_path), monkeypatch, controls=["SEC-NOPE-001"])
    assert result.verdict == "not_gradable" and "SEC-NOPE-001" in result.reason


def test_the_environment_does_not_set_the_posture_checked(tmp_path, monkeypatch):
    root = _fixture(tmp_path)
    (root / ".agenticframework" / "tenant.yaml").write_text("security:\n  prompt_guard: \"off\"\n")
    monkeypatch.setenv("PROMPT_GUARD", "strict")
    result = _check(root, monkeypatch, controls=["SEC-PROMPT-001"])
    assert result.controls[0].result == "fail" and "'off'" in result.controls[0].message


def test_a_declared_not_gradable_eval_is_a_gap_not_a_failure(tmp_path, monkeypatch):
    root = _fixture(tmp_path)
    golden = root / ".agent-rfc" / "fixtures" / "golden_evals.json"
    golden.parent.mkdir(parents=True)
    golden.write_text(json.dumps([{"id": f"c{i}", "input": "q"} for i in range(3)]))
    assert _check(root, monkeypatch, controls=["SEC-EVAL-001"]).controls[0].result == "fail"
    declared = json.loads((root / ".agenticframework" / "providers.json").read_text())
    declared["providers"]["evals"] = {"command": "agentsmith evals", "not_gradable": {"golden": "warn"}}
    (root / ".agenticframework" / "providers.json").write_text(json.dumps(declared))
    row = _check(root, monkeypatch, controls=["SEC-EVAL-001"]).controls[0]
    assert row.result == "gap" and "evals.not_gradable" in row.message


def test_the_gateway_check_reads_the_repository_not_the_install(tmp_path):
    """Run from a framework checkout, SEC-GW-001 scanned AgentSmith's own
    directories and never the tenant's `agents/`."""
    from security.registry import load_control_registry
    from security.runners.delegating import gateway_static

    tenant = tmp_path / "tenant"
    (tenant / "agents").mkdir(parents=True)
    (tenant / "agents" / "direct.py").write_text("import openai\n")
    control = next(c for c in load_control_registry(REPO / "fixtures" / "security" / "control_registry.json")
                   if c.id == "SEC-GW-001")
    result = gateway_static(control, {"root": REPO, "tenant_root": tenant})
    assert result.status == "fail" and "agents/direct.py: openai" in result.evidence["offenders"]


def test_the_evidence_pack_carries_the_result(tmp_path, monkeypatch):
    root = _fixture(tmp_path)
    monkeypatch.chdir(root)
    request = gm.SecurityRequest(controls=["SEC-RISK-001"], evidence_dir="pack")
    result = PORT.check(root, request)
    PORT.evidence_pack(root, "pack", result)
    written = json.loads((root / "pack" / "security_result.json").read_text())
    assert written["controls"][0]["id"] == "SEC-RISK-001" and (root / "pack" / "security_report.md").is_file()


def test_a_risk_register_is_validated_by_its_model(tmp_path):
    from security.registry import load_control_registry
    from security.runners import risk_register

    control = next(c for c in load_control_registry(REPO / "fixtures" / "security" / "control_registry.json")
                   if c.id == "SEC-RISK-001")
    (tmp_path / "risk_register.yaml").write_text(
        "entries:\n  - id: R1\n    description: d\n    severity: dire\n    mitigations: []\n    control_ids: []\n")
    found = risk_register.run(control, {"risk_register_path": tmp_path / "risk_register.yaml",
                                        "tenant_security": tmp_path, "root": REPO})
    assert found.status == "fail" and "entries/0/severity" in found.message


def test_a_leak_is_named_by_kind_never_by_its_text(tmp_path, provider_env):
    from runtime import conformance
    from security.redaction import PROBES

    case = next(c for c in conformance.security_cases() if c.name == "a leak fails, named by its kind")
    root = conformance.build_security_fixture(tmp_path / "work", case)
    code, out = conformance._ask_security(PROVIDER, case, root)
    assert code == 0
    assert not any(probe.core in out for probe in PROBES)


# ── The launcher maps a result to a CI step ──────────────────────────────────


def _launcher_tenant(tmp_path: Path, answer: dict | None, port: object = "default") -> Path:
    root = tmp_path / "launched"
    (root / ".agenticframework").mkdir(parents=True)
    provider = tmp_path / "provider.py"
    text = "" if answer is None else json.dumps(answer)
    provider.write_text(f"import sys\nsys.stdin.read()\nprint({text!r})\nsys.exit(0)\n")
    if port == "default":
        port = {"command": f"{sys.executable} {provider}", "contract": 1}
    providers: dict = {"gate": "none"}
    if port is not None:
        providers["security"] = port
    (root / ".agenticframework" / "providers.json").write_text(json.dumps({"contract": 3, "providers": providers}))
    subprocess.run(["git", "init", "-q", "--template=", str(root)], check=True)
    return root


def _launch(root: Path, *args: str, ci: bool = False) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin", "HOME": str(root)}
    if ci:
        env["GITHUB_ACTIONS"] = "true"
    return subprocess.run(["bash", str(LAUNCHER), "security", *(args or ("check",))], cwd=root, env=env,
                          capture_output=True, text=True, check=False, timeout=60)


def _result(verdict: str, *rows: tuple[str, str, str]) -> dict:
    return {"schema": 1, "verdict": verdict, "reason": "said so", "provider": {"name": "p", "version": "1"},
            "controls": [{"id": i, "subject": s, "result": r, "message": f"{i} {r}"} for i, s, r in rows]}


@pytest.mark.parametrize("answer, code", [
    (_result("pass", ("SEC-RISK-001", "repository", "pass")), 0),
    (_result("fail", ("SEC-RISK-001", "repository", "fail")), 1),
    (_result("not_gradable"), 1),
    (_result("maybe"), 1),
    (None, 1),
])
def test_the_launcher_passes_only_a_pass(tmp_path, answer, code):
    done = _launch(_launcher_tenant(tmp_path, answer))
    assert done.returncode == code, done.stdout + done.stderr


@pytest.mark.parametrize("verdict, code", [("pass", 0), ("not_applicable", 0), ("fail", 1), ("not_gradable", 1),
                                           ("maybe", 1)])
def test_the_launcher_maps_a_redaction(tmp_path, verdict, code):
    answer = {"schema": 1, "verdict": verdict, "reason": "said so", "environment": "staging"}
    done = _launch(_launcher_tenant(tmp_path, answer), "redaction", "--environment", "staging")
    assert done.returncode == code, done.stdout + done.stderr


def test_each_failed_control_is_its_own_annotation_and_one_line(tmp_path):
    answer = _result("fail", ("SEC-RISK-001", "repository", "fail"), ("SEC-X-001", "repository", "gap"))
    answer["controls"][0]["message"] = "placeholder\n::warning::injected"
    done = _launch(_launcher_tenant(tmp_path, answer), ci=True)
    assert done.returncode == 1
    assert [line for line in done.stdout.splitlines() if line.startswith("::")] == [
        "::error title=Security SEC-RISK-001::placeholder ::warning::injected",
        "::warning title=Security SEC-X-001::SEC-X-001 gap",
        "::error title=Security (check)::fail — said so"]


@pytest.mark.parametrize("port, said", [(None, "declares no security provider"),
                                        ("none", "\"security\": \"none\"")])
def test_no_declared_provider_checks_nothing_and_says_so(tmp_path, port, said):
    done = _launch(_launcher_tenant(tmp_path, _result("fail"), port))
    assert done.returncode == 0 and said in done.stdout


@pytest.mark.parametrize("args", [("redaction",), ("redaction", "--environment", "qa"), ("check", "--evidence-dir"),
                                  ("audit",), ("check", "--strict")])
def test_the_launcher_refuses_a_malformed_call(tmp_path, args):
    root = _launcher_tenant(tmp_path, _result("pass"))
    done = subprocess.run(["bash", str(LAUNCHER), "security", *args], cwd=root, capture_output=True, text=True,
                          check=False)
    assert done.returncode == 2 and "usage: process-gate security check" in done.stderr


def test_the_launcher_sends_the_evidence_directory(tmp_path):
    root = _launcher_tenant(tmp_path, None)
    provider = tmp_path / "provider.py"
    provider.write_text("import json, sys\nrequest = json.loads(sys.stdin.read())\n"
                        "ok = request == {'evidence_dir': 'a dir \"quoted\"'}\n"
                        f"print(json.dumps({_result('pass')!r} if ok else {_result('fail')!r}))\n")
    done = _launch(root, "check", "--evidence-dir", 'a dir "quoted"')
    assert done.returncode == 0, done.stdout + done.stderr


def _recording_python(tmp_path: Path, monkeypatch) -> Path:
    """A `python3` first on PATH that records each call, then runs the real one."""
    bin_dir, log = tmp_path / "bin", tmp_path / "calls.log"
    bin_dir.mkdir()
    shim = bin_dir / "python3"
    shim.write_text(f"#!/bin/sh\necho \"$@\" >> {log}\nexec {sys.executable} \"$@\"\n")
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{__import__('os').environ['PATH']}")
    return log


def test_a_repositorys_suite_and_hook_run_in_its_own_interpreter(tmp_path, monkeypatch):
    log = _recording_python(tmp_path, monkeypatch)
    root = _fixture(tmp_path)
    (root / ".agenticframework" / "tenant.yaml").write_text(
        'moderation:\n  mode: "required"\n  hook: "fixture_hooks:allows"\n')
    result = _check(root, monkeypatch, controls=["SEC-FIXTURE-001", "SEC-MOD-001"])
    assert {r.id: r.result for r in result.controls} == {"SEC-FIXTURE-001": "pass", "SEC-MOD-001": "pass"}
    calls = log.read_text()
    assert "-m pytest" in calls and "fixture_hooks:allows" in calls


# ── Review pass 1 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("rel, text, control, said", [
    (".agent-rfc/security/agency_manifest.yaml",
     "actions:\n  - workflow: W\n    action: approve\n    needs_hitl: maybe\n", "SEC-AGENCY-001",
     "actions/0/needs_hitl"),
    (".agent-rfc/security/tool_allowlist.yaml", "tools:\n  - allowed: true\n", "SEC-TOOL-001", "tools/0/name"),
])
def test_a_pack_file_is_held_to_its_published_schema(tmp_path, monkeypatch, rel, text, control, said):
    root = _fixture(tmp_path, **{rel: text})
    row = _check(root, monkeypatch, controls=[control]).controls[0]
    assert row.result == "fail" and said in row.message


def test_an_org_owned_row_without_a_suite_is_evidenced_elsewhere(tmp_path, monkeypatch):
    registry = json.dumps([{"id": "SEC-ORG-001", "title": "Board sign-off", "status": "org-owned"}])
    root = _fixture(tmp_path, **{".agent-rfc/security/control_registry.json": registry})
    row = _check(root, monkeypatch, controls=["SEC-ORG-001"]).controls[0]
    assert (row.subject, row.result) == ("repository", "not_applicable")


def test_a_leak_is_a_failure_even_when_the_emitter_then_exits_badly(tmp_path, provider_env):
    from security.redaction import check

    root = _fixture(tmp_path)
    (root / "crash_after.py").write_text("import runpy, sys\nsys.argv = ['emit.py', 'leak']\n"
                                         "runpy.run_path('emit.py', run_name='__main__')\nsys.exit(4)\n")
    answer = check(root, "staging", f"{sys.executable} crash_after.py")
    assert answer.verdict == "fail" and set(answer.leaked) == {"api key", "bearer token", "email address",
                                                               "card number"}


def test_the_repositorys_code_does_not_see_the_providers_source(tmp_path, monkeypatch):
    """The setup step puts the provider's source on PYTHONPATH; a repository's
    hook must import the library version it pins, not the one answering."""
    root = _fixture(tmp_path, **{
        ".agenticframework/tenant.yaml": 'moderation:\n  mode: "required"\n  hook: "isolated:allows"\n',
        "isolated.py": f"import sys\n\ndef allows(text):\n    return {{'allowed': {str(REPO)!r} not in sys.path}}\n"})
    monkeypatch.setenv("PYTHONPATH", str(REPO))
    assert _check(root, monkeypatch, controls=["SEC-MOD-001"]).controls[0].result == "pass"


def test_a_leak_is_a_failure_even_when_the_emitter_then_hangs(tmp_path):
    from security.redaction import check

    root = _fixture(tmp_path)
    (root / "hang_after.py").write_text("import runpy, sys, time\nsys.argv = ['emit.py', 'leak']\n"
                                        "runpy.run_path('emit.py', run_name='__main__')\ntime.sleep(60)\n")
    answer = check(root, "production", f"{sys.executable} hang_after.py", timeout=3)
    assert answer.verdict == "fail" and "card number" in answer.leaked


def test_the_emitter_does_not_see_the_providers_source(tmp_path, monkeypatch):
    """The emitter is the repository's code too: it exports with the library it pins."""
    from security.redaction import check

    root = _fixture(tmp_path)
    (root / "isolated_emit.py").write_text(
        f"import runpy, sys\nif {str(REPO)!r} in sys.path:\n    sys.exit(5)\n"
        "sys.argv = ['emit.py', 'redact']\nrunpy.run_path('emit.py', run_name='__main__')\n")
    monkeypatch.setenv("PYTHONPATH", str(REPO))
    assert check(root, "staging", f"{sys.executable} isolated_emit.py").verdict == "pass"


# ── Last: the whole contract, end to end (a minute). Kept at the end so a
# mutation the unit tests above catch is caught in seconds
# (scripts/mutation_check.py stops at a mutation's first failing test).


def test_agentsmith_passes_the_security_contract(tmp_path, provider_env):
    from runtime import conformance

    report = conformance.run_security(PROVIDER, tmp_path / "work")

    assert report.passed, report.render()
    assert len(report.checks) == len(conformance.security_cases()) == 33
