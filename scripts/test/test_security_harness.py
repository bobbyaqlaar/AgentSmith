from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_run_security_checks_smoke_exits_zero() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/run-security-checks.py", "--mode", "smoke"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_run_security_checks_writes_report(tmp_path: Path) -> None:
    out = tmp_path / "evidence"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/run-security-checks.py",
            "--mode",
            "smoke",
            "--evidence-pack",
            str(out),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    report = out / "security_report.json"
    assert report.exists()
    data = json.loads(report.read_text())
    assert "controls" in data
    assert any(c["control_id"] == "SEC-PII-001" for c in data["controls"])
