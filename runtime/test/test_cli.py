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
import argparse
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from runtime import cli
from runtime.cli import (
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
    # `workspace` is written only when `--ide` declared one, and it is read by
    # runtime.config.chosen_ides — so the criterion holds in both shapes
    # (runtime/test/test_chosen_ides.py).
    assert set(yaml.safe_load(tenant_yaml("acme", ides=["cursor"]))) == set(doc) | {"workspace"}


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


@pytest.mark.parametrize("stack", STACKS)
def test_composite_actions_ship_with_the_workflows_that_use_them(tmp_path: Path, monkeypatch, stack):
    """`uses: ./.github/actions/<name>` resolves in the tenant's own repo. The
    hook copied the actions; `tenant init` did not, so every CD workflow it
    wrote failed at its first step. HOME is emptied so the checkout's own
    actions are used, not whatever an older install left in ~/.agent-framework."""
    import re as _re

    monkeypatch.setenv("HOME", str(tmp_path / "empty-home"))
    repo = tmp_path / "repo"
    repo.mkdir()
    init_tenant("acme", repo, stack=stack)

    used = set()
    for wf in (repo / ".github" / "workflows").glob("*.yml"):
        used |= set(_re.findall(r"uses:\s*\./\.github/actions/([\w.-]+)", wf.read_text()))
    assert used, "expected the CD workflows to reference composite actions"
    missing = {a for a in used if not (repo / ".github" / "actions" / a / "action.yml").is_file()}
    assert not missing, f"workflows use actions tenant init never wrote: {missing}"
    assert "{{TENANT_ID}}" not in (repo / ".github" / "workflows" / "cd-production.yml").read_text()


def test_unknown_stack_and_isolation_are_refused(tmp_path: Path):
    with pytest.raises(ValueError, match="stack"):
        init_tenant("acme", tmp_path, stack="cobol")
    with pytest.raises(ValueError, match="isolation"):
        init_tenant("acme", tmp_path, isolation="whatever")


# ── the command surface ──────────────────────────────────────────────────────


# Every shell function the installer used to write, and the command that replaced it.
SHELL_FUNCTIONS_REPLACED = {
    "ai-mode-local": ["mode", "local"],
    "ai-mode-hybrid": ["mode", "hybrid"],
    "ai-stack-off": ["mode", "off"],
    "ai-stack-check": ["check"],
    "ai-stack-status": ["status"],
    "ai-stack-judge-model": ["models", "--judge"],
    "ai-stack-required-models": ["models", "--ollama"],
    "ai-dashboard-start": ["dashboard", "start"],
    "ai-dashboard-stop": ["dashboard", "stop"],
    "ai-test-evals": ["evals"],
    "ai-stack-promote": ["promote", "case-1", "query", "output"],
    "ai-tenant-init": ["tenant", "init", "acme"],
    "ai-tenant-promote": ["tenant", "promote", "acme", "--from", "staging", "--to", "production"],
    "ai-onprem-deploy-scaffold": ["tenant", "onprem-scaffold"],
    "ai-stack-upgrade": ["upgrade", "--to", "1.3.0"],
    "ai-stack-scrub": ["scrub", "some/dir", "--yes"],
    "ai-stack-uninstall": ["uninstall", "--yes"],
}


def test_parser_covers_the_shell_functions_it_replaced():
    parser = build_parser()
    for function, argv in SHELL_FUNCTIONS_REPLACED.items():
        args = parser.parse_args(argv)
        assert callable(getattr(args, "func", None)), f"{function} → agentsmith {' '.join(argv)} dispatches to nothing"
    for argv in (["tenant", "init", "acme", "--stack", "go", "--isolation", "dedicated"], ["version"],
                 ["doctor"], ["purge-idempotency"], ["hooks", "bypass-check"], ["mode"]):
        assert parser.parse_args(argv) is not None


def _leaf_parsers(parser: argparse.ArgumentParser, path=()):
    subparsers = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not subparsers:
        yield path, parser
        return
    for action in subparsers:
        for name, child in action.choices.items():
            yield from _leaf_parsers(child, (*path, name))


def test_every_subcommand_dispatches_somewhere():
    """A subcommand without `set_defaults(func=...)` parses fine and then does
    nothing — argparse does not mind, and `main` would raise AttributeError at
    the moment someone runs it. Registering the parser and forgetting the
    handler is one line apart in build_parser."""
    leaves = list(_leaf_parsers(build_parser()))
    assert len(leaves) >= 15, f"expected the full command set, found {[p for p, _ in leaves]}"
    for path, leaf in leaves:
        assert callable(leaf.get_default("func")), f"`agentsmith {' '.join(path)}` dispatches to nothing"


def test_shellenv_is_gone():
    """It printed `export AI_STACK_MODE=…` for a profile to eval, and an exported
    mode outranks the machine's mode file for everything that shell starts."""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["shellenv"])


