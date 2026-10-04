"""
scripts/test/test_telemetry_contract.py — the telemetry contract: what a governed
application's spans and metrics carry (.agent-rfc/designs/telemetry-contract.md,
contract/telemetry/v1/protocol.md).

The catalogue is held to its model; the judge to the contract's own cases; the
runtime library to the judge — in process and over OTLP through `--emitter`;
emitters that break the contract are seen to fail; and every name the
framework's emitters write is in the catalogue, so a new one cannot ship
uncatalogued.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from runtime import conformance as rc
from runtime import telemetry_contract as tc

V1 = REPO / "contract" / "telemetry" / "v1"
EMITTER = REPO / "scripts" / "test" / "telemetry_emitter.py"


# ── The published files ───────────────────────────────────────────────────────


def test_the_catalogue_schema_is_the_model():
    published = json.loads((V1 / "catalogue.schema.json").read_text(encoding="utf-8"))
    generated = tc.Catalogue.model_json_schema()
    for key in ("description", "$schema", "$id"):
        published.pop(key, None)
        generated.pop(key, None)
    assert published == generated


def test_the_catalogue_is_valid_and_names_its_contract():
    catalogue = tc.load_catalogue()
    assert catalogue.contract == tc.TELEMETRY_CONTRACT
    entry = catalogue.lookup("resource", tc.CONTRACT_ATTRIBUTE)
    assert entry is not None and entry.requirement == "required" and entry.type == "int"


@pytest.mark.parametrize("case", rc.telemetry_cases(), ids=lambda c: c.name)
def test_the_judge_decides_every_case_as_the_contract_says(case):
    ok, why = rc.judge_case(case)
    assert ok, why


def test_the_cases_cover_every_check():
    """A check no case can fail is a check nobody knows still works."""
    names = {c.name for c in tc.judge(json.loads((V1 / "fixture.json").read_text())["exports"]).checks}
    failed_by_a_case = {c.expect["failed"] for c in rc.telemetry_cases() if "failed" in c.expect}
    assert names == failed_by_a_case


# ── The runtime library, judged ───────────────────────────────────────────────


def test_the_runtime_library_passes_over_otlp(tmp_path, monkeypatch):
    """The real exporter, the real protocol, through the loopback receiver."""
    monkeypatch.setenv("PYTHONPATH", str(REPO))
    report = rc.run_telemetry_emitter(f"{sys.executable} {EMITTER}")

    assert report.passed, report.render()
    assert any("inside a run" in note and "0 span" not in note for note in report.notes), report.render()


def test_the_runtime_library_states_the_contract_on_its_resource():
    from runtime.tracing import resource_attributes

    attrs = resource_attributes("t")
    assert attrs[tc.CONTRACT_ATTRIBUTE] == tc.TELEMETRY_CONTRACT
    catalogue = tc.load_catalogue()
    for name in attrs:
        assert catalogue.lookup("resource", name), f"{name} is on the Resource and not in the catalogue"


# ── Emitters that break it are seen to ────────────────────────────────────────


PLAIN = '''
import os
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
resource = {{"service.name": "stub", "project.name": "stub", "environment": "staging"}}
if {contract}:
    resource["governance.telemetry.contract"] = 1
provider = TracerProvider(resource=Resource.create(resource))
provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
with trace.get_tracer("stub").start_as_current_span("agent.step") as span:
    span.set_attribute("run.id", "r-1")
    span.set_attribute("agent.role", "stub")
    if {tenant}:
        span.set_attribute("tenant.id", "t-1")
provider.shutdown()
'''


def _plain(tmp_path: Path, *, contract: bool, tenant: bool) -> str:
    script = tmp_path / "plain_emitter.py"
    script.write_text(PLAIN.format(contract=contract, tenant=tenant), encoding="utf-8")
    return f"{sys.executable} {script}"


def test_a_plain_opentelemetry_emitter_that_keeps_the_contract_passes(tmp_path):
    """The point of the contract: no AgentSmith code, and conformant."""
    report = rc.run_telemetry_emitter(_plain(tmp_path, contract=True, tenant=True))
    assert report.passed, report.render()


def test_an_emitter_that_names_no_contract_fails(tmp_path):
    report = rc.run_telemetry_emitter(_plain(tmp_path, contract=False, tenant=True))
    failed = {c.name for c in report.checks if not c.ok}
    assert failed == {"the Resource names the contract it speaks"}, report.render()


def test_an_emitter_whose_run_spans_lack_a_tenant_fails(tmp_path):
    report = rc.run_telemetry_emitter(_plain(tmp_path, contract=True, tenant=False))
    failed = {c.name for c in report.checks if not c.ok}
    assert failed == {"every span inside a run carries the run's identity"}, report.render()


def test_an_emitter_that_exports_nothing_fails():
    report = rc.run_telemetry_emitter(f"{sys.executable} -c pass")
    assert not report.passed
    assert "something was exported" in {c.name for c in report.checks if not c.ok}


def test_an_emitter_that_fails_to_run_is_said(tmp_path):
    report = rc.run_telemetry_emitter(f"{sys.executable} -c \"raise SystemExit(4)\"")
    assert "the emitter ran" in {c.name for c in report.checks if not c.ok}


def test_an_export_file_is_judged_one_object_or_one_per_line(tmp_path):
    exports = json.loads((V1 / "fixture.json").read_text())["exports"]
    whole, lines = tmp_path / "whole.json", tmp_path / "lines.jsonl"
    whole.write_text(json.dumps(exports[0]))
    lines.write_text("\n".join(json.dumps(e) for e in exports) + "\n")
    assert rc.run_telemetry_export(lines).passed
    assert any("0 metric" in n for n in rc.run_telemetry_export(whole).notes)


# ── The receiver reads bodies it did not write ────────────────────────────────


def _post(url: str, body: bytes, content_type: str = "application/x-protobuf") -> int:
    request = urllib.request.Request(url, data=body, headers={"Content-Type": content_type}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as answer:
            return answer.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_the_receiver_survives_bodies_that_are_not_otlp():
    with tc.LoopbackCollector() as collector:
        assert collector.endpoint.startswith("http://127.0.0.1:")
        assert _post(collector.endpoint + "/v1/traces", b"\xff\x00 not protobuf") == 200
        assert _post(collector.endpoint + "/v1/traces", b"{not json", "application/json") == 200
        assert _post(collector.endpoint + "/elsewhere", b"x") == 404
        problems = list(collector.problems)
    assert len(problems) == 2 and all(p.startswith("traces:") for p in problems), problems


def test_the_receiver_refuses_an_oversize_body(monkeypatch):
    monkeypatch.setattr(tc, "MAX_BODY_BYTES", 10)
    with tc.LoopbackCollector() as collector:
        assert _post(collector.endpoint + "/v1/traces", b"x" * 11) == 413
        assert not collector.exports


# ── Every name the framework emits is catalogued ──────────────────────────────


EMITTERS = sorted([*(REPO / "runtime").glob("*.py"),
                   *(REPO / "scripts" / name for name in ("gate_tracing.py", "process_gate.py", "rules_port.py",
                                                          "local_agent_stack.py", "multi_agent_system.py"))])
# Sites whose attribute names are not literals — each reviewed: the identity
# processor writes `current_identity()` (tenancy.py, inventoried below), the
# gateway writes `prompt_attributes()` (prompt_identity.py, likewise), and the
# portal's helpers are TypeScript. A new dynamic site fails here until reviewed.
REVIEWED_DYNAMIC = {("runtime/tracing.py", "key"), ("runtime/llm_gateway.py", "key")}


def _constants(tree: ast.Module) -> dict[str, str]:
    return {t.id: node.value.value for node in tree.body if isinstance(node, ast.Assign)
            for t in node.targets if isinstance(t, ast.Name)
            and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)}


def _name(arg: ast.expr, constants: dict[str, str]) -> tuple[str, bool] | None:
    """(name, is a prefix) for a literal, an f-string's literal head, or a module constant."""
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value, False
    if isinstance(arg, ast.Name) and arg.id in constants:
        return constants[arg.id], False
    if isinstance(arg, ast.JoinedStr):
        head = ""
        for part in arg.values:
            if isinstance(part, ast.Constant):
                head += str(part.value)
            elif isinstance(part.value, ast.Name) and part.value.id in constants and not head:
                head += constants[part.value.id]
            else:
                return head, True
        return head, False
    return None


