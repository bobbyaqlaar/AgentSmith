"""
runtime/test/test_cli.py — the tests the shell functions could never have.

`ai-tenant-init` was a zsh function that `install-ai-stack.sh` appended to
~/.zshrc, so it existed only after an interactive install on macOS or Linux.
Nothing tested it, nothing could: there was no importable artifact, and the
scaffold it wrote lived in two places that drifted apart twice in one day.

These assert on the scaffold as a value.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from runtime.cli import (  # noqa: E402
    ISOLATIONS,
    STACKS,
    build_parser,
    init_tenant,
    main,
    tenant_yaml,
)


# ── the scaffold as data ─────────────────────────────────────────────────────


def test_scaffold_parses_and_carries_the_declared_id():
    doc = yaml.safe_load(tenant_yaml("acme"))
    assert doc["tenant"]["id"] == "acme"
    assert doc["workflow"]["task_queue"] == "acme"


def test_every_scaffolded_key_is_one_the_runtime_reads():
    """The entry criterion, learned from shipping five keys that nothing read.
    `environments:` with phoenix_namespace / eval_fail_below / redaction_profile
    used to be here; two of the three were actively misleading."""
    doc = yaml.safe_load(tenant_yaml("acme"))
    assert set(doc) == {
        "tenant", "framework", "security", "moderation", "budget", "workflow", "delivery"
    }
    assert "environments" not in doc


def test_modes_are_strings_not_booleans():
    """YAML 1.1 parses a bare `off` as False, which matches no mode name. Every
    mode in the scaffold is quoted; this is what proves it stayed that way."""
    doc = yaml.safe_load(tenant_yaml("acme"))
    assert doc["security"]["prompt_guard"] == "default"
    assert doc["moderation"]["mode"] == "optional"
    assert isinstance(doc["security"]["prompt_guard"], str)
    # And the flags really are booleans, not the strings "false".
    assert doc["security"]["tool_allowlist_strict"] is False
    assert doc["security"]["ip_redaction"] is False


def test_env_overrides_ships_commented_out():
    """Empty by default: an ambient export must not silently relax a declared
    posture. The line is present as documentation of the escape hatch."""
    text = tenant_yaml("acme")
    doc = yaml.safe_load(text)
    assert "env_overrides" not in doc
    assert "# env_overrides:" in text


@pytest.mark.parametrize("isolation", ISOLATIONS)
def test_isolation_round_trips(isolation):
    doc = yaml.safe_load(tenant_yaml("acme", isolation=isolation))
    assert doc["tenant"]["isolation"] == isolation


# ── init_tenant ──────────────────────────────────────────────────────────────


def test_init_writes_the_config(tmp_path: Path):
    written = init_tenant("acme", tmp_path)
    assert ".agenticframework/tenant.yaml" in written
    doc = yaml.safe_load((tmp_path / ".agenticframework" / "tenant.yaml").read_text())
    assert doc["tenant"]["id"] == "acme"


def test_init_never_overwrites_without_force(tmp_path: Path):
    """A tenant.yaml is hand-edited after generation. Silently replacing it
    would discard a declared security posture."""
    init_tenant("acme", tmp_path)
    cfg = tmp_path / ".agenticframework" / "tenant.yaml"
    cfg.write_text("tenant:\n  id: edited-by-hand\n")

    written = init_tenant("acme", tmp_path)
    assert ".agenticframework/tenant.yaml" not in written
    assert "edited-by-hand" in cfg.read_text()

    init_tenant("acme", tmp_path, force=True)
    assert "edited-by-hand" not in cfg.read_text()


def test_ci_callees_ship_with_their_caller(tmp_path: Path):
    """A workflow referenced by `uses:` and not provisioned makes GitHub reject
    the WHOLE caller as invalid, not just the missing job — which is how every
    Python/FastAPI tenant was once scaffolded with unusable CI."""
    from runtime.cli import WORKFLOWS, _templates_dir

    if _templates_dir() is None:
        pytest.skip("no workflow-templates available")

    init_tenant("acme", tmp_path, stack="python-fastapi")
    caller = (tmp_path / ".github" / "workflows" / "ci-python-fastapi.yml").read_text()
    for name in WORKFLOWS:
        if f"./.github/workflows/{name}" in caller:
            assert (tmp_path / ".github" / "workflows" / name).is_file(), (
                f"ci-python-fastapi.yml uses {name} but init did not provision it"
            )


def test_unknown_stack_and_isolation_are_refused(tmp_path: Path):
    with pytest.raises(ValueError, match="stack"):
        init_tenant("acme", tmp_path, stack="cobol")
    with pytest.raises(ValueError, match="isolation"):
        init_tenant("acme", tmp_path, isolation="whatever")


# ── the command surface ──────────────────────────────────────────────────────


def test_parser_covers_the_shell_functions_being_replaced():
    parser = build_parser()
    for argv in (
        ["tenant", "init", "acme"],
        ["tenant", "init", "acme", "--stack", "go", "--isolation", "dedicated"],
        ["shellenv", "--mode", "hybrid"],
        ["version"],
        ["doctor"],
    ):
        assert parser.parse_args(argv) is not None


def test_shellenv_emits_evaluable_exports(capsys):
    """The one thing a child process cannot do for its parent. Five generated
    lines instead of sixty-one hand-maintained ones in a profile."""
    assert main(["shellenv", "--mode", "local"]) == 0
    out = capsys.readouterr().out
    assert 'export AI_STACK_MODE="local"' in out
    for line in out.strip().splitlines():
        assert line.startswith("export "), f"not evaluable: {line!r}"


def test_main_returns_two_on_a_bad_argument(tmp_path: Path, capsys):
    """argparse rejects an unknown --stack itself; this covers the ValueError
    path for a caller that reaches init_tenant directly."""
    from runtime.cli import _cmd_tenant_init
    import argparse as _argparse

    args = _argparse.Namespace(
        tenant_id="acme", root=str(tmp_path), stack="cobol",
        isolation="shared", force=False,
    )
    assert _cmd_tenant_init(args) == 2
    assert "stack" in capsys.readouterr().err


def test_stacks_match_the_shipped_ci_templates():
    """Every stack the CLI offers must have a template, or `tenant init` writes
    a repo whose CI does not exist."""
    from runtime.cli import _templates_dir

    templates = _templates_dir()
    if templates is None:
        pytest.skip("no workflow-templates available")
    for stack in STACKS:
        assert (templates / f"ci-{stack}.yml").is_file(), f"no template for {stack}"