def test_main_returns_two_on_a_bad_argument(tmp_path: Path, capsys):
    """argparse rejects an unknown --stack itself; this covers the ValueError
    path for a caller reaching init_tenant with one anyway.

    Built through the parser and then mutated, NOT hand-constructed as a
    Namespace: a hand-built one duplicates the parser's argument list and
    breaks the moment an argument is added — which it did, the first time one
    was.
    """
    from runtime.cli import _cmd_tenant_init

    args = build_parser().parse_args(["tenant", "init", "acme", "--root", str(tmp_path)])
    args.stack = "cobol"
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


# ── the framework-root guard ─────────────────────────────────────────────────


def test_refuses_to_scaffold_into_the_framework_itself():
    """Written after doing exactly this by accident: `tenant init` defaults
    --root to cwd, and running it from the wrong terminal is a two-second
    mistake. Twelve tests went red because the stray tenant.yaml declared a
    security posture that outranked the environment they set."""
    from runtime.cli import FrameworkRootError, init_tenant

    framework = Path(__file__).resolve().parent.parent.parent
    with pytest.raises(FrameworkRootError) as exc:
        init_tenant("acme", framework)
    assert "agentsmith-runtime" in str(exc.value)
    assert "--allow-framework-root" in str(exc.value), "the error must name its own override"


def test_force_does_not_bypass_the_guard(tmp_path: Path):
    """`force` means "replace files I already own". Writing into the wrong
    repository is a different question, and overloading one flag onto both is
    how a guard gets disabled by someone solving an unrelated problem."""
    from runtime.cli import FrameworkRootError, init_tenant

    framework = Path(__file__).resolve().parent.parent.parent
    with pytest.raises(FrameworkRootError):
        init_tenant("acme", framework, force=True)


def test_the_override_works_when_meant(tmp_path: Path):
    from runtime.cli import init_tenant

    (tmp_path / "install-ai-stack.sh").write_text("#!/bin/sh\n")
    (tmp_path / "workflow-templates").mkdir()
    written = init_tenant("acme", tmp_path, allow_framework_root=True)
    assert ".agenticframework/tenant.yaml" in written


def test_two_markers_are_required_not_one(tmp_path: Path):
    """A single marker would refuse in a repo that merely vendored the
    installer, and a guard that fires on legitimate work is one people learn to
    bypass."""
    from runtime.cli import init_tenant, looks_like_framework

    (tmp_path / "install-ai-stack.sh").write_text("#!/bin/sh\n")
    assert looks_like_framework(tmp_path) is None, "one marker must not be enough"
    assert ".agenticframework/tenant.yaml" in init_tenant("acme", tmp_path)

    (tmp_path / "workflow-templates").mkdir()
    assert looks_like_framework(tmp_path) is not None, "two markers must trip it"


def test_the_package_name_marker_reads_the_file_not_the_filename(tmp_path: Path):
    """A tenant has a pyproject.toml too — it is the declared package name that
    identifies the framework, and that string exists in exactly one project."""
    from runtime.cli import looks_like_framework

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "some-tenant"\n')
    (tmp_path / "workflow-templates").mkdir()
    assert looks_like_framework(tmp_path) is None

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "agentsmith-runtime"\n')
    assert looks_like_framework(tmp_path) is not None


def test_cli_exit_code_is_distinct_for_a_refusal(capsys):
    """3, not 1 or 2 — a script wrapping this can tell "wrong directory" from
    "bad argument" without parsing the message."""
    framework = Path(__file__).resolve().parent.parent.parent
    assert main(["tenant", "init", "acme", "--root", str(framework)]) == 3
    assert "refusing to scaffold here" in capsys.readouterr().err


