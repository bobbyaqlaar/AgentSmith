"""
scripts/test/test_evals_contract.py — the evals contract: a tenant's datasets,
judged by the provider it declares (.agent-rfc/designs/evals-contract.md,
contract/evals/v1/protocol.md).

The published files are held to the models; AgentSmith is held to the contract
as a provider against the stub judge, and a provider that reports a pass it never
earned is shown failing; the provider's own terms — the tenant's cases only, an
output on every judged case, bars from the request or the declaration and never
the environment, the four verdicts apart — and the launcher's mapping of a
scorecard to a CI step are held here too.
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

V1 = REPO / "contract" / "evals" / "v1"
PROVIDER = f"{sys.executable} -m runtime.cli evals"
LAUNCHER = REPO / ".githooks" / "process-gate"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git required")


@pytest.fixture
def provider_env(monkeypatch):
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("PYTHONPATH", str(REPO))


# Loaded once, through the one shared loader: the fake-scoring tests below
# replace `load_script` for what the provider loads, not for the provider itself.
EVALS_PORT = load_script("evals_port")


def _port():
    return EVALS_PORT


# ── The published contract ────────────────────────────────────────────────────


def test_agentsmith_passes_the_evals_contract(tmp_path, provider_env):
    from runtime import conformance

    report = conformance.run_evals(PROVIDER, tmp_path / "work")

    assert report.passed, report.render()
    assert len(report.checks) == len(conformance.evals_cases()) == 17


def _liar(tmp_path: Path) -> str:
    """A provider that answers `pass` to everything — including a verb the
    contract does not name — whatever the dataset and whether or not a judge
    answered."""
    script = tmp_path / "liar.py"
    script.write_text(
        "import json, sys\n"
        "request = json.loads(sys.stdin.read() or '{}')\n"
        "print(json.dumps({'schema': 1, 'suite': request.get('suite', 'golden'), 'verdict': 'pass', "
        "'reason': '', 'threshold': 0.8, 'fail_above': None, 'cases_total': 3, 'cases_graded': 3}))\n")
    return f"{sys.executable} {script}"


def test_a_provider_that_always_passes_is_not_conformant(tmp_path):
    from runtime import conformance

    report = conformance.run_evals(_liar(tmp_path), tmp_path / "work")

    failed = {c.name for c in report.checks if not c.ok}
    owed = {c.name for c in conformance.evals_cases()
            if c.expect.get("verdict") != "pass" or "threshold" in c.expect or "fail_above" in c.expect}
    assert not report.passed
    assert owed <= failed, sorted(owed - failed)
    assert "a judge that does not answer gives no verdict" in failed
    assert "an unknown verb gets no answer" in failed


def test_the_stub_judge_scores_from_the_markers_and_refuses_a_call_without_its_key():
    import urllib.error
    import urllib.request

    from runtime import conformance

    def ask(judge, key):
        body = json.dumps({"model": "stub-judge", "messages": [
            {"role": "user", "content": "INPUT: q\nACTUAL OUTPUT: a SCORE=0.65 HALLUCINATION=0.2"}]}).encode()
        request = urllib.request.Request(f"{judge.url}/chat/completions", data=body, method="POST",
                                         headers={"Authorization": f"Bearer {key}",
                                                  "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as answer:
            return json.loads(json.loads(answer.read())["choices"][0]["message"]["content"])

    with conformance.StubJudge() as judge:
        assert ask(judge, conformance.STUB_JUDGE_KEY) == {
            "correctness": 1, "tool_accuracy": 1, "score": 0.65, "quality_notes": "stub judge", "hallucination": 0.2}
        with pytest.raises(urllib.error.HTTPError, match="401"):
            ask(judge, "")


def test_a_scorecard_with_a_failing_exit_code_is_not_an_answer(tmp_path):
    from runtime import conformance

    script = tmp_path / "exits_one.py"
    script.write_text("import json, sys\nrequest = json.loads(sys.stdin.read())\n"
                      "print(json.dumps({'schema': 1, 'suite': request['suite'], 'verdict': 'pass', 'reason': '', "
                      "'cases_total': 3, 'cases_graded': 3}))\nsys.exit(1)\n")

    report = conformance.run_evals(f"{sys.executable} {script}", tmp_path / "work")

    passing = [c for c in report.checks if c.name == "a suite above its bar passes"]
    assert passing and not passing[0].ok and "exited 1" in passing[0].why


@pytest.mark.parametrize("name, model", [
    ("request.schema.json", "EvalsRequest"),
    ("scorecard.schema.json", "Scorecard"),
])
def test_the_evals_schemas_are_the_models(name, model):
    published = json.loads((V1 / name).read_text(encoding="utf-8"))
    generated = getattr(gm, model).model_json_schema()
    for key in ("description", "$schema", "$id"):
        published.pop(key, None)
        generated.pop(key, None)
    assert published == generated, f"contract/evals/v1/{name} no longer matches {model}"


@pytest.mark.parametrize("suite", gm.EVAL_SUITES)
def test_each_dataset_schema_is_its_model(suite):
    published = json.loads((V1 / f"dataset.{suite}.schema.json").read_text(encoding="utf-8"))
    model = gm.EVAL_CASES[suite]
    generated = model.model_json_schema()
    generated.pop("description", None)
    defs = generated.pop("$defs", {})
    assert published["type"] == "array" and published["items"] == {"$ref": f"#/$defs/{model.__name__}"}
    published["$defs"][model.__name__].pop("description", None)
    assert published["$defs"] == {**defs, model.__name__: generated}


def test_the_rules_contract_describes_the_extends_that_carries_the_bars():
    """`extends.evals` lives in the one `extends` the rules contract publishes."""
    published = json.loads((REPO / "contract/rules/v1/extends.schema.json").read_text(encoding="utf-8"))
    assert "evals" in published["properties"]
    assert "EvalsThresholds" in published["$defs"]


def test_the_declared_port_is_the_model():
    schema = json.loads((V1 / "providers.schema.json").read_text(encoding="utf-8"))
    entry = schema["properties"]["providers"]["properties"]["evals"]["oneOf"][1]
    generated = gm.EvalsPort.model_json_schema()
    for key in ("title", "description"):
        entry.pop(key, None)
        generated.pop(key, None)
    assert entry == generated


def test_what_adopt_declares_names_the_evals_provider_under_both_contracts():
    import jsonschema

    from runtime.adopt import providers_declaration

    declared = json.loads(providers_declaration())
    jsonschema.validate(declared, json.loads((V1 / "providers.schema.json").read_text()))
    jsonschema.validate(declared, json.loads((REPO / "contract/gate/v3/providers.schema.json").read_text()))
    assert declared["providers"]["evals"] == {"command": "agentsmith evals",
                                              "version": declared["providers"]["rules"]["version"], "contract": 1}


def test_every_fixture_dataset_matches_its_schema():
    """The contract's own data is held to the contract it tests — and the one
    dataset meant to break it breaks it on the field it names."""
    fixture = json.loads((V1 / "fixture.json").read_text(encoding="utf-8"))
    for name, dataset in fixture["datasets"].items():
        model = gm.EVAL_CASES[dataset["suite"]]
        if name.endswith("_no_output"):
            bare = [c for c in dataset["cases"] if "actual_output" not in c]
            assert len(bare) == 1 and len(dataset["cases"]) >= 3, name
            continue
        for case in dataset["cases"]:
            model.model_validate(case)
        assert name.startswith(dataset["suite"]), f"{name} holds a {dataset['suite']} dataset"
    assert set(fixture["paths"]) == set(gm.EVAL_SUITES)


# ── The provider's terms ──────────────────────────────────────────────────────


def _tenant(tmp_path: Path, extends: dict | None = None) -> Path:
    root = tmp_path / "tenant"
    (root / ".agenticframework").mkdir(parents=True)
    (root / ".agenticframework" / "process-gates.json").write_text(json.dumps({"extends": extends or {}}))
    return root


@pytest.mark.parametrize("suite, request_bars, declared, registry, want", [
    ("golden", {}, {}, None, (0.80, None)),
    ("golden", {}, {"golden": {"fail_below": 0.7}}, None, (0.7, None)),
    ("golden", {}, {}, 0.95, (0.95, None)),
    ("golden", {}, {"golden": {"fail_below": 0.7}}, 0.95, (0.7, None)),
    ("golden", {"fail_below": 0.9}, {"golden": {"fail_below": 0.7}}, 0.95, (0.9, None)),
    ("hallucination", {}, {"hallucination": {"fail_above": 0.2}}, None, (0.80, 0.2)),
    ("adversarial", {"fail_below": 0.5}, {}, None, (None, 0.10)),
    ("rag_poison", {"fail_above": 0.0}, {"rag_poison": {"fail_above": 0.3}}, None, (None, 0.0)),
])
def test_bars_come_from_the_request_then_the_declaration_then_the_default(tmp_path, suite, request_bars, declared,
                                                                        registry, want):
    root = _tenant(tmp_path, {"evals": declared})
    request = gm.EvalsRequest(suite=suite, **request_bars)
    assert _port().thresholds(root, request, registry) == want


def test_an_unreadable_declaration_falls_to_the_default_rather_than_crashing(tmp_path):
    root = _tenant(tmp_path)
    (root / ".agenticframework" / "process-gates.json").write_text("{not json")
    assert _port().thresholds(root, gm.EvalsRequest(suite="golden"), None) == (0.80, None)


def test_a_judged_case_without_its_output_names_the_case(tmp_path):
    path = tmp_path / "golden.json"
    path.write_text(json.dumps([{"id": "kept", "input": "q", "actual_output": "a"}, {"id": "bare", "input": "q"}]))

    cases, why, count = _port().dataset(path, "golden")

    assert cases is None and count == 2
    assert "bare (actual_output)" in why and "kept" not in why


def test_a_guard_case_needs_no_output_and_a_tenant_key_is_kept(tmp_path):
    path = tmp_path / "adversarial.json"
    path.write_text(json.dumps([{"id": "a", "input": "hi", "expect": "safe", "owner": "team-x"}]))

    cases, why, _count = _port().dataset(path, "adversarial")

    assert why == "" and cases == [{"id": "a", "input": "hi", "expect": "safe", "owner": "team-x"}]


def _run(root: Path, request: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / "scripts" / "evals_port.py"), *(args or ("run",))],
                          input=json.dumps({"cwd": str(root), **request}), capture_output=True, text=True,
                          check=False, timeout=120)


def test_an_ungradable_suite_answers_and_exits_zero_and_removes_a_stale_result(tmp_path):
    root = _tenant(tmp_path)
    stale = root / ".agent-rfc" / "fixtures" / "eval_results.json"
    stale.parent.mkdir(parents=True)
    stale.write_text(json.dumps({"verdict": "pass"}))

    done = _run(root, {"suite": "golden"})

    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["verdict"] == "not_gradable"
    assert not stale.exists()


@pytest.mark.parametrize("args, request_body", [(("judge",), {"suite": "golden"}), (("run",), {"suite": "nope"}),
                                                (("run", "--write"), {"suite": "golden"})])
def test_a_request_outside_the_contract_gets_no_answer(tmp_path, args, request_body):
    done = _run(_tenant(tmp_path), request_body, *args)
    assert done.returncode == 2 and done.stdout == ""


def _fake_scoring(monkeypatch, tmp_path, *, code: int, written: dict | None):
    """`judge()` over a stand-in for run-evals.py: its scoring returns `code`
    and writes `written` as its result file (or nothing)."""
    import types

    import _shared

    root = _tenant(tmp_path)
    data = root / "golden.json"
    data.write_text(json.dumps([{"id": f"g{i}", "input": "q", "actual_output": "a"} for i in range(3)]))
    results = root / "results.json"

    def run_scorecard(**_kw):
        if written is not None:
            results.write_text(json.dumps(written))
        return code

    fake = types.SimpleNamespace(
        _registry_fail_below=lambda _suite: None, _evals_path=lambda _suite: data,
        _results_path=lambda _suite: results, _missing_judge_credential=lambda: None,
        _load_cases=lambda _suite: [], run_scorecard=run_scorecard,
        _resolve_parity_fail_below=lambda: 1.0, _resolve_score_spread_fail_above=lambda: 0.25)
    monkeypatch.setattr(_shared, "load_script", lambda _name: fake)
    monkeypatch.chdir(tmp_path)
    return root


@pytest.mark.parametrize("written, below, above, says", [
    ({"suite": "golden", "avg_score": 0.5}, 0.8, None, ["average score 0.500 is below 0.80"]),
    ({"suite": "golden", "avg_score": 0.9}, 0.8, None, []),
    ({"suite": "fairness", "avg_score": 0.9, "pair_parity": {"p1": 0.0, "p2": 1.0}}, 0.8, None,
     ["worst pair parity 0.000 is below 1.00"]),
    ({"suite": "fairness", "avg_score": 0.9, "worst_same_text_pair_spread": 0.4}, 0.8, None,
     ["a pair scored on identical output differs by 0.400, over 0.25"]),
    ({"suite": "hallucination", "avg_score": 0.9, "hallucination_flag_rate": 0.3, "hallucination_miss_rate": 1.0},
     0.8, 0.05, ["hallucination flag rate 0.300 is over 0.05", "a planted hallucination was not flagged"]),
    ({"suite": "adversarial", "avg_score": 0.0, "adversarial_miss_rate": 0.5}, None, 0.1,
     ["miss rate 0.500 is over 0.10"]),
    ({"suite": "golden", "avg_score": True}, 0.8, None, []),
])
def test_a_failed_suite_names_each_bar_it_missed(written, below, above, says):
    assert _port().missed(written, below, above, 1.0, 0.25) == says


@pytest.mark.parametrize("code, written, verdict, reason", [
    (1, {"verdict": "no_verdict", "cases_total": 3, "cases_graded": 0}, "fail", "no longer served"),
    (1, None, "fail", "more than one judge"),
    (0, {"verdict": "no_verdict", "cases_total": 3, "cases_graded": 2}, "no_verdict", "graded 2 of 3"),
    (0, {"verdict": "no_verdict", "cases_total": 3, "cases_graded": 0}, "no_verdict", "did not answer"),
    (2, None, "not_gradable", "too few"),
    (0, {"verdict": "pass", "cases_total": 3, "cases_graded": 3}, "pass", "cleared"),
    (1, {"verdict": "fail", "cases_total": 3, "cases_graded": 3}, "fail", "missed a bar"),
    (1, {"verdict": "fail", "suite": "golden", "avg_score": 0.1, "cases_total": 3, "cases_graded": 3}, "fail",
     "average score 0.100 is below 0.80"),
])
def test_each_outcome_of_the_scoring_is_one_verdict(monkeypatch, tmp_path, code, written, verdict, reason):
    root = _fake_scoring(monkeypatch, tmp_path, code=code, written=written)

    card = _port().judge(root, gm.EvalsRequest(suite="golden"))

    assert (card.verdict, reason in card.reason) == (verdict, True), card.reason


def test_the_environment_sets_no_bar_on_the_scoring(monkeypatch, tmp_path):
    seen = {}
    root = _fake_scoring(monkeypatch, tmp_path, code=0, written={"verdict": "pass"})
    import _shared

    fake = _shared.load_script("run-evals")
    original = fake.run_scorecard

    def spy(**kw):
        import os

        seen.update(kw, env={k: os.environ.get(k) for k in _port().THRESHOLD_ENV})
        return original(**kw)

    fake.run_scorecard = spy
    for name in _port().THRESHOLD_ENV:
        monkeypatch.setenv(name, "0.99")

    _port().judge(root, gm.EvalsRequest(suite="golden"))

    assert seen["fail_below"] == 0.80
    assert set(seen["env"].values()) == {None}


# ── The caller: the launcher maps a scorecard to a step ───────────────────────


def _launcher_tenant(tmp_path: Path, verdict: str | None, port: object = "default", suite: str = "golden") -> Path:
    root = tmp_path / "launched"
    (root / ".agenticframework").mkdir(parents=True)
    provider = tmp_path / "provider.py"
    answer = "" if verdict is None else json.dumps({"schema": 1, "suite": suite, "verdict": verdict,
                                                    "reason": "said so"})
    provider.write_text(f"import sys\nsys.stdin.read()\nprint({answer!r})\nsys.exit(0)\n")
    if port == "default":
        port = {"command": f"{sys.executable} {provider}", "contract": 1}
    elif isinstance(port, dict):
        port = {"command": f"{sys.executable} {provider}", "contract": 1, **port}
    providers: dict = {"gate": "none"}
    if port is not None:
        providers["evals"] = port
    (root / ".agenticframework" / "providers.json").write_text(json.dumps({"contract": 3, "providers": providers}))
    subprocess.run(["git", "init", "-q", "--template=", str(root)], check=True)
    return root


def _launch(root: Path, suite: str = "golden", ci: bool = False) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin", "HOME": str(root)}
    if ci:
        env["GITHUB_ACTIONS"] = "true"
    return subprocess.run(["bash", str(LAUNCHER), "evals", "run", "--suite", suite], cwd=root, env=env,
                          capture_output=True, text=True, check=False, timeout=60)


@pytest.mark.parametrize("verdict, port, code", [
    ("pass", "default", 0),
    ("fail", "default", 1),
    ("no_verdict", "default", 1),
    ("not_gradable", "default", 1),
    ("no_verdict", {"no_verdict": {"golden": "warn"}}, 0),
    ("not_gradable", {"not_gradable": {"golden": "warn"}}, 0),
    ("no_verdict", {"no_verdict": {"fairness": "warn"}}, 1),
    ("no_verdict", {"not_gradable": {"golden": "warn"}}, 1),
    ("fail", {"no_verdict": {"golden": "warn"}}, 1),
    ("maybe", "default", 1),
    (None, "default", 1),
])
def test_the_launcher_passes_only_a_pass_unless_the_tenant_declared_a_warning(tmp_path, verdict, port, code):
    done = _launch(_launcher_tenant(tmp_path, verdict, port))
    assert done.returncode == code, done.stdout + done.stderr


def test_a_reason_cannot_start_a_workflow_command(tmp_path):
    """The reason quotes the tenant's data; in CI it is one annotation line."""
    root = _launcher_tenant(tmp_path, "fail")
    provider = tmp_path / "provider.py"
    provider.write_text("import json, sys\nsys.stdin.read()\nprint(json.dumps({'schema': 1, 'suite': 'golden', "
                        "'verdict': 'fail', 'reason': 'case x\\n::warning::injected'}))\n")
    done = _launch(root, ci=True)
    assert done.returncode == 1
    assert [line for line in done.stdout.splitlines() if line.startswith("::")] == [
        "::error title=Evals (golden)::fail — case x ::warning::injected"]


