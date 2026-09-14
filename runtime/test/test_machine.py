"""
runtime/test/test_machine.py — machine state, the bypass policy and the operator
commands behind `agentsmith` (runtime/machine/, .agent-rfc/designs/agentsmith-cli.md).

Everything here was a shell function in ~/.zshrc, untestable without carving it
out of the installer. The state directory is isolated per test (the conftest
isolates the session; these point it somewhere they can inspect), and git's
global config is redirected with GIT_CONFIG_GLOBAL so `mode` cannot touch the
developer's.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import subprocess
from pathlib import Path

import pytest

from runtime.llm_gateway import _active_profile_name
from runtime.machine import ops, policy, state
from runtime.machine.upgrade import upgrade
from runtime.otlp import resolve_otlp_endpoint

REPO = Path(__file__).resolve().parents[2]
CATALOG_DOC = {
    "default_profile": "local",
    "catalog": {"qwen2.5": {"provider": "ollama"}},
    "profiles": {"local": {"architect": "qwen2.5"}, "hybrid": {"architect": "qwen2.5"}},
}


@pytest.fixture
def machine(tmp_path, monkeypatch):
    """A fake HOME with its own state dir and git global config."""
    home = tmp_path / "home"
    (home / ".agent-framework").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENTSMITH_STATE_DIR", str(home / ".agent-framework" / "state"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    for var in ("AI_STACK_MODE", "AGENT_MODEL_PROFILE", "OTEL_EXPORTER_OTLP_ENDPOINT", "AGENT_PHOENIX_ENDPOINT",
                "OPS_PORTAL_URL", "AUDIT_LOG_WRITE_TOKEN", "AI_BREAK_GLASS_TOKEN", "BREAK_GLASS_HMAC_KEY"):
        monkeypatch.delenv(var, raising=False)
    return home


def _git_global_template_dir() -> str:
    cmd = ["git", "config", "--global", "init.templateDir"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def _record_install_mode(mode: str) -> None:
    """What install-ai-stack.sh Step 7 writes: `printf '%s\\n' "$INSTALL_MODE"`."""
    state.state_dir().mkdir(parents=True, exist_ok=True)
    (state.state_dir() / "install-mode").write_text(f"{mode}\n")


# ── state ───────────────────────────────────────────────────────────────────


def test_mode_round_trips_and_garbage_reads_as_unset(machine):
    assert state.read_mode() is None
    state.write_mode("hybrid")
    assert state.read_mode() == "hybrid"
    (state.state_dir() / "mode").write_text("hybird\n")
    assert state.read_mode() is None, "a word we never write must not be trusted"
    with pytest.raises(ValueError):
        state.write_mode("off")


def test_the_state_dir_override_in_the_process_survives_a_hand_built_env(machine, tmp_path, monkeypatch):
    """A caller passing its own env mapping (the OTLP resolver's tests do) must
    not escape the isolation the process set. The process override is somewhere
    other than the default, or this could not tell the two apart."""
    isolated = tmp_path / "isolated-state"
    monkeypatch.setenv("AGENTSMITH_STATE_DIR", str(isolated))
    assert state.state_dir({}) == isolated
    assert state.state_dir({"AGENTSMITH_STATE_DIR": str(tmp_path / "x")}) == tmp_path / "x"
    monkeypatch.delenv("AGENTSMITH_STATE_DIR")
    assert state.state_dir({}) == machine / ".agent-framework" / "state"


def test_install_mode_defaults_to_developer(machine):
    assert state.read_install_mode() == "developer"
    _record_install_mode("enterprise")
    assert state.read_install_mode() == "enterprise"


def test_find_script_returns_exactly_one_copy(machine, tmp_path, monkeypatch):
    installed = machine / ".agent-framework" / "scripts" / "run-evals.py"
    installed.parent.mkdir(parents=True)
    installed.write_text("# machine\n")
    tenant = tmp_path / "tenant"
    (tenant / "scripts").mkdir(parents=True)
    assert state.find_script("run-evals.py", tenant) == installed
    (tenant / "scripts" / "run-evals.py").write_text("# tenant\n")
    assert state.find_script("run-evals.py", tenant) == tenant / "scripts" / "run-evals.py"
    assert state.find_script("nope.py", tenant) is None


def test_a_failing_tenant_script_is_not_re_run_from_the_machine_copy(machine, tmp_path, monkeypatch, capsys):
    """The shell functions ran `python3 scripts/X.py || python3 ~/.agent-framework/scripts/X.py`."""
    installed = machine / ".agent-framework" / "scripts" / "run-evals.py"
    installed.parent.mkdir(parents=True)
    installed.write_text("import sys; print('MACHINE COPY'); sys.exit(0)\n")
    tenant = tmp_path / "tenant"
    (tenant / "scripts").mkdir(parents=True)
    (tenant / "scripts" / "run-evals.py").write_text("import sys; print('TENANT COPY'); sys.exit(3)\n")
    monkeypatch.chdir(tenant)

    rc = ops._run_script("run-evals.py", [], lambda _: None, quiet=False)

    assert rc == 3
    assert "MACHINE COPY" not in capsys.readouterr().out


# ── precedence: the gateway's profile and the OTLP endpoint ─────────────────


def test_profile_precedence_explicit_then_env_then_mode_file_then_default(machine, monkeypatch):
    assert _active_profile_name(CATALOG_DOC) == "local"
    state.write_mode("hybrid")
    assert _active_profile_name(CATALOG_DOC) == "hybrid", "the machine's mode was not read"
    monkeypatch.setenv("AI_STACK_MODE", "local")
    assert _active_profile_name(CATALOG_DOC) == "local", "the environment must outrank the file"
    monkeypatch.setenv("AGENT_MODEL_PROFILE", "hybrid")
    assert _active_profile_name(CATALOG_DOC) == "hybrid"


def test_a_disabled_mode_names_no_profile(machine):
    state.write_mode("disabled")
    assert _active_profile_name(CATALOG_DOC) == "local"


def test_otlp_reads_the_dashboard_endpoint_only_after_the_environment(machine):
    assert resolve_otlp_endpoint(env={}) is None
    state.write_phoenix_endpoint("http://localhost:6006")
    assert resolve_otlp_endpoint(env={}) == "http://localhost:6006/v1/traces"
    assert resolve_otlp_endpoint(env={"AGENT_PHOENIX_ENDPOINT": "http://other:9"}) == "http://other:9/v1/traces"
    state.clear_phoenix_endpoint()
    assert resolve_otlp_endpoint(env={}) is None


# ── policy ──────────────────────────────────────────────────────────────────


def _token(key: str, actor: str, expires: int) -> str:
    payload = f"{actor}:{expires}"
    return payload + "." + hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def test_break_glass_tokens(machine):
    good = _token("k", "alice", 2_000)
    assert policy.validate_break_glass_token(good, "k", now=1_000) == (True, "valid")
    assert policy.validate_break_glass_token(good, "k", now=2_001)[1].endswith("request a new one from IT")
    assert "signature is invalid" in policy.validate_break_glass_token(good, "other", now=1_000)[1]
    assert "malformed" in policy.validate_break_glass_token("no-dot", "k", now=1_000)[1]
    assert "not configured" in policy.validate_break_glass_token(good, "", now=1_000)[1]


def _policy(machine: Path, text: str) -> None:
    (machine / ".agent-framework" / "agenticframework-org.yaml").write_text(text)


def _audit(machine: Path) -> list[dict]:
    log = machine / ".agent-framework" / "local-audit-fallback.log"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def test_no_policy_allows_and_records_nothing(machine):
    assert policy.bypass_decision(env={}).allowed
    assert _audit(machine) == []


def test_a_disabled_policy_refuses_and_records(machine):
    _policy(machine, 'hooks:\n  bypass_policy: disabled\n  break_glass_approvers: ["it@x", "sec@x"]\n')
    decision = policy.bypass_decision(env={"AGENT_OWNER_ID": "dev"})
    assert not decision.allowed and "it@x, sec@x" in decision.message
    [event] = _audit(machine)
    assert event["eventType"] == "hook_bypass" and event["details"] == {"result": "denied", "policy": "disabled"}
    assert event["actorId"] == "dev" and event["reason"] == "ops_portal_not_configured"


@pytest.mark.parametrize(
    ("env", "allowed", "reason"),
    [
        ({}, False, "no_token"),
        ({"AI_BREAK_GLASS_TOKEN": "bad.sig", "BREAK_GLASS_HMAC_KEY": "k"}, False, "invalid_token"),
        ({"AI_BREAK_GLASS_TOKEN": _token("k", "a", 2_000), "BREAK_GLASS_HMAC_KEY": "k"}, True, None),
    ],
)
def test_break_glass_policy(machine, env, allowed, reason):
    _policy(machine, "hooks:\n  bypass_policy: break-glass\n")
    assert policy.bypass_decision(env=env, now=1_000).allowed is allowed
    [event] = _audit(machine)
    assert event["details"].get("reason") == reason
    assert event["details"]["result"] == ("approved" if allowed else "denied")


def test_an_unreadable_policy_refuses(machine):
    """guards-must-be-able-to-fail: a corrupt policy is not the way to get a bypass."""
    _policy(machine, "hooks: [unterminated\n")
    assert not policy.bypass_decision(env={}).allowed


def test_audit_event_types_are_the_ones_the_portal_accepts():
    ts = (REPO / "portal" / "lib" / "auditSignature.ts").read_text(encoding="utf-8")
    block = re.search(r"AUDIT_EVENT_TYPES = \[(.*?)\]", ts, re.S)
    assert block, "AUDIT_EVENT_TYPES not found in portal/lib/auditSignature.ts"
    assert set(policy.AUDIT_EVENT_TYPES) == set(re.findall(r'"([a-z_]+)"', block.group(1)))
    with pytest.raises(ValueError):
        policy.audit_log_event("onprem_deploy_scaffolded", "a", "", {}, env={})


# ── mode ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("install_mode", ["developer", "enterprise"])
def test_mode_writes_the_file_and_touches_git_only_on_a_developer_install(machine, monkeypatch, install_mode):
    monkeypatch.setattr(ops, "check", lambda out=print, env=None: 0)
    _record_install_mode(install_mode)

    assert ops.mode("hybrid", out=lambda _: None) == 0
    assert state.read_mode() == "hybrid"
    expected = str(machine / ".git_templates") if install_mode == "developer" else ""
    assert _git_global_template_dir() == expected

    assert ops.mode("off", out=lambda _: None) == 0
    assert state.read_mode() == "disabled"
    assert _git_global_template_dir() == ""


def test_mode_off_is_refused_by_a_disabled_policy_and_leaves_the_mode_alone(machine, monkeypatch):
    monkeypatch.setattr(ops, "check", lambda out=print, env=None: 0)
    ops.mode("local", out=lambda _: None)
    _policy(machine, "hooks:\n  bypass_policy: disabled\n")
    said: list[str] = []

    assert ops.mode("off", out=said.append) == 1
    assert state.read_mode() == "local"
    assert any("DISABLED" in s for s in said)


# ── scrub / onprem / tenant promote / upgrade default ───────────────────────


def test_scrub_finds_the_generated_files_at_find_maxdepth_and_nothing_else(tmp_path):
    for rel in ("CLAUDE.md", "a/b/.cursorrules", "a/b/c/AGENTS.md", "p/.github/copilot-instructions.md",
                "p/q/r/.github/copilot-instructions.md", "a/.agents/skill.md", "p/.github/workflows/ci.yml"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x")
    found = {p.relative_to(tmp_path).as_posix() for p in ops.scrub_matches(tmp_path)}
    assert found == {"CLAUDE.md", "a/b/.cursorrules", "p/.github/copilot-instructions.md", "a/.agents"}


def test_scrub_without_confirmation_deletes_nothing(tmp_path, monkeypatch):
    (tmp_path / "CLAUDE.md").write_text("x")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert ops.scrub(str(tmp_path), yes=False, out=lambda _: None) == 1
    assert (tmp_path / "CLAUDE.md").exists()
    assert ops.scrub(str(tmp_path), yes=True, out=lambda _: None) == 0
    assert not (tmp_path / "CLAUDE.md").exists()


def test_onprem_scaffold_records_an_event_the_portal_accepts(machine, tmp_path, monkeypatch):
    src = machine / ".agent-framework" / "templates" / "onprem-deploy"
    src.mkdir(parents=True)
    (src / "README.md").write_text("x")
    repo = tmp_path / "tenant"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.chdir(repo)

    assert ops.onprem_scaffold(out=lambda _: None) == 0
    assert (repo / "deploy" / "onprem" / "README.md").is_file()
    [event] = _audit(machine)
    assert event["eventType"] == "config_change" and event["details"] == {"action": "onprem_deploy_scaffolded"}


def test_tenant_promote_compares_the_parsed_quoted_id(tmp_path, monkeypatch):
    """`tenant init` writes `id: "acme"`; the shell function compared the raw text."""
    (tmp_path / ".agenticframework").mkdir()
    (tmp_path / ".agenticframework" / "tenant.yaml").write_text('tenant:\n  id: "acme"\n')
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(ops, "_run_script", lambda name, args, out, quiet=False: calls.append(args) or 1)

    assert ops.tenant_promote("acme-sandbox", "staging", "production", out=lambda _: None) == 1
    assert calls == [], "a mismatched id reached the eval gate"
    assert ops.tenant_promote("acme", "staging", "production", out=lambda _: None) == 1
    assert calls == [["--fail-below", "0.75"]]
    assert ops.tenant_promote("acme", "dev", "production", out=lambda _: None) == 1


def test_upgrade_without_to_declares_the_installed_release_not_1_1_0(monkeypatch):
    """The shell function defaulted to ${FRAMEWORK_VERSION:-1.1.0}, and the
    profile never set FRAMEWORK_VERSION."""
    from runtime import cli

    seen = {}
    def fake_upgrade(repo, version, **_):
        seen["v"] = version
        return 0

    monkeypatch.setattr("runtime.machine.upgrade.upgrade", fake_upgrade)
    cli.main(["upgrade"])
    assert seen["v"] == cli._default_framework_version() != "1.1.0"


def test_upgrade_refuses_outside_a_tenant(tmp_path):
    assert upgrade(tmp_path, "9.9.9", out=lambda _: None, home=tmp_path) == 1


def test_tenant_init_records_tenant_created_once(machine, tmp_path, monkeypatch):
    """OPERATIONS.md and the portal's audit route name `agentsmith tenant init →
    tenant_created`; nothing wrote it after the scaffold left the shell profile."""
    from runtime import cli

    repo = tmp_path / "tenant"
    repo.mkdir()
    assert cli.main(["tenant", "init", "acme", "--root", str(repo)]) == 0
    assert cli.main(["tenant", "init", "acme", "--root", str(repo)]) == 0  # nothing new written
    events = [e for e in _audit(machine) if e["eventType"] == "tenant_created"]
    assert len(events) == 1 and events[0]["tenantId"] == "acme"


@pytest.mark.parametrize(
    ("policy_text", "expected"), [(None, "muted"), ("hooks:\n  bypass_policy: disabled\n", "org policy decides")]
)
def test_status_does_not_call_hooks_muted_when_a_policy_decides(machine, monkeypatch, policy_text, expected):
    monkeypatch.setenv("DISABLE_AI_STACK", "true")
    monkeypatch.setattr(ops, "judge_model", lambda: "j")
    monkeypatch.setattr(ops, "_online", lambda: True)
    if policy_text:
        _policy(machine, policy_text)
    said: list[str] = []
    ops.status(out=said.append)
    [hooks] = [line for line in said if line.strip().startswith("Hooks:")]
    assert expected in hooks
    assert _audit(machine) == [], "status must not record a bypass attempt"


def test_an_unknown_bypass_policy_value_refuses(machine):
    """guards-must-be-able-to-fail: a typo'd policy (`disable`) read as "no restriction"."""
    _policy(machine, "hooks:\n  bypass_policy: disable\n")
    assert not policy.bypass_decision(env={}).allowed
    _policy(machine, "hooks:\n  version: '1.0.0'\n")
    assert policy.bypass_decision(env={}).allowed, "a policy with no bypass_policy restricts nothing"


def test_doctor_forwards_verify_system_flags(tmp_path, monkeypatch, capfd):
    """`agentsmith doctor --check-kg` failed with "unrecognized arguments"."""
    from runtime import cli

    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "verify_system.py").write_text("import sys; print('ARGS', sys.argv[1:])\n")
    monkeypatch.chdir(tmp_path)

    assert cli.main(["doctor", "--check-kg", "--check-hooks"]) == 0
    assert "ARGS ['--check-kg', '--check-hooks']" in capfd.readouterr().out
    with pytest.raises(SystemExit):
        cli.main(["status", "--bogus"])


def test_dashboard_stop_does_not_signal_a_reused_pid(machine, monkeypatch):
    """A stale pid file naming some other process must not get its group killed."""
    import os

    pid_file = state.state_dir() / "phoenix.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(f"{os.getpid()}\n")  # this test process: alive, and not Phoenix
    killed = []
    monkeypatch.setattr(ops.os, "killpg", lambda pid, sig: killed.append(pid))
    monkeypatch.setattr(ops.shutil, "which", lambda name: None if name == "docker" else f"/usr/bin/{name}")
    real_run = subprocess.run
    monkeypatch.setattr(ops.subprocess, "run", lambda cmd, **kw: real_run(cmd, **kw) if cmd[0] == "ps"
                        else subprocess.CompletedProcess(cmd, 0, "", ""))

    assert ops.dashboard_stop(out=lambda _: None) == 0
    assert killed == [] and not pid_file.exists()
