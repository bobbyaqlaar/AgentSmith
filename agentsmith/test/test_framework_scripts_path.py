"""
agentsmith/test/test_framework_scripts_path.py — importing from the framework's
`scripts/` leaves `sys.path` as it found it (.agent-rfc/designs/ruff-s-rules.md,
Pass 7 follow-up F).

`gate_ides_module`, `sync._shared_files` and `adopt.adopt` put
`<framework>/scripts` at `sys.path[0]` to import `gate_ides`, and never took it
off. When the framework was the machine's installed copy, every later
`import notifier` or `import _shared` in the same process resolved to that
stale copy, and the tests that pin those modules tested the wrong file.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture()
def fresh_gate_ides():
    """`gate_ides` out of sys.modules for one test and put back after, so the
    fake one a test imports does not answer for the real one later."""
    prior = sys.modules.pop("gate_ides", None)
    yield
    sys.modules.pop("gate_ides", None)
    if prior is not None:
        sys.modules["gate_ides"] = prior


def _fake_framework(tmp_path: Path) -> Path:
    fw = tmp_path / "framework"
    (fw / "scripts").mkdir(parents=True)
    (fw / "scripts" / "gate_ides.py").write_text("MARK = 'fake'\n", encoding="utf-8")
    return fw


def test_gate_ides_module_leaves_sys_path_as_it_found_it(tmp_path, fresh_gate_ides):
    from agentsmith.cli import gate_ides_module

    fw = _fake_framework(tmp_path)
    before = list(sys.path)
    module = gate_ides_module(fw)
    assert module is not None and module.MARK == "fake"
    assert sys.path == before


def test_an_entry_already_on_sys_path_is_neither_duplicated_nor_removed(tmp_path, monkeypatch, fresh_gate_ides):
    from agentsmith.cli import gate_ides_module

    fw = _fake_framework(tmp_path)
    monkeypatch.setattr(sys, "path", [str(fw / "scripts"), *sys.path])
    before = list(sys.path)
    gate_ides_module(fw)
    assert sys.path == before


def test_the_entry_is_removed_when_the_block_raises(tmp_path):
    from agentsmith.cli import framework_scripts_on_path

    fw = _fake_framework(tmp_path)
    before = list(sys.path)
    with pytest.raises(RuntimeError), framework_scripts_on_path(fw):
        assert sys.path[0] == str(fw / "scripts")
        raise RuntimeError("boom")
    assert sys.path == before


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@x", *args],
                          capture_output=True, text=True, check=False)


@pytest.fixture()
def tenant(tmp_path, monkeypatch):
    """A one-commit Python repository, before `tenant adopt`."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("AGENTSMITH_PYTHON", sys.executable)
    root = tmp_path / "tenant"
    (root / "mypkg").mkdir(parents=True)
    (root / "mypkg" / "core.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname = "t"\nversion = "0.1.0"\n', encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "feat: the tenant's own code")
    return root


def test_adopt_and_sync_leave_sys_path_as_they_found_it(tenant, monkeypatch):
    from agentsmith.adopt import adopt, plan_adoption, rules_port
    from agentsmith.sync import _shared_files, plan_sync

    # `scripts/rules_port.py` inserts its own directory when it is imported, and
    # its functions import `_shared` and `gate_tracing` when called, so that entry
    # stays by design (the design note's follow-up F). Loaded first, so what is
    # measured is what `adopt` and `sync` themselves leave.
    rules_port(REPO)
    # Then the framework's scripts/ is taken off sys.path (pytest.ini's
    # `pythonpath` puts it there for the whole session). With it present, the
    # helper has nothing to insert, and a site that inserted only if absent and
    # never removed would pass unseen (Pass 8, item M).
    scripts = str(REPO / "scripts")
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != scripts])
    before = list(sys.path)
    adopt(plan_adoption("t", tenant, architecture="layered"))
    assert sys.path == before, "adopt left an entry on sys.path"
    _shared_files(plan_sync(tenant, framework=REPO))
    assert sys.path == before, "sync left an entry on sys.path"


def test_the_suite_resolves_this_checkout_not_the_machines_install():
    """The autouse fixture in conftest.py: without it, a test that reaches
    `cli._framework_dir` with no AGENTSMITH_DIR picks `~/.agent-framework`."""
    import os

    from agentsmith.cli import _framework_dir

    assert os.environ.get("AGENTSMITH_DIR") == str(REPO)
    assert _framework_dir() == REPO
