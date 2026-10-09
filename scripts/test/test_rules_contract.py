"""
scripts/test/test_rules_contract.py — the rules contract: what a tenant's agents
are told, rendered and checked by the provider it declares
(.agent-rfc/designs/rules-contract.md, contract/rules/v1/protocol.md).

The published files are held to the models; AgentSmith is held to the contract
as a provider, and two providers that break it are shown failing; the caller's
side — the path guard, the placement rules, the launcher's three outcomes, and
`sync` naming the provider's documents — is held here too.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import gate_models as gm

V1 = REPO / "contract" / "rules" / "v1"
PROVIDER = f"{sys.executable} -m runtime.cli rules"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git required")


@pytest.fixture
def provider_env(monkeypatch):
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("PYTHONPATH", str(REPO))


# ── The published contract ────────────────────────────────────────────────────


def test_agentsmith_passes_the_rules_contract(tmp_path, provider_env):
    from runtime import conformance

    report = conformance.run_rules(PROVIDER, tmp_path / "work")

    assert report.passed, report.render()
    assert len(report.checks) == len(conformance.rules_cases()) == 11
    assert not any("not applicable" in c.why for c in report.checks), report.render()


@pytest.mark.parametrize("name, model", [
    ("request.schema.json", "RulesRequest"),
    ("rendered.schema.json", "RulesRender"),
    ("check.schema.json", "RulesCheck"),
    ("extends.schema.json", "Extends"),
])
def test_the_rules_schemas_are_the_models(name, model):
    published = json.loads((V1 / name).read_text(encoding="utf-8"))
    generated = getattr(gm, model).model_json_schema()
    for key in ("description", "$schema", "$id"):
        published.pop(key, None)
        generated.pop(key, None)
    assert published == generated, f"contract/rules/v1/{name} no longer matches {model}"


def test_the_declared_port_is_the_model():
    schema = json.loads((V1 / "providers.schema.json").read_text(encoding="utf-8"))
    entry = schema["properties"]["providers"]["properties"]["rules"]["oneOf"][1]
    generated = gm.RulesPort.model_json_schema()
    for key in ("title", "description"):
        entry.pop(key, None)
        generated.pop(key, None)
    assert entry == generated


def test_what_adopt_declares_names_the_rules_provider_under_both_contracts():
    import jsonschema

    from runtime.adopt import providers_declaration

    declared = json.loads(providers_declaration())
    jsonschema.validate(declared, json.loads((V1 / "providers.schema.json").read_text()))
    jsonschema.validate(declared, json.loads((REPO / "contract/gate/v3/providers.schema.json").read_text()))
    assert declared["providers"]["rules"]["command"] == "agentsmith rules"
    assert declared["providers"]["rules"]["contract"] == 1


SAFE = ["CLAUDE.md", ".github/copilot-instructions.md", ".agents/skills/x/skill.md", ".gitignore",
        ".github/CODEOWNERS.md", "docs/.githooks-notes.md", ".cursorrules"]
UNSAFE = ["/etc/passwd", "../outside.md", "a/../b.md", "./CLAUDE.md", "a//b.md", "docs/", ".git/config",
          ".GIT/hooks/pre-commit", ".githooks/pre-push", ".Githooks/commit-msg", ".agenticframework/providers.json",
          ".github/workflows/x.yml", ".GitHub/Actions/a/action.yml", "a\\b.md", ".git", "x/./y.md", "a\nb.md"]


@pytest.mark.parametrize("path", SAFE + UNSAFE)
def test_the_path_rule_is_one_rule_in_the_model_and_the_schema(path):
    """The caller validates with the model; another platform validates with the
    published schema. They must refuse the same paths
    (`pin-unremovable-duplicates`)."""
    import jsonschema

    entry = {"path": path, "text": "", "placement": "whole", "kind": "supporting"}
    try:
        gm.RulesFile.model_validate(entry)
        by_model = True
    except gm.ValidationError:
        by_model = False
    try:
        jsonschema.validate({"files": [entry]}, json.loads((V1 / "rendered.schema.json").read_text()))
        by_schema = True
    except jsonschema.ValidationError:
        by_schema = False
    assert by_model == by_schema == (path in SAFE), path


def test_a_render_naming_a_path_twice_is_refused():
    entry = {"path": "CLAUDE.md", "text": "", "placement": "whole", "kind": "instructions"}
    with pytest.raises(gm.ValidationError):
        gm.RulesRender.model_validate({"files": [entry, {**entry, "path": "claude.md"}]})


# ── Providers that break it are seen to ───────────────────────────────────────


STUB = '''
import json, os, sys
verb = sys.argv[1] if len(sys.argv) > 1 else ""
note = {note!r}
owner = os.environ.get("AGENT_OWNER_ID", "") if {reads_env!r} else ""
text = "# Rules\\n" + note + owner + "\\n"
if verb == "render":
    print(json.dumps({{"files": [{{"path": "AGENTS.md", "text": text, "placement": "whole",
                                   "kind": "instructions"}}]}}))
elif verb == "check":
    print(json.dumps({{"decision": "allow", "text": "", "files": []}}))
else:
    sys.exit(2)
'''


def _stub(tmp_path: Path, *, note: str, reads_env: bool) -> str:
    script = tmp_path / "stub_rules.py"
    script.write_text(STUB.format(note=note, reads_env=reads_env), encoding="utf-8")
    return f"{sys.executable} {script}"


def test_a_provider_that_ignores_the_tenants_notes_and_drift_fails(tmp_path, provider_env):
    from runtime import conformance

    report = conformance.run_rules(_stub(tmp_path, note="", reads_env=False), tmp_path / "work")

    failed = {c.name for c in report.checks if not c.ok}
    assert not report.passed
    assert "every note is in every instructions file" in failed
    assert {"a change to a whole file is drift", "a changed note is drift"} <= failed


def test_a_provider_that_reads_the_environment_fails(tmp_path, provider_env):
    from runtime import conformance

    notes = "\n".join(conformance.rules_fixture()["notes"])
    report = conformance.run_rules(_stub(tmp_path, note=notes, reads_env=True), tmp_path / "work")

    failed = {c.name for c in report.checks if not c.ok}
    assert "render reads no environment" in failed
    assert "every note is in every instructions file" not in failed


# ── Placement: the contract's rules, the caller's code ────────────────────────


def _port():
    from runtime.adopt import rules_port

    return rules_port(REPO)


def _file(text: str, placement: str = "block") -> gm.RulesFile:
    return gm.RulesFile(path="CLAUDE.md", text=text, placement=placement, kind="instructions")


def test_a_block_is_appended_once_then_replaced_and_the_tenants_text_survives():
    port = _port()
    own = "# Ours\n\nWritten by hand.\n"

    once = port.place(own, _file("rules v1\n"))
    twice = port.place(once + "\nMore of ours.\n", _file("rules v2\n"))

    assert once.startswith(own.rstrip("\n")) and once.count("agentsmith:rules:begin") == 1
    assert twice.count("agentsmith:rules:begin") == 1 and "rules v2" in twice and "rules v1" not in twice
    assert twice.startswith(own.rstrip("\n")) and twice.endswith("More of ours.\n")
    assert port.state(twice, _file("rules v2\n")) == "current"


def test_text_outside_the_block_is_never_compared_and_a_file_without_markers_has_drifted():
    port = _port()
    placed = port.place("# Ours\n", _file("rules\n"))

    assert port.state(placed + "\nA line of ours.\n", _file("rules\n")) == "current"
    assert port.state(placed.replace("rules\n", "rules, edited\n"), _file("rules\n")) == "drifted"
    assert port.state("# Ours, and no block\n", _file("rules\n")) == "drifted"
    assert port.state(None, _file("rules\n")) == "absent"


def test_a_whole_file_is_replaced_and_any_change_to_it_is_drift():
    port = _port()
    assert port.place("anything\n", _file("rules\n", "whole")) == "rules\n"
    assert port.state("rules\n", _file("rules\n", "whole")) == "current"
    assert port.state("rules\nmore\n", _file("rules\n", "whole")) == "drifted"


def test_a_marker_quoted_inside_a_line_is_not_a_marker():
    """Markers stand on lines of their own — a document that mentions one in
    prose is not split there."""
    port = _port()
    prose = "Our rules live after `<!-- agentsmith:rules:begin` in this file.\n"
    assert port.region(prose) is None
    assert port.place(prose, _file("rules\n")).startswith(prose.rstrip("\n"))


# ── The caller refuses a bad render whole ─────────────────────────────────────


def _tenant(tmp_path: Path, command: str) -> Path:
    root = tmp_path / "tenant"
    (root / ".agenticframework").mkdir(parents=True)
    (root / ".agenticframework" / "providers.json").write_text(json.dumps(
        {"contract": 3, "providers": {"gate": "none", "rules": {"command": command, "contract": 1}}}))
    subprocess.run(["git", "init", "-q", "--template=", str(root)], check=True)
    return root


def _bad_provider(tmp_path: Path, path: str) -> str:
    script = tmp_path / "bad_rules.py"
    script.write_text("import json\nprint(json.dumps({'files': ["
                      "{'path': 'AGENTS.md', 'text': 'fine', 'placement': 'whole', 'kind': 'instructions'}, "
                      f"{{'path': {path!r}, 'text': 'exit 0', 'placement': 'whole', 'kind': 'supporting'}}]}}))\n")
    return f"{sys.executable} {script}"


def test_a_render_that_names_a_hook_is_refused_and_nothing_is_written(tmp_path):
    from runtime.adopt import RulesUnavailable, rendered_rules

    root = _tenant(tmp_path, _bad_provider(tmp_path, ".githooks/pre-push"))

    with pytest.raises(RulesUnavailable, match="path"):
        rendered_rules(root, REPO)
    assert not (root / "AGENTS.md").exists() and not (root / ".githooks").exists()


def test_a_provider_that_gives_no_render_is_named(tmp_path):
    from runtime.adopt import RulesUnavailable, rendered_rules

    (tmp_path / "provider.py").write_text("import sys\nsys.exit(3)\n")
    root = _tenant(tmp_path, f"{sys.executable} {tmp_path / 'provider.py'}")

    with pytest.raises(RulesUnavailable, match="exit 3"):
        rendered_rules(root, REPO)


def test_none_declared_renders_nothing(tmp_path):
    from runtime.adopt import rendered_rules

    root = _tenant(tmp_path, "unused")
    (root / ".agenticframework" / "providers.json").write_text(json.dumps(
        {"contract": 3, "providers": {"gate": "none", "rules": "none"}}))

    assert rendered_rules(root, REPO).files == []


# ── The render reads declarations, not the environment ────────────────────────


def test_the_render_context_ignores_the_environment(tmp_path, monkeypatch):
    from _shared import load_script

    gen = load_script("generate-ide-config")
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text(
        'tenant:\n  id: "t"\n  name: "t"\n  owner: o@example.test\nframework:\n  version: "2.1.0"\n')
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")
    (tmp_path / "uv.lock").write_text("")
    plain = gen.declared_context(tmp_path)

    monkeypatch.setenv("AGENT_OWNER_ID", "junk@junk.test")
    monkeypatch.setenv("AGENT_PHOENIX_ENDPOINT", "http://junk.test:1")
    monkeypatch.setenv("FRAMEWORK_VERSION", "9.9.9")

    assert gen.declared_context(tmp_path) == plain
    assert plain["owner_id"] == "o@example.test" and plain["framework_version"] == "2.1.0"
    assert plain["test_cmd"] == "uv run pytest", "the lock file decides the default, as adopt always did"


# ── The launcher: three outcomes ──────────────────────────────────────────────


def _launcher_repo(tmp_path: Path, rules: object) -> Path:
    root = tmp_path / "repo"
    (root / ".githooks").mkdir(parents=True)
    shutil.copy2(REPO / ".githooks" / "process-gate", root / ".githooks" / "process-gate")
    (root / ".agenticframework").mkdir()
    providers = {"contract": 3, "providers": {"gate": {"command": "agentsmith gate", "contract": 3}}}
    if rules is not None:
        providers["providers"]["rules"] = rules
    (root / ".agenticframework" / "providers.json").write_text(json.dumps(providers, indent=2))
    subprocess.run(["git", "init", "-q", "--template=", str(root)], check=True)
    return root


def _check(root: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}
    return subprocess.run(["bash", ".githooks/process-gate", "rules", "check"], cwd=root, capture_output=True,
                          text=True, check=False, env=env)


@pytest.mark.parametrize("rules", [None, "none"])
def test_no_rules_provider_declared_passes_and_says_so(tmp_path, rules):
    done = _check(_launcher_repo(tmp_path, rules))
    assert done.returncode == 0
    assert "nothing checked" in done.stdout


@pytest.mark.parametrize("body, says", [
    ("import sys; sys.exit(3)", "cannot run here (exit 3)"),
    (None, "not installed (exit 127)"),
    ("print('not json')", "printed no decision"),
])
def test_a_declared_provider_that_gives_no_answer_fails_and_says_how(tmp_path, body, says):
    """The launcher splits the command into words, as it does the gate's: a
    provider is a program, not a shell snippet."""
    command = "no-such-rules-provider-anywhere"
    if body is not None:
        (tmp_path / "provider.py").write_text(body + "\n")
        command = f"{sys.executable} {tmp_path / 'provider.py'}"
    done = _check(_launcher_repo(tmp_path, {"command": command}))
    assert done.returncode == 1
    assert says in done.stderr and "rules provider gave no decision" in done.stderr


def test_the_launcher_carries_the_providers_verdict(tmp_path):
    deny = json.dumps({"decision": "deny", "text": "CLAUDE.md drifted", "report": "the diff", "files": []})
    allow = json.dumps({"decision": "allow", "text": "", "files": []})
    for answer, code in ((deny, 1), (allow, 0)):
        script = tmp_path / "answer.py"
        script.write_text(f"print({answer!r})\n")
        done = _check(_launcher_repo(tmp_path / str(code), {"command": f"{sys.executable} {script}"}))
        assert done.returncode == code
        if code:
            assert "CLAUDE.md drifted" in done.stderr and "the diff" in done.stdout


def test_the_launcher_reads_each_port_apart(tmp_path):
    """Two ports in one declaration: the gate's command is never taken for the
    rules provider's, whichever comes first."""
    root = _launcher_repo(tmp_path, {"command": "rules-cmd"})
    data = json.loads((root / ".agenticframework" / "providers.json").read_text())
    reordered = {"contract": 3, "providers": {"rules": data["providers"]["rules"], "gate": data["providers"]["gate"]}}
    for declaration in (data, reordered):
        (root / ".agenticframework" / "providers.json").write_text(json.dumps(declaration, indent=2))
        script = 'eval "$(sed -n "/^decl_get()/,/^}/p;/^declared_port()/,/^}/p" .githooks/process-gate)"; root=$PWD; ' \
                 'echo "$(declared_port gate)|$(declared_port rules)"'
        done = subprocess.run(["bash", "-c", script], cwd=root, capture_output=True, text=True, check=False)
        assert done.stdout.strip() == "agentsmith gate|rules-cmd", declaration


