"""
scripts/test/test_vendoring_retired.py — a tenant holds no copy of AgentSmith,
and nothing runs one (.agent-rfc/designs/vendoring-retired.md, C9, 3.0.0).

Until 3.0.0 a repository could be governed by code it carried: the machine-wide
post-checkout vendored scripts/ and runtime/, the workflow templates ran them by
path, `sync` and `upgrade` refreshed them, and the launcher and the machine's
commands preferred a tenant's copy to the provider's. These hold the other side:
what `tenant init` writes asks the provider, nothing is copied in, a copy left
behind is named and never run, and no hook is armed outside a repository.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from _shared import load_script  # bound now: `init_tenant` later puts an install's scripts/ first
from runtime.adopt import SETUP_ACTION, is_machine_hook, retired_machine_hooks, stub_names
from runtime.cli import init_tenant

LAUNCHER = REPO / ".githooks" / "process-gate"
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")


def _verify_system():
    """This checkout's verify_system: `init_tenant` puts the installed
    framework's scripts/ on sys.path, and a bare import could load that copy."""
    module = load_script("verify_system", cache=False)
    assert Path(module.__file__).resolve().parent == REPO / "scripts", module.__file__
    return module


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@x", *args],
                   check=True, capture_output=True)


@pytest.fixture()
def scaffolded(tmp_path: Path) -> Path:
    root = tmp_path / "tenant"
    root.mkdir()
    _git(root, "init", "-q", "--template=")
    init_tenant("acme", root, stack="python-fastapi", framework_ref="abc1234")
    return root


# ── What `tenant init` writes ────────────────────────────────────────────────


def test_init_declares_the_providers_its_workflows_ask(scaffolded: Path):
    declared = json.loads((scaffolded / ".agenticframework" / "providers.json").read_text())
    assert declared["providers"]["gate"]["setup"] == f"{SETUP_ACTION}@abc1234"
    for port in ("rules", "evals", "security"):
        assert port in declared["providers"]
    # A repository init just created exports no telemetry; said, so the security
    # port answers "not applicable" rather than failing SEC-PII-002.
    assert declared["providers"]["security"]["emitter"] == "none"
    # ...and no eval data of its own: each judged suite warns, visibly, until it has some.
    for verdict in ("not_gradable", "no_verdict"):
        assert declared["providers"]["evals"][verdict] == {s: "warn" for s in ("golden", "fairness", "hallucination")}
    for workflow in ("agentsmith-gates.yml", "agentsmith-sync.yml"):
        assert (scaffolded / ".github" / "workflows" / workflow).is_file()


def test_every_workflow_asks_the_provider_at_the_declared_release(scaffolded: Path):
    """No template placeholder survives, no step runs a tenant's scripts/ or
    runtime/, and every AgentSmith action is referenced at the setup's release."""
    for workflow in (scaffolded / ".github" / "workflows").glob("*.yml"):
        text = workflow.read_text()
        assert not PLACEHOLDER.search(text), f"{workflow.name} carries an unfilled placeholder"
        assert not re.search(r"python3? (-m )?(scripts/|runtime\.)", text), f"{workflow.name} runs a copy by path"
        assert "uses: ./.github/actions/" not in text, f"{workflow.name} expects a copied action"
        for ref in re.findall(r"bobbyaqlaar/AgentSmith/\.github/actions/[a-z-]+@([^\"\s]+)", text):
            assert ref == "abc1234", f"{workflow.name} takes an action from {ref}, not the declared release"


def test_init_copies_none_of_agentsmiths_code(scaffolded: Path):
    for path in ("scripts", "runtime", "fixtures/security", ".github/actions"):
        assert not (scaffolded / path).exists(), f"tenant init wrote {path}/"


