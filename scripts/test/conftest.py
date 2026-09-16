"""
scripts/test/conftest.py — isolate these tests from this machine's `agentsmith` state.

The same isolation as runtime/test/conftest.py, for a run that collects only
scripts/test/: `agentsmith mode` and `agentsmith dashboard start` write
~/.agent-framework/state/, which the gateway and runtime/otlp.py read after the
environment, so without this a developer's mode would decide what these tests
resolve.
"""

from __future__ import annotations


def pytest_configure(config):
    import os
    import tempfile

    os.environ.setdefault("AGENTSMITH_STATE_DIR", tempfile.mkdtemp(prefix="agentsmith-test-state-"))


# The gated-repo fixture lives beside the gate's own tests; re-exported here so
# every gate suite builds the same repo shape instead of a second one.
from test_process_gate import gated_repo  # noqa: F401 — a fixture, used by name
