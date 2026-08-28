"""
templates/onprem-deploy/scripts/_env.py — .env parsing for the render scripts.

`render-envoy-config.py` and `render-traefik-config.py` each carried a
byte-identical `load_env`, and both had the same defect: an inline comment was
kept as part of the value. `APP_PORT=8080  # the app port` produced the port
`"8080  # the app port"`, which Traefik then embedded in a backend URL, and
`CANARY_WEIGHT_PERCENT=10  # start small` raised ValueError inside int(). Both
are near-universal .env conventions, so this hit a normal, correct-looking file
and failed in a way that reads like a broken deployment rather than a parse bug.

Deliberately NOT importing `scripts/_shared._dotenv_value`, which implements the
same rule. `templates/onprem-deploy/` is a standalone bundle: it is copied to a
customer's on-prem host, often air-gapped (see bundle-airgapped.sh), where the
framework's `scripts/` directory does not exist. That is the same architectural
boundary `_shared` already documents for `runtime/`. What this file removes is
the duplication WITHIN the bundle, which is the part that could drift silently
between two scripts shipped side by side.
"""

from __future__ import annotations

import os
from pathlib import Path


def parse_value(raw: str) -> str:
    """One .env value: strip an unquoted inline comment, then quotes.

    An inline comment must be preceded by whitespace, so a bare `#` inside an
    unquoted value survives — passwords and URL fragments contain them. A
    QUOTED value keeps everything between the quotes: `PASS="a#b # c"` is
    `a#b # c`, not `a#b`.
    """
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        quote = raw[0]
        end = raw.find(quote, 1)
        if end != -1:
            return raw[1:end]
        return raw[1:]  # unterminated quote — take the rest
    for i, ch in enumerate(raw):
        if ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            return raw[:i].strip()
    return raw


def load_env(env_path: Path) -> dict:
    """Process environment, overlaid with `env_path` for keys it does not set.

    `setdefault`, so a value exported in the shell still wins over the file —
    which is what lets `up.sh` override a bundled default without editing it.
    """
    env = dict(os.environ)
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), parse_value(v))
    return env


def port(env: dict, name: str, default: str) -> int:
    """A TCP port from `env`, or a clear failure.

    Here rather than in either renderer because the two had drifted on exactly
    this, in the bundle whose duplication this module exists to remove.
    `render-envoy-config.py` wrapped APP_PORT in `int()` and crashed with a
    bare ValueError traceback on a bad value; `render-traefik-config.py` took
    the string and interpolated it into a backend URL, so
    `APP_PORT=8080/../admin` rendered `http://app-prod:8080/../admin` and
    `APP_PORT=not-a-port` rendered a URL the proxy rejects at startup, hours
    away from the file that caused it.

    Neither was right. One failed unhelpfully, one did not fail at all, and a
    customer switching proxies on the same `.env` got different behaviour from
    the same bundle.

    Raises ValueError with a message naming the variable and the value — the
    renderers catch it and exit non-zero, the way they already do for the
    canary and shadow percentages.
    """
    raw = (env.get(name) or default).strip()
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be a whole number, got {raw!r}") from None
    if not 1 <= value <= 65535:
        raise ValueError(f"{name} must be a TCP port in 1-65535, got {value}")
    return value
