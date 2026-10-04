"""
scripts/test/provider_shim.py — this checkout's `agentsmith` on PATH, for tests.

A tenant declares `"command": "agentsmith gate"` and, at gate contract 3, its
commits ask that command (.agent-rfc/designs/gate-local-events.md). Without this,
`agentsmith` is whatever the machine installed — an older release that does not
know `commit`, so every commit a test makes is blocked — or, in CI, nothing at
all. This is the test suite's equivalent of `.github/actions/setup-agentsmith`:
the provider being tested is the one being changed. It defers to an
AGENTSMITH_DIR a test sets, and otherwise points at this checkout, never at
~/.agent-framework.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def install() -> Path:
    """Write the shim once per process and put it first on PATH. Idempotent."""
    existing = os.environ.get("AGENTSMITH_TEST_PROVIDER_BIN")
    if existing and Path(existing, "agentsmith").is_file():
        return Path(existing)
    bin_dir = Path(tempfile.mkdtemp(prefix="agentsmith-test-provider-"))
    shim = bin_dir / "agentsmith"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        f'export AGENTSMITH_DIR="${{AGENTSMITH_DIR:-{REPO}}}"\n'
        # -P: `python -m` otherwise puts the working directory first on the
        # path — inside a vendored tenant, its own older `runtime/`.
        f'PYTHONPATH="{REPO}${{PYTHONPATH:+:$PYTHONPATH}}" exec "{sys.executable}" -P -m runtime.cli "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    os.environ["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    os.environ["AGENTSMITH_TEST_PROVIDER_BIN"] = str(bin_dir)
    return bin_dir