def test_the_declared_warning_is_visible_in_ci(tmp_path):
    done = _launch(_launcher_tenant(tmp_path, "no_verdict", {"no_verdict": {"golden": "warn"}}), ci=True)
    assert done.returncode == 0
    assert "::warning title=Evals (golden)::" in done.stdout and "proves nothing" in done.stdout


def test_a_scorecard_for_another_suite_fails_the_step(tmp_path):
    done = _launch(_launcher_tenant(tmp_path, "pass", suite="fairness"))
    assert done.returncode == 1 and "answered about fairness" in done.stderr


@pytest.mark.parametrize("port, said", [(None, "declares no evals provider"), ("none", "\"evals\": \"none\"")])
def test_no_declared_provider_judges_nothing_and_says_so(tmp_path, port, said):
    done = _launch(_launcher_tenant(tmp_path, "fail", port))
    assert done.returncode == 0 and said in done.stdout


@pytest.mark.parametrize("args", [("evals",), ("evals", "run"), ("evals", "run", "--suite", "nope"),
                                  ("evals", "judge", "--suite", "golden")])
def test_the_launcher_refuses_a_malformed_call(tmp_path, args):
    root = _launcher_tenant(tmp_path, "pass")
    done = subprocess.run(["bash", str(LAUNCHER), *args], cwd=root, capture_output=True, text=True, check=False)
    assert done.returncode == 2 and "usage: process-gate evals run --suite" in done.stderr


# ── The CLI ───────────────────────────────────────────────────────────────────


def test_the_cli_writes_the_request_from_suite(tmp_path, provider_env):
    root = _tenant(tmp_path)
    subprocess.run(["git", "init", "-q", "--template=", str(root)], check=True)
    done = subprocess.run([*PROVIDER.split(), "run", "--suite", "rag_poison"], cwd=root, input="",
                          capture_output=True, text=True, check=False, timeout=120)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["suite"] == "rag_poison"


def test_suite_without_run_is_refused(tmp_path, provider_env):
    done = subprocess.run([*PROVIDER.split(), "--suite", "golden"], cwd=tmp_path, input="",
                          capture_output=True, text=True, check=False, timeout=60)
    assert done.returncode == 2 and "--suite goes with run" in done.stderr
