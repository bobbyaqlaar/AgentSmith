"""Small fixes before going public: .agent-rfc/designs/launch-small-fixes.md.

The portal and the React template have no DOM test lane, so their two rows read the
source. They hold the shape of the fix, not the behaviour in a browser.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_no_compose_image_floats():
    images = re.findall(r"^\s*image:\s*(\S+)", (REPO / "docker-compose.yml").read_text(encoding="utf-8"), re.M)
    assert images and [i for i in images if i.endswith(":latest") or ":" not in i] == []
    assert any(re.fullmatch(r"arizephoenix/phoenix:version-[\d.]+@sha256:[0-9a-f]{64}", i) for i in images), images


def test_discard_asks_before_it_acts():
    text = (REPO / "portal" / "components" / "DlqEntryCard.tsx").read_text(encoding="utf-8")
    body = text[text.index("async function discard()"):]
    assert body.index("window.confirm(") < body.index("/discard`"), "the request goes out before the question"


def test_the_widget_names_no_host_that_does_not_exist():
    tracked = subprocess.run(["git", "-C", str(REPO), "ls-files", "templates/in-app-widget"],
                             capture_output=True, text=True, check=True).stdout.split()
    assert tracked
    assert [p for p in tracked if "cdn.agenticframework.io" in (REPO / p).read_text(errors="replace")] == []
    component = (REPO / "templates/in-app-widget/react/AgentStatus.tsx").read_text(encoding="utf-8")
    assert "  widgetScriptUrl: string;" in component and "  widgetScriptUrl,\n" in component


def test_the_compat_wrappers_are_gone():
    assert not (REPO / "templates" / "shell" / "ai-compat.sh").exists()
    assert "ai-compat" not in (REPO / "install-ai-stack.sh").read_text(encoding="utf-8")