# ── The tenant id has to survive being written and read back ──────────────────


@pytest.mark.parametrize(
    "tenant_id",
    ["acme", "off", "no", "yes", "on", "true", "null", "123", "1.5",
     "kyc-sentinel", "acme.corp", "a_1"],
)
def test_the_scaffolded_id_is_the_id_that_was_asked_for(tenant_id):
    """YAML 1.1 reads bare off/no/yes/on/true as booleans and 123 as an int.

    The id was interpolated unquoted, so `agentsmith tenant init off` wrote
    `id: off`, YAML read False, and runtime/tenancy.py resolved the tenant to
    the string "False" — which then keys the spend ledger, the
    HITL_ENCRYPTION_KEY_<TENANT> variable and every span.

    This file's own docstring already explained the trap and quoted the MODE
    values. The quoting had been applied to the values someone thought about
    rather than to the class of problem.
    """
    import yaml

    document = yaml.safe_load(cli.tenant_yaml(tenant_id))
    assert document["tenant"]["id"] == tenant_id
    assert isinstance(document["tenant"]["id"], str)
    assert document["tenant"]["name"] == tenant_id


def test_the_scaffold_round_trips_through_the_real_resolver(tmp_path, monkeypatch):
    """Not just yaml.safe_load — the function that actually reads this file."""
    import runtime.config as config
    from runtime.tenancy import resolve_tenant_id

    monkeypatch.setattr(config, "_CACHE", {})
    for var in ("AGENT_TENANT_ID", "TENANT_ID"):
        monkeypatch.delenv(var, raising=False)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text(
        cli.tenant_yaml("off"), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    assert resolve_tenant_id() == "off", "the resolver saw a boolean, not the id"


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "a b", "acme\ncorp: x", 'acme"q', "-leading", "a:b", "x" * 65],
)
def test_an_unusable_tenant_id_is_refused_at_creation(bad):
    """The id is written into YAML, resolved back, and spliced into an
    environment variable NAME. Creation is the only moment it is free to
    change, so it is checked there rather than surfacing later as a broken
    config file or an unsettable key variable."""
    with pytest.raises(ValueError, match="tenant id"):
        cli.validate_tenant_id(bad)


def test_a_non_string_id_is_a_clear_error_not_a_typeerror():
    """The isinstance guard is what separates this from a TypeError out of
    re.match. The regex alone rejects "" and "   ", so mutation testing showed
    the guard doing nothing for every case that WAS tested — None is the case
    that needs it.
    """
    for value in (None, 123, ["acme"]):
        with pytest.raises(ValueError, match="non-empty string"):
            cli.validate_tenant_id(value)


def test_the_refusal_explains_the_shape():
    with pytest.raises(ValueError) as exc:
        cli.validate_tenant_id("a b")
    assert "letters, digits" in str(exc.value)
    assert "HITL_ENCRYPTION_KEY" in str(exc.value)


def test_init_refuses_a_bad_id_before_writing_anything(tmp_path):
    """The guard belongs before the first mkdir, not after a partial scaffold."""
    with pytest.raises(ValueError):
        cli.init_tenant("bad id", tmp_path, allow_framework_root=True)
    assert not (tmp_path / ".agenticframework").exists()


# ── The declared framework version ────────────────────────────────────────────


def test_the_scaffold_declares_the_installed_version():
    """It was the literal "1.3.0" in a default argument — a second copy of the
    version number that would drift from pyproject.toml at the next bump, and
    every tenant scaffolded after that would declare a stale release."""
    import yaml

    from runtime.version import SOURCE_SUFFIX, framework_version

    declared = yaml.safe_load(cli.tenant_yaml("acme"))["framework"]["version"]
    running = framework_version()
    expected = (
        running[: -len(SOURCE_SUFFIX)] if running.endswith(SOURCE_SUFFIX) else running
    )
    assert declared == expected


