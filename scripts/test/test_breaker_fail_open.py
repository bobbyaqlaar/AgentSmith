"""
scripts/test/test_breaker_fail_open.py — the circuit breaker's callers must
survive a breaker they cannot load.

Both call sites document themselves as fail-open: the provider request has
already completed and already been paid for by the time the breaker is
consulted, so a bookkeeping fault must not fail the call. That guarantee was
not what the code did.

`agent_logger` held the import and the call in ONE try, with
`except CircuitBreakerTripped` as the first clause. When the import failed the
name was never bound, and Python evaluates except clauses in order — so
resolving it raised UnboundLocalError, which escaped the try rather than being
caught by the `except Exception` below it. The handler written to keep the call
alive was the thing that killed it.

`cost_router` imported the breaker bare, in the middle of the request path, so
the same failure propagated with no handler at all.

The trigger did not have to be exotic: circuit_breaker read its limits with
int()/float() at module level, so `AGENT_MONTHLY_USD_CAP=` — an environment
variable declared with no value, which is what a k8s manifest produces for an
unset input — was enough.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # scripts/

import agent_logger


@pytest.fixture
def _unimportable_breaker(monkeypatch):
    """Make `from circuit_breaker import ...` fail.

    None in sys.modules is the documented way to force ImportError, and it
    stands in for every real cause: a malformed module-level env read, a
    missing dependency, a syntax error in a half-applied edit.
    """
    monkeypatch.setitem(sys.modules, "circuit_breaker", None)


def test_llm_call_survives_a_breaker_it_cannot_import(
    _unimportable_breaker, monkeypatch, tmp_path, capsys
):
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    logger = agent_logger.AgentLogger(agent_name="fail-open-probe")

    entry = logger.llm_call("probe_event", 10, 5, model="m")

    assert entry is not None, "the log entry is written before the breaker runs"
    assert "unmetered" in capsys.readouterr().err


def test_the_unmetered_warning_names_the_cause(
    _unimportable_breaker, monkeypatch, tmp_path, capsys
):
    """Fail-open, but not fail-silent.

    An unmetered call is a real cost consequence, so the warning has to carry
    enough to act on — that the breaker was unavailable, and why.
    """
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    agent_logger.AgentLogger(agent_name="probe").llm_call("e", 1, 1, model="m")

    err = capsys.readouterr().err
    assert "circuit breaker unavailable" in err
    # The concrete class, not the base: the handler prints type(exc).__name__,
    # and "ModuleNotFoundError" is what an operator greps for.
    assert "ModuleNotFoundError" in err
