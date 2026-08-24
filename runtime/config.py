"""
runtime/config.py — where configuration reaches the runtime from.

Two channels, one precedence, stated once.

`.env` WAS NEVER LOADED BY THE RUNTIME. `scripts/` loads it (via
`_shared._load_dotenv`); `runtime/` — worker, gateway, tenancy, redactor, dead
letter, idempotency — read `os.environ` directly and loaded nothing. So the
runtime worked locally only because the launching shell happened to have the
values exported, which is why `~/.agentsmith-split_eval.sh` opens with
`set -a; . ./.env; set +a`: a per-script workaround for a gap here. Anything
that forgot the incantation silently got defaults.

`tenant.yaml` DECLARED POLICY NOTHING READ. The scaffold has shipped
`budget.monthly_usd_cap`, `workflow.task_queue`, `tenant.owner` and `tenant.id`
since the beginning and only `moderation.hook` was ever wired. KYC Sentinel
declared a $5 monthly cap while the gateway enforced `AGENT_MONTHLY_USD_CAP`
or, unset, a $150 default — and `.env` isn't deployed to Cloud Run, so in
production the declared cap became the default: a 30x breach resting on
somebody remembering `--set-env-vars`. A declared-but-unenforced control is
worse than an absent one, because it reads as a control in an audit.

PRECEDENCE, everywhere:

    explicit argument  >  environment  >  tenant.yaml  >  documented default

Environment above the file on purpose. The file is the declared policy under
review; the environment is the per-deploy override that lets an operator raise
a cap or repoint a queue without a redeploy. Where a key has no safe default —
`tenant.id` — the last step raises instead (see `tenancy.py`).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

_UNSET = object()

_TRUE = {"1", "true", "yes", "on"}


def as_bool(value: Any) -> bool:
    """Coerce a flag from either channel.

    YAML gives a real bool; the environment gives a string. Unrecognised text
    is False rather than truthy — `TOOL_ALLOWLIST_STRICT=maybe` must not turn a
    deny-by-default guard on by accident, nor off: False is this flag's
    documented default in every case it is used for.
    """
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUE


def repo_root(start: Optional[Path] = None) -> Path:
    """Nearest ancestor holding `.agenticframework/` or `.git/`."""
    cwd = start or Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".agenticframework").is_dir() or (parent / ".git").exists():
            return parent
    return cwd


def _dotenv_value(raw: str) -> str:
    """Strip quotes and a trailing inline comment, matching scripts/_shared."""
    val = raw.strip()
    if val[:1] in {'"', "'"} and val[-1:] == val[:1] and len(val) > 1:
        return val[1:-1]
    # Only an unquoted value can carry an inline comment.
    return val.split(" #", 1)[0].strip()


def load_env_file(root: Optional[Path] = None) -> int:
    """Load repo-root `.env` into `os.environ`. Returns how many keys were set.

    NEVER OVERWRITES. A value already in the environment came from the deploy
    platform or the operator's shell and outranks a file in the checkout — so
    calling this in production, where `.env` is usually absent anyway, cannot
    change what a container was configured with.

    Call it once, early, before anything reads configuration. Deliberately not
    an import side effect: a module that reconfigures the process just by being
    imported is the kind of surprise that makes an incident hard to read.
    """
    path = repo_root(root) / ".env"
    if not path.exists():
        return 0
    loaded = 0
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, raw = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()
            if key and key not in os.environ:
                os.environ[key] = _dotenv_value(raw)
                loaded += 1
    except OSError:  # fail-open: .env is optional convenience, never fatal
        return loaded
    return loaded


_CACHE: dict[Path, dict] = {}


def tenant_config(root: Optional[Path] = None, *, refresh: bool = False) -> dict:
    """Parsed `.agenticframework/tenant.yaml`, or `{}`.

    Cached per root: this is read on several hot-ish paths and the file cannot
    change under a running worker. `refresh=True` is for tests.
    """
    base = repo_root(root)
    if not refresh and base in _CACHE:
        return _CACHE[base]

    path = base / ".agenticframework" / "tenant.yaml"
    doc: dict = {}
    if path.exists():
        try:
            import yaml  # type: ignore

            parsed = yaml.safe_load(path.read_text())
            doc = parsed if isinstance(parsed, dict) else {}
        except Exception:  # fail-open: an unreadable config declares nothing
            doc = {}
    _CACHE[base] = doc
    return doc


def config_get(dotted: str, root: Optional[Path] = None) -> Any:
    """`config_get("budget.monthly_usd_cap")` → the declared value, or None."""
    node: Any = tenant_config(root)
    for part in dotted.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
        if node is None:
            return None
    return node


def resolve(
    dotted: str,
    *,
    explicit: Any = None,
    env_var: Optional[str] = None,
    default: Any = _UNSET,
    cast: Any = None,
    root: Optional[Path] = None,
) -> Any:
    """One setting, resolved by the precedence in this module's docstring.

    `default=_UNSET` means there is no safe default: unresolved raises rather
    than inventing one. Use it for anything an auditor would read as a control.
    """
    if explicit is not None:
        return cast(explicit) if cast else explicit

    if env_var:
        raw = os.environ.get(env_var, "").strip()
        if raw:
            try:
                return cast(raw) if cast else raw
            except (TypeError, ValueError) as exc:
                # Loud: a malformed override must not fall through to the
                # declared value, or the operator's intent is silently ignored.
                raise ValueError(f"{env_var}={raw!r} is not valid for {dotted}") from exc

    declared = config_get(dotted, root)
    if declared is not None:
        return cast(declared) if cast else declared

    if default is _UNSET:
        raise LookupError(
            f"{dotted} is not set. Pass it explicitly"
            + (f", set {env_var}" if env_var else "")
            + f", or declare `{dotted}` in .agenticframework/tenant.yaml."
        )
    return default
