"""
scripts/test/test_standalone_without_runtime.py — scripts/ must start when
`runtime` is not importable.

`scripts/` is machine-installed (~/.agent-framework/scripts) and `runtime/`
ships as a pip package. They are not guaranteed co-located, and the normal
invocation — `python3 <install>/scripts/foo.py` from a tenant directory — puts
`scripts/` on sys.path[0] and the framework root nowhere. Any module-reachable
`from runtime...` that is neither guarded nor preceded by an explicit
sys.path insert kills the process before it does any work.

This has now shipped twice, and the second time it was expensive. `_load_dotenv`
in `_shared` acquired an unconditional `from runtime.config import
load_env_file` on 2026-08-24. It took out the KYC Sentinel judged-eval split run
for five consecutive daily windows (08-25 → 08-29): the driver read the nonzero
exit as "judge unreachable", logged `NO VERDICT — will retry in a later window`,
and the failure presented as an exhausted free-tier quota. Golden and
hallucination graded nothing for five days while the log said the gate was
merely waiting its turn. `agent_logger._owner` had the identical defect and
killed AgentLogger's constructor.

The whole local suite passed throughout, both times. That is the point of this
file: pytest puts the repo root on sys.path, so an in-process test imports
`runtime` successfully no matter what, and is structurally incapable of failing
on this. Only a subprocess with a clean path can catch it — which is why every
test here shells out and clears PYTHONPATH explicitly rather than trusting the
inherited one.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def _run_standalone(code: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run `code` with ONLY scripts/ importable — no framework root, no
    inherited PYTHONPATH."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        # Not check=True: a nonzero exit is the finding, and the assertions
        # below report stderr. Raising here would hide the traceback that says
        # which import died.
        check=False,
    )


def _tenant(tmp_path: Path) -> Path:
    """A directory that looks like a tenant checkout to `_repo_root`."""
    (tmp_path / ".agenticframework").mkdir(exist_ok=True)
    (tmp_path / ".env").write_text(
        "OLLAMA_BASE_URL=http://localhost:11434   # intake route\n", encoding="utf-8"
    )
    return tmp_path


def test_runtime_really_is_absent(tmp_path: Path) -> None:
    """Guard the guard. If a future change makes `runtime` importable from a
    bare subprocess — an editable install, a stray .pth, a conftest that
    reaches out — every other test in this file would pass without testing
    anything, exactly like the in-process suite did for five days."""
    proc = _run_standalone(
        "import importlib.util, sys;"
        f"sys.path.insert(0, {str(SCRIPTS)!r});"
        "print(importlib.util.find_spec('runtime') is not None)",
        _tenant(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "False", (
        "`runtime` is importable in a clean subprocess, so the tests in this "
        "file no longer prove anything about the standalone path"
    )


def test_run_evals_entrypoint_starts(tmp_path: Path) -> None:
    """The real invocation the eval drivers use: `python3 <install>/scripts/
    run-evals.py` from a tenant directory. `--help` is enough — `_load_dotenv()`
    runs at import time, before argparse, which is why the crash presented on
    every subcommand including this one."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "run-evals.py"), "--help"],
        cwd=str(_tenant(tmp_path)),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,  # see _run_standalone
    )
    assert "ModuleNotFoundError" not in proc.stderr, proc.stderr
    assert proc.returncode == 0, f"exit={proc.returncode}\n{proc.stderr}"
    assert "usage: run-evals.py" in proc.stdout


def test_dotenv_still_loads_without_runtime(tmp_path: Path) -> None:
    """Starting is not enough — the loader must still do its job, or the judge
    runs with no credentials and the suite fails as a quality regression.

    The inline comment is the assertion that matters: it proves the standalone
    branch went through `_dotenv_value` rather than a cruder re-implementation.
    """
    proc = _run_standalone(
        "import sys, os;"
        f"sys.path.insert(0, {str(SCRIPTS)!r});"
        "from _shared import _load_dotenv;"
        "os.environ.pop('OLLAMA_BASE_URL', None);"
        "_load_dotenv();"
        "print(os.environ.get('OLLAMA_BASE_URL'))",
        _tenant(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "http://localhost:11434"


def test_agent_logger_constructs(tmp_path: Path) -> None:
    """`AgentLogger.__init__` resolves two owner fields through
    `runtime.config.resolve`. Unguarded, that made the logger unusable from any
    standalone script — and the logger is what several of them log through."""
    proc = _run_standalone(
        "import sys;"
        f"sys.path.insert(0, {str(SCRIPTS)!r});"
        "from agent_logger import AgentLogger;"
        "lg = AgentLogger(agent_name='Probe', agent_role='subagent', orchestrator='none');"
        "print(bool(lg.owner_id) and bool(lg.owner_name))",
        _tenant(tmp_path),
    )
    assert "ModuleNotFoundError" not in proc.stderr, proc.stderr
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "True"


def test_agent_logger_prefers_the_ambient_owner_when_degraded(tmp_path: Path) -> None:
    """In the degraded path the environment is consulted before git. Pinned
    because the fallback deliberately does NOT rebuild `resolve`'s four-layer
    precedence — so the little of it that survives should be on the record."""
    proc = _run_standalone(
        "import sys, os;"
        f"sys.path.insert(0, {str(SCRIPTS)!r});"
        "os.environ['AGENT_OWNER_ID'] = 'someone@example.test';"
        "from agent_logger import AgentLogger;"
        "lg = AgentLogger(agent_name='Probe', agent_role='subagent', orchestrator='none');"
        "print(lg.owner_id)",
        _tenant(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "someone@example.test"