def test_the_gates_workflow_checks_the_rules_after_the_gate():
    import yaml

    workflow = yaml.safe_load((REPO / "workflow-templates" / "agentsmith-gates.yml").read_text(encoding="utf-8"))
    runs = [step.get("run", "") for step in workflow["jobs"]["process-gates"]["steps"]]
    gate = next(i for i, run in enumerate(runs) if "process-gate ci" in run)
    rules = next(i for i, run in enumerate(runs) if "process-gate rules check" in run)
    assert rules > gate


# ── The provider's documents, named without its paths ────────────────────────


def test_provider_names_the_gate_providers_own_document():
    import process_gate as pg

    config = pg.Config({"gated": ["**"], "registry": "provider", "levers_doc": "provider",
                        "design_checklist": "provider"})

    assert config.registry == "@framework/templates/governance.json"
    assert config.registry_declared, "declared, so the pillar requirements apply"
    assert config.levers_doc == "@framework/docs/review-levers.md"
    assert config.design_checklist == "@framework/docs/design-review-checklist.md"
    assert pg.Config({"gated": ["**"], "levers_doc": "docs/levers.md"}).levers_doc == "docs/levers.md"


def test_adopt_writes_provider_not_this_installs_paths():
    from runtime.cli import _process_gates_config

    config = json.loads(_process_gates_config("python-fastapi"))
    assert {config[k] for k in ("registry", "levers_doc", "design_checklist")} == {"provider"}
    assert "@framework/" not in json.dumps(config)


def test_sync_renames_only_what_adopt_wrote_and_leaves_every_other_byte():
    from runtime.sync import provider_documents

    before = ('{\n  "gated": ["src/**"],\n  "registry": "@framework/templates/governance.json",\n'
              '  "levers_doc":   "@framework/docs/review-levers.md",\n'
              '  "design_checklist": "@framework/docs/our-own-checklist.md"\n}\n')
    after = provider_documents(before)

    assert after == before.replace('"@framework/templates/governance.json"', '"provider"') \
        .replace('"@framework/docs/review-levers.md"', '"provider"')
    assert '"@framework/docs/our-own-checklist.md"' in after, "a value the tenant chose is theirs"
    assert provider_documents('{"registry": "templates/governance.json"}') == \
        '{"registry": "templates/governance.json"}'
