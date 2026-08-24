"""
runtime/test/test_config.py — the two channels the runtime reads configuration
from, and the precedence between them.

Both existed and neither reached the runtime. `.env` was loaded only by
`scripts/`, so a worker outside an already-exported shell ran on defaults —
which is why the detached eval script opens with `set -a; . ./.env`. And
tenant.yaml declared `budget.monthly_usd_cap`, `workflow.task_queue` and
`tenant.owner` that nothing read: KYC declared a $5 cap while the gateway
enforced $150 whenever AGENT_MONTHLY_USD_CAP was unset, which it is in
production because .env is not deployed to Cloud Run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from runtime.config import (  # noqa: E402
    config_get,
    load_env_file,
    resolve,
    tenant_config,
)


@pytest.fixture
def repo(tmp_path: Path):
    """A scaffolded repo root: .agenticframework/tenant.yaml plus optional .env."""
    (tmp_path / ".agenticframework").mkdir()

    def _build(declared: dict | None = None, dotenv: str | None = None) -> Path:
        (tmp_path / ".agenticframework" / "tenant.yaml").write_text(
            yaml.dump(declared or {})
        )
        if dotenv is not None:
            (tmp_path / ".env").write_text(dotenv)
        tenant_config(tmp_path, refresh=True)
        return tmp_path

    return _build


# ── .env loading ─────────────────────────────────────────────────────────────


def test_loads_env_file(repo, monkeypatch):
    root = repo(dotenv="FOO_ONE=alpha\nFOO_TWO=beta\n")
    monkeypatch.delenv("FOO_ONE", raising=False)
    monkeypatch.delenv("FOO_TWO", raising=False)
    import os

    assert load_env_file(root) == 2
    assert os.environ["FOO_ONE"] == "alpha"


def test_never_overwrites_the_environment(repo, monkeypatch):
    """A value already set came from the deploy platform or the operator's
    shell and outranks a file in the checkout — so calling this in production
    cannot change what a container was configured with."""
    root = repo(dotenv="FOO_SET=from-file\n")
    monkeypatch.setenv("FOO_SET", "from-environment")
    import os

    assert load_env_file(root) == 0
    assert os.environ["FOO_SET"] == "from-environment"


def test_absent_env_file_is_not_an_error(repo):
    assert load_env_file(repo()) == 0


def test_parses_quotes_comments_and_export(repo, monkeypatch):
    root = repo(dotenv='export FOO_Q="quoted value"\nFOO_C=bare # trailing\n')
    for key in ("FOO_Q", "FOO_C"):
        monkeypatch.delenv(key, raising=False)
    import os

    load_env_file(root)
    assert os.environ["FOO_Q"] == "quoted value"
    assert os.environ["FOO_C"] == "bare", "an inline comment is not part of the value"


# ── tenant.yaml ──────────────────────────────────────────────────────────────


def test_dotted_lookup(repo):
    root = repo({"budget": {"monthly_usd_cap": 5}, "tenant": {"id": "acme"}})
    assert config_get("budget.monthly_usd_cap", root) == 5
    assert config_get("tenant.id", root) == "acme"
    assert config_get("budget.nope", root) is None
    assert config_get("nope.nope", root) is None


# ── precedence ───────────────────────────────────────────────────────────────


def test_precedence_explicit_then_env_then_declaration(repo, monkeypatch):
    root = repo({"budget": {"monthly_usd_cap": 5}})
    monkeypatch.setenv("CAP_VAR", "50")
    assert resolve("budget.monthly_usd_cap", explicit=1, env_var="CAP_VAR",
                   default=150.0, cast=float, root=root) == 1
    assert resolve("budget.monthly_usd_cap", env_var="CAP_VAR",
                   default=150.0, cast=float, root=root) == 50.0
    monkeypatch.delenv("CAP_VAR")
    assert resolve("budget.monthly_usd_cap", env_var="CAP_VAR",
                   default=150.0, cast=float, root=root) == 5.0


def test_the_regression_a_declared_cap_beats_the_code_default(repo, monkeypatch):
    """The live gap this closes. tenant.yaml said $5, the gateway enforced $150
    whenever the env var was unset — and it is unset in production, because
    .env is not deployed. A 30x breach resting on somebody remembering
    --set-env-vars."""
    root = repo({"budget": {"monthly_usd_cap": 5}})
    monkeypatch.delenv("AGENT_MONTHLY_USD_CAP", raising=False)
    cap = resolve("budget.monthly_usd_cap", env_var="AGENT_MONTHLY_USD_CAP",
                  default=150.0, cast=float, root=root)
    assert cap == 5.0, "the declared policy must win over the code default"


def test_falls_back_to_the_default_when_nothing_declares_it(repo, monkeypatch):
    monkeypatch.delenv("CAP_VAR", raising=False)
    assert resolve("budget.monthly_usd_cap", env_var="CAP_VAR", default=150.0,
                   cast=float, root=repo()) == 150.0


def test_no_default_means_raise_not_invent(repo, monkeypatch):
    """For anything an auditor would read as a control, an unresolved value
    must stop the process rather than become a plausible number."""
    monkeypatch.delenv("CAP_VAR", raising=False)
    with pytest.raises(LookupError) as exc:
        resolve("budget.monthly_usd_cap", env_var="CAP_VAR", root=repo())
    assert "tenant.yaml" in str(exc.value)


def test_a_malformed_override_raises_rather_than_falling_through(repo, monkeypatch):
    """Falling back to the declared value here would silently ignore what the
    operator actually asked for."""
    root = repo({"budget": {"monthly_usd_cap": 5}})
    monkeypatch.setenv("CAP_VAR", "not-a-number")
    with pytest.raises(ValueError) as exc:
        resolve("budget.monthly_usd_cap", env_var="CAP_VAR", default=150.0,
                cast=float, root=root)
    assert "CAP_VAR" in str(exc.value)


def test_a_blank_override_is_not_an_override(repo, monkeypatch):
    root = repo({"budget": {"monthly_usd_cap": 5}})
    monkeypatch.setenv("CAP_VAR", "   ")
    assert resolve("budget.monthly_usd_cap", env_var="CAP_VAR", default=150.0,
                   cast=float, root=root) == 5.0


# ── Security posture: declared in tenant.yaml, overridden by env ─────────────


@pytest.mark.parametrize(
    "dotted,env_var,declared,expected",
    [
        ("security.prompt_guard", "PROMPT_GUARD", "strict", "strict"),
        ("security.input_guardrail", "INPUT_GUARDRAIL", "off", "off"),
        ("moderation.mode", "MODERATION_HOOK", "required", "required"),
    ],
)
def test_posture_is_readable_from_the_declaration(
    repo, monkeypatch, dotted, env_var, declared, expected
):
    """These were reachable only through environment variables, so a tenant's
    security posture lived nowhere reviewable — not in the repo, not in a diff,
    not in anything an auditor could be handed."""
    section, key = dotted.split(".")
    root = repo({section: {key: declared}})
    monkeypatch.delenv(env_var, raising=False)
    assert resolve(dotted, env_var=env_var, default="", root=root) == expected


def test_env_still_overrides_the_posture(repo, monkeypatch):
    root = repo({"security": {"prompt_guard": "off"}})
    monkeypatch.setenv("PROMPT_GUARD", "strict")
    assert resolve("security.prompt_guard", env_var="PROMPT_GUARD",
                   default="", root=root) == "strict"


def test_a_declared_false_flag_is_honoured_not_treated_as_absent(repo, monkeypatch):
    """`False` is a declared value; `None` is an absent one. Collapsing them
    would make `tool_allowlist_strict: false` fall through to the default,
    which for a deny-by-default guard is the wrong direction to guess."""
    from runtime.config import as_bool

    root = repo({"security": {"tool_allowlist_strict": False}})
    monkeypatch.delenv("TOOL_ALLOWLIST_STRICT", raising=False)
    assert resolve("security.tool_allowlist_strict",
                   env_var="TOOL_ALLOWLIST_STRICT", default=True, root=root) is False
    assert as_bool(False) is False


def test_yaml_bare_off_would_have_been_a_boolean(repo, monkeypatch):
    """Why every mode in the scaffold is quoted. YAML 1.1 parses a bare `off`
    as the boolean false, so `prompt_guard: off` would resolve to False and
    match no mode name at all."""
    import yaml as _yaml

    assert _yaml.safe_load("mode: off")["mode"] is False
    assert _yaml.safe_load('mode: "off"')["mode"] == "off"


def test_as_bool_reads_both_channels(monkeypatch):
    from runtime.config import as_bool

    assert as_bool(True) is True and as_bool(False) is False       # yaml
    assert as_bool("1") and as_bool("true") and as_bool("YES")     # env
    assert not as_bool("0") and not as_bool("") and not as_bool("maybe")
