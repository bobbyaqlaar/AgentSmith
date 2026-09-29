"""
scripts/test/test_fail_closed_declared.py — every adapter that declares
`fail_closed` shows the mechanism that makes it true.

`Adapter.fail_closed` says whether the EDIT GATE refuses an edit when the gate
cannot run. Before 2026-09-29 it was declared for all seven adapters, mirrored
into templates/governance.json, and read by nothing — and its values encoded a
different question ("does this IDE's config need a failClosed key?"), so for
`claude`, the IDE this repository runs, the registry reported the opposite of the
truth (.agent-rfc/designs/fail-closed-has-a-reader.md).

No single line of production code can read it, because the three IDEs that fail
closed do it three different ways — a vendor config key, a shell fallback, and a
protocol rule. This is the reader: each declaration is checked against its own
mechanism, and each adapter that declares `false` is checked for not having one,
so adding a mechanism without updating the registry fails here.
"""

from __future__ import annotations

import json
import sys

from test_process_gate import REPO

sys.path.insert(0, str(REPO / "scripts"))

import gate_ides as gi

LAUNCHER = (REPO / ".githooks" / "process-gate").read_text(encoding="utf-8")
PROTOCOL = (REPO / "contract" / "gate" / "v1" / "protocol.md").read_text(encoding="utf-8")


def test_the_registry_and_the_adapters_agree():
    """governance.json mirrors ADAPTERS. If these drift, everything below is
    checking one of two disagreeing sources."""
    registry = json.loads((REPO / "templates" / "governance.json").read_text(encoding="utf-8"))
    declared = {i["id"]: i["fail_closed"] for i in registry["ides"]}
    for name, adapter in gi.ADAPTERS.items():
        if name in declared:
            assert declared[name] == adapter.fail_closed, (
                f"{name}: governance.json says {declared[name]}, ADAPTERS says {adapter.fail_closed}"
            )
    assert declared, "no ides in the registry — this test would pass by checking nothing"


def test_cursor_fail_closed_reaches_its_generated_config():
    """Cursor's mechanism is its vendor's `failClosed` key. It used to be a
    hardcoded True beside a registry field nothing read; the config must now
    follow the registry."""
    config = gi.render_config("cursor")
    keys = [hook.get("failClosed") for name in ("preToolUse", "beforeShellExecution") for hook in config["hooks"][name]]
    assert keys, "no deny-capable Cursor hooks found — the sweep found nothing to check"
    assert all(k is gi.ADAPTERS["cursor"].fail_closed for k in keys), (
        f"generated config says {keys}, registry says {gi.ADAPTERS['cursor'].fail_closed}"
    )


def test_claude_fail_closed_is_the_launchers_deny_fallback():
    """Claude has no config key for this. Its mechanism is .githooks/process-gate
    printing a deny when no interpreter can run the gate."""
    denies = '"permissionDecision":"deny"' in LAUNCHER and "pre-edit" in LAUNCHER
    assert denies is gi.ADAPTERS["claude"].fail_closed, (
        f"claude declares fail_closed={gi.ADAPTERS['claude'].fail_closed} but the launcher's deny fallback is {denies}"
    )


def test_the_neutral_profile_fail_closed_is_the_contracts_fall_through():
    """A provider that cannot answer falls through to the framework's own gate,
    which denies — so the contract, not a config, is what makes this true."""
    assert "exit 3" in PROTOCOL, "the contract no longer states the cannot-run code"
    assert gi.ADAPTERS[gi.NEUTRAL].fail_closed, (
        "the neutral profile must fail closed: contract/gate/v1 falls through to the framework gate"
    )


def test_the_generator_never_hardcodes_fail_closed():
    """The regression this slice exists to prevent: a `failClosed` literal beside
    a registry field nothing reads.

    The other direction — an IDE declaring fail_closed=False while emitting the
    key — cannot be checked today: all four fail-open adapters (antigravity,
    copilot, gemini, codex) have no verified config schema, so `render_config`
    refuses to generate one and there is no output to inspect. An earlier version
    of this test tried it and said so itself. Asserted as a source rule instead,
    which holds whether or not those schemas ever land."""
    import ast

    source = (REPO / "scripts" / "gate_ides.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == "render_config")

    found = 0
    for node in ast.walk(fn):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=True):
            if isinstance(key, ast.Constant) and key.value == "failClosed":
                found += 1
                rendered = ast.unparse(value)
                assert "fail_closed" in rendered, (
                    f"render_config hardcodes failClosed={rendered} — it must read the "
                    "registry, or the declaration in governance.json means nothing"
                )
    assert found, "no failClosed key found in render_config — this test checked nothing"