def _inventory(paths: list[Path] | None = None) -> tuple[set[tuple[str, str, bool]], set[tuple[str, str]]]:
    found, dynamic = set(), set()
    for path in paths or EMITTERS:
        rel = path.relative_to(REPO).as_posix() if path.is_relative_to(REPO) else path.name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = _constants(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if func == "set_attribute" and node.args:
                named = _name(node.args[0], constants)
                if named is None or (named[1] and not named[0]):
                    dynamic.add((rel, ast.unparse(node.args[0])))
                elif named[0] != "docs":  # verify_system's redaction probe is not in this list
                    found.add(("span", named[0], named[1]))
            elif func == "agent_span":
                found.update(("span", f"agent.{kw.arg}", False) for kw in node.keywords
                             if kw.arg and kw.arg not in ("tenant_id",))
            elif func == "_instrument" and len(node.args) >= 2:
                named = _name(node.args[1], constants)
                if named:
                    found.add(("metric", named[0], False))
    return found, dynamic


def _dict_keys(path: Path, function: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == function:
            for inner in ast.walk(node):
                if isinstance(inner, ast.Dict):
                    keys |= {k.value for k in inner.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
                if isinstance(inner, ast.Subscript) and isinstance(inner.ctx, ast.Store) \
                        and isinstance(inner.slice, ast.Constant):
                    keys.add(inner.slice.value)
    return keys


def test_every_name_the_framework_emits_is_catalogued():
    catalogue = tc.load_catalogue()
    found, _dynamic = _inventory()
    found |= {("span", k, False) for k in _dict_keys(REPO / "runtime" / "tenancy.py", "current_identity")}
    found |= {("span", k, False) for k in _dict_keys(REPO / "runtime" / "prompt_identity.py", "prompt_attributes")}
    found |= {("metric_attribute", k, False) for k in _dict_keys(REPO / "runtime" / "metrics.py", "record_llm_call")
              | _dict_keys(REPO / "runtime" / "metrics.py", "record_cache")
              | _dict_keys(REPO / "runtime" / "metrics.py", "record_retry")
              | _dict_keys(REPO / "runtime" / "metrics.py", "record_retrieval")}
    missing = []
    for where, name, prefix in sorted(found):
        if prefix:
            if not any(e.where == where and (e.name.startswith(name) or name.startswith(e.name))
                       for e in catalogue.entries):
                missing.append(f"{where} {name}…")
        elif catalogue.lookup(where, name) is None:
            missing.append(f"{where} {name}")
    assert not missing, f"emitted and not in contract/telemetry/v1/attributes.json: {missing}"
    assert len(found) > 40, "the inventory found too little to mean anything — has the AST walk stopped matching?"


def test_a_new_dynamic_attribute_site_is_reviewed():
    _found, dynamic = _inventory()
    assert dynamic == REVIEWED_DYNAMIC, f"set_attribute with a computed name: {sorted(dynamic - REVIEWED_DYNAMIC)}"


def test_the_inventory_can_fail(tmp_path):
    """An attribute nobody catalogued is found, and the catalogue lacks it —
    so the guard above is not vacuous."""
    rogue = tmp_path / "rogue.py"
    rogue.write_text('def f(span):\n    span.set_attribute("acme.uncatalogued", 1)\n')
    found, _ = _inventory([rogue])
    assert found == {("span", "acme.uncatalogued", False)}
    assert tc.load_catalogue().lookup("span", "acme.uncatalogued") is None


# ── The Wire Contract table is pinned to the catalogue ────────────────────────


def _wire_rows() -> list[tuple[str, list[str], str]]:
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    table = text[text.index("| Emitted since | Field | Wire |"):]
    table = table[: table.index("\n\n")]
    rows = []
    for line in table.splitlines()[2:]:
        version, field, wire = (cell.strip() for cell in line.strip("|").split("|"))
        rows.append((version, re.findall(r"`([^`]+)`", field), wire))
    return rows


def test_the_wire_contract_table_names_catalogued_attributes_with_their_release():
    catalogue = tc.load_catalogue()
    where = {"span": "span", "OTel Resource": "resource", "OTel metrics": "metric"}
    by_name: dict[str, set[str]] = {}
    checked = 0
    for version, names, wire in _wire_rows():
        if wire not in where:
            continue  # the record and run-status wires are other contracts
        for name in names:
            if name.endswith(".*"):
                members = [e for e in catalogue.of(where[wire]) if e.name.startswith(name[:-1])]
                assert members, f"the table's {name} matches nothing catalogued"
                for entry in members:
                    by_name.setdefault(f"{entry.where} {entry.name}", set()).add(version)
                continue
            full = name if "." in name and not name.startswith(("output_", "total_")) else None
            if full is None or full.startswith("contract/"):
                continue
            entry = catalogue.lookup(where[wire], full)
            assert entry is not None and not entry.family, f"the table's {full} ({wire}) is not catalogued"
            by_name.setdefault(f"{entry.where} {entry.name}", set()).add(version)
            checked += 1
    for key, versions in by_name.items():
        where_, name = key.split(" ", 1)
        entry = catalogue.lookup(where_, name)
        assert entry.since in versions, f"{name}: the table says {sorted(versions)}, the catalogue {entry.since}"
    assert checked >= 10


def test_the_catalogue_carries_the_runs_identity_as_the_table_says():
    catalogue = tc.load_catalogue()
    for name in ("tenant.id", "agent.role", "run.id"):
        assert catalogue.lookup("span", name).requirement == "required_in_run"


def test_the_cli_answers_an_export(tmp_path):
    export = tmp_path / "export.json"
    export.write_text(json.dumps(json.loads((V1 / "fixture.json").read_text())["exports"][0]))
    done = subprocess.run([sys.executable, "-m", "runtime.cli", "conformance", "--port", "telemetry", "--export",
                           str(export)], cwd=REPO, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "telemetry contract v1" in done.stdout


# ── Found while building: a shim must never answer with a tenant's vendored CLI ──


def _decoy_tenant(tmp_path: Path) -> Path:
    """A vendored tenant's working directory: its own `runtime/`, older than the
    provider's (.agent-rfc/designs/telemetry-contract.md)."""
    tenant = tmp_path / "vendored-tenant"
    (tenant / "runtime").mkdir(parents=True)
    (tenant / "runtime" / "__init__.py").write_text("")
    (tenant / "runtime" / "cli.py").write_text("print('DECOY: the tenant\\'s vendored cli')\n")
    return tenant


def test_the_test_shim_answers_with_the_provider_inside_a_vendored_tenant(tmp_path):
    import provider_shim

    shim = provider_shim.install() / "agentsmith"
    done = subprocess.run([str(shim), "version"], cwd=_decoy_tenant(tmp_path), capture_output=True, text=True,
                          check=False)
    assert "DECOY" not in done.stdout + done.stderr
    assert done.returncode == 0, done.stderr


def test_the_ci_setup_shim_answers_with_the_provider_inside_a_vendored_tenant(tmp_path):
    """Builds the shim exactly as `.github/actions/setup-agentsmith` does — its
    own shell lines, run here — and calls it from a vendored tenant."""
    import os

    import yaml

    action = yaml.safe_load((REPO / ".github" / "actions" / "setup-agentsmith" / "action.yml").read_text())
    script = next(step["run"] for step in action["runs"]["steps"] if "agentsmith" in step.get("run", ""))
    start = script.index('bin="${RUNNER_TEMP}')
    end = script.index('chmod +x "$bin/agentsmith"')
    lines = script[start:end] + 'chmod +x "$bin/agentsmith"\n'
    fake = tmp_path / "fakebin"
    fake.mkdir()
    (fake / "python").symlink_to(sys.executable)
    env = {**os.environ, "RUNNER_TEMP": str(tmp_path), "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}"}
    subprocess.run(["bash", "-c", f'set -euo pipefail\nroot="{REPO}"\n{lines}'], env=env, check=True)

    shim = tmp_path / "agentsmith-provider" / "bin" / "agentsmith"
    done = subprocess.run([str(shim), "version"], cwd=_decoy_tenant(tmp_path), capture_output=True, text=True,
                          check=False, env=env)
    assert "DECOY" not in done.stdout + done.stderr
    assert done.returncode == 0, done.stderr


def test_no_shipped_shim_runs_the_cli_with_the_working_directory_first():
    """Every place AgentSmith ships `python -m runtime.cli` to run inside a
    tenant: the CI setup shim, the weekly sync workflow. `-P` on each — a new
    one without it is the vendored-CLI defect again (grep-for-siblings)."""
    shipped = [REPO / ".github" / "actions" / "setup-agentsmith" / "action.yml",
               *(REPO / "workflow-templates").glob("*.yml")]
    unsafe = [f"{path.relative_to(REPO)}: {line.strip()}" for path in shipped
              for line in path.read_text(encoding="utf-8").splitlines()
              if re.search(r"(?<!-P )-m runtime\.cli", line)]
    assert not unsafe, unsafe
    assert any("-P -m runtime.cli" in p.read_text() for p in shipped)