def test_init_seeds_the_tenants_own_data_without_overwriting(tmp_path: Path):
    root = tmp_path / "tenant"
    (root / ".agent-rfc" / "security").mkdir(parents=True)
    (root / ".agent-rfc" / "security" / "risk_register.yaml").write_text("risks: [ours]\n")
    _git(root, "init", "-q", "--template=")
    written = init_tenant("acme", root, stack="go")
    assert (root / ".agent-rfc" / "security" / "risk_register.yaml").read_text() == "risks: [ours]\n"
    assert ".agent-rfc/security/risk_register.yaml" not in written
    for seeded in (".agent-rfc/security/agency_manifest.yaml", ".agent-rfc/security/tool_allowlist.yaml"):
        assert seeded in written and (root / seeded).is_file(), seeded
    # The framework's base eval cases carry no `actual_output`: seeded, they
    # could never be this repository's dataset under contract/evals/v1.
    assert not (root / ".agent-rfc" / "fixtures" / "golden_evals.json").exists()


# ── A copy left behind is named, and never run ───────────────────────────────


def _tenant_with_copies(tmp_path: Path) -> Path:
    root = tmp_path / "old-tenant"
    for rel, body in {"scripts/process_gate.py": "raise SystemExit('the copy ran')\n",
                      "scripts/run-security-checks.py": "# a stale copy\n",
                      "scripts/my_own_tool.py": "print('mine')\n",
                      "runtime/llm_gateway.py": "# a stale copy\n",
                      ".github/actions/gcp-auth/action.yml": "name: x\n",
                      "fixtures/golden_evals_base.json": "[]\n",
                      "fixtures/our_data.json": "[]\n"}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    _git(root, "init", "-q", "--template=")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "old", "--no-verify")
    return root


def test_the_governed_check_names_each_copy_by_path(tmp_path: Path):
    copies = dict(_verify_system().framework_copies(_tenant_with_copies(tmp_path), REPO))
    assert set(copies) == {"scripts/process_gate.py", "scripts/run-security-checks.py", "runtime/llm_gateway.py",
                           ".github/actions/gcp-auth/action.yml", "fixtures/golden_evals_base.json"}
    assert "uses: bobbyaqlaar/AgentSmith/.github/actions" in copies[".github/actions/gcp-auth/action.yml"]


def test_the_governed_check_finds_nothing_in_agentsmith_itself():
    assert _verify_system().framework_copies(REPO, REPO) == []


def test_sync_names_a_copy_and_never_refreshes_it(tmp_path: Path):
    from runtime.sync import plan_sync

    root = _tenant_with_copies(tmp_path)
    (root / ".agenticframework").mkdir()
    (root / ".agenticframework" / "process-gates.json").write_text(json.dumps({"gated": ["**"]}))
    plan = plan_sync(root, framework=REPO)
    assert plan.vendored == ["runtime", "scripts"]
    assert any("no longer refreshes" in note for note in plan.notes)
    assert not any(path.startswith(("scripts/", "runtime/")) for path in plan.stale + plan.added)


def test_the_launcher_never_runs_a_tenants_copy_of_the_gate(tmp_path: Path):
    """A tenant's scripts/process_gate.py is not the gate: with no provider
    installed the launcher says so, rather than running the copy."""
    root = _tenant_with_copies(tmp_path)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path / "no-home")}
    done = subprocess.run(["bash", str(LAUNCHER), "artifacts"], cwd=root, env=env,
                          capture_output=True, text=True, check=False, timeout=60)
    assert "the copy ran" not in done.stdout + done.stderr
    assert "not found in $AGENTSMITH_DIR or ~/.agent-framework" in done.stdout + done.stderr