def test_the_declared_version_follows_the_module_not_a_literal(monkeypatch):
    """The assertion that a hardcoded literal cannot pass.

    Comparing the scaffold's version to framework_version() holds just as well
    when the scaffold hardcodes today's number — mutation testing put "1.3.0"
    back and every version test stayed green, because "1.3.0" is what
    framework_version() currently returns. Moving the module's answer is the
    only way to tell the two apart.
    """
    import yaml

    monkeypatch.setattr(cli, "_default_framework_version", lambda: "9.9.9")
    declared = yaml.safe_load(cli.tenant_yaml("acme"))["framework"]["version"]
    assert declared == "9.9.9", "the scaffold is not reading the version, it is a literal"


def test_the_declared_version_carries_no_source_marker(monkeypatch):
    """framework_version() reports `1.3.0+src` from a checkout. That is the
    right answer for "what is running" and the wrong one to write into a
    tenant's config, which declares the RELEASE it targets.

    The marker is set here rather than left to the machine: where AgentSmith
    is installed, framework_version() reads the package metadata and there is
    no marker to strip, so a test relying on the environment passed with the
    strip deleted."""
    import yaml

    import runtime.version

    monkeypatch.setattr(runtime.version, "framework_version", lambda: "1.3.0+src")
    declared = yaml.safe_load(cli.tenant_yaml("acme"))["framework"]["version"]
    assert declared == "1.3.0"


def test_a_released_version_is_declared_unchanged(monkeypatch):
    import yaml

    import runtime.version

    monkeypatch.setattr(runtime.version, "framework_version", lambda: "1.3.0")
    declared = yaml.safe_load(cli.tenant_yaml("acme"))["framework"]["version"]
    assert declared == "1.3.0"


# ── A machine install missing a template (.agent-rfc/designs/installed-architectures.md) ──


@pytest.mark.parametrize("command", ["init", "adopt"])
def test_a_missing_template_is_a_message_not_a_traceback(command, monkeypatch, tmp_path, capsys):
    """`--architecture` reads templates/architectures.yaml, which an install
    that predates it does not have. The error names the file and the fix; it
    reached the user as a traceback until 2026-09-23."""
    missing = FileNotFoundError("templates/architectures.yaml not found in $AGENTSMITH_DIR, "
                                "~/.agent-framework or this checkout — re-run install-ai-stack.sh")
    if command == "init":
        monkeypatch.setattr(cli, "init_tenant", lambda *a, **k: (_ for _ in ()).throw(missing))
        args = argparse.Namespace(tenant_id="acme", root=str(tmp_path), stack="python-fastapi",
                                  isolation="shared", force=False, allow_framework_root=False,
                                  architecture="hexagonal", agentic=False, ide=None)
        code = cli._cmd_tenant_init(args)
    else:
        import runtime.adopt as adopt

        monkeypatch.setattr(adopt, "plan_adoption", lambda *a, **k: (_ for _ in ()).throw(missing))
        args = argparse.Namespace(tenant_id="acme", root=str(tmp_path), stack=None, architecture="hexagonal",
                                  agentic=False, gate=None, framework_ref=None, yes=True)
        code = cli._cmd_tenant_adopt(args)

    assert code == 2
    err = capsys.readouterr().err
    assert "architectures.yaml" in err and "install-ai-stack.sh" in err
    assert "Traceback" not in err


def test_an_empty_framework_never_arms_an_empty_hooks_directory(tmp_path):
    """Found adopting a real tenant from an installed machine: the install
    carried no .githooks/, so `install_gate_hooks` copied nothing, armed
    core.hooksPath anyway, and the tenant had neither the gates nor the
    machine's hooks. Arming is what makes the gates real — it must not happen
    over an empty directory (.agent-rfc/designs/installed-architectures.md)."""
    import subprocess as sp

    framework = tmp_path / "framework"      # no .githooks/ in it
    framework.mkdir()
    root = tmp_path / "repo"
    root.mkdir()
    sp.run(["git", "init", "-q", "-b", "main", "--template=", str(root)], check=True)

    with pytest.raises(FileNotFoundError, match=r"\.githooks"):
        cli.install_gate_hooks(root, framework)

    armed = sp.run(["git", "-C", str(root), "config", "--get", "core.hooksPath"],
                   capture_output=True, text=True, check=False)
    assert armed.stdout.strip() == "", "core.hooksPath was armed with no hooks to run"