def test_the_machine_commands_never_take_a_tenants_script(tmp_path: Path, monkeypatch):
    from runtime.machine.state import find_script

    root = _tenant_with_copies(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
    found = find_script("process_gate.py", cwd=root)
    assert found is None, f"took {found}"  # no install under this HOME, and never the tenant's


# ── No hook outside a repository ─────────────────────────────────────────────


def test_an_old_installs_provisioning_hooks_are_never_chained(tmp_path: Path):
    prior = tmp_path / "hooks"
    prior.mkdir()
    for name, line in (("post-checkout", "# AgentSmith: post-checkout"), ("post-commit", "# AgentSmith: post-commit"),
                       ("post-merge", "# their own")):
        hook = prior / name
        hook.write_text(f"#!/usr/bin/env bash\n{line}\nexit 0\n")
        hook.chmod(0o755)
    assert is_machine_hook(prior / "post-checkout")
    assert stub_names(prior) == ["post-merge"]
    assert sorted(retired_machine_hooks(prior)) == ["post-checkout", "post-commit"]


def test_the_installer_arms_no_hook_outside_a_repository():
    """It may only ever put back or unset init.templateDir — never point it at
    AgentSmith's templates — and ships no machine-wide hooks to copy."""
    text = (REPO / "install-ai-stack.sh").read_text()
    sets = [v for v in re.findall(r'git config --global init\.templateDir ("[^"]+"|\S+)', text)
            if not v.startswith("2>")]  # a read, `... init.templateDir 2>/dev/null`
    assert sets == ['"$PREVIOUS_TEMPLATE_DIR"'], sets
    assert not (REPO / "hooks").exists()
    assert "/hooks/post-checkout" not in text


# ── The knowledge-graph check, asked of the provider ─────────────────────────


def test_kg_check_fails_a_stale_graph_and_passes_once_regenerated(scaffolded: Path):
    """The templates' graph step asks the declared gate provider (`kg check`)
    instead of running a copy of verify_system. A tracked module the committed
    graph does not know fails it; the graph is rewritten in place, so the next
    run passes and the fix is a commit."""
    def check() -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(LAUNCHER), "kg", "check"], cwd=scaffolded,
                              capture_output=True, text=True, check=False, timeout=120)

    _git(scaffolded, "add", "-A")
    _git(scaffolded, "commit", "-qm", "scaffold", "--no-verify")
    assert check().returncode == 0
    (scaffolded / "app").mkdir(exist_ok=True)
    (scaffolded / "app" / "added.py").write_text("def added():\n    return 1\n")
    _git(scaffolded, "add", "app/added.py")
    stale = check()
    assert stale.returncode == 1 and "stale" in stale.stdout + stale.stderr
    assert check().returncode == 0


def test_kg_check_takes_no_other_verb(scaffolded: Path):
    done = subprocess.run(["bash", str(LAUNCHER), "kg", "build"], cwd=scaffolded,
                          capture_output=True, text=True, check=False, timeout=60)
    assert done.returncode == 2 and "usage: process-gate kg check" in done.stderr


def test_the_provider_setup_installs_what_kg_check_imports(scaffolded: Path, tmp_path: Path):
    """The setup step installs scripts/requirements-gate.txt and nothing else, so
    `kg check` must run on that list. It loads the graph with networkx; without
    it, every tenant's graph step failed on an ImportError (the scratch tenants,
    the first run after merge). This checkout's environment has networkx, so the
    gap only showed in CI: block it here to see the step's real dependency."""
    blocker = tmp_path / "without_networkx.py"
    blocker.write_text("import runpy, sys\nsys.modules['networkx'] = None\npath = sys.argv[1]\n"
                       "sys.argv = [path] + sys.argv[2:]\nrunpy.run_path(path, run_name='__main__')\n")
    _git(scaffolded, "add", "-A")
    _git(scaffolded, "commit", "-qm", "scaffold", "--no-verify")
    done = subprocess.run([sys.executable, str(blocker), str(REPO / "scripts" / "verify_system.py"),
                           "--check-kg-fresh"],
                          cwd=scaffolded, capture_output=True, text=True, check=False, timeout=120)
    assert done.returncode != 0 and "networkx" in done.stderr, \
        "kg check no longer needs networkx — drop it from the list"
    required = [line.split("#")[0].strip() for line in
                (REPO / "scripts" / "requirements-gate.txt").read_text(encoding="utf-8").splitlines()]
    assert any(line.startswith("networkx") for line in required), "the setup step must install what kg check imports"
