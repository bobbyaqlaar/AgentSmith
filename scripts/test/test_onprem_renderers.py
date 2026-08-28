"""
scripts/test/test_onprem_renderers.py — the two proxy renderers must agree.

`templates/onprem-deploy/` ships a customer both an Envoy and a Traefik path
over one `.env`. `_env.py` exists in that bundle to stop its two scripts
drifting — its own docstring says so. They drifted anyway, in the validation
rather than the parsing:

  * `render-envoy-config.py` wrapped APP_PORT in `int()` and died with a bare
    ValueError traceback, not the `❌` message it uses for the canary and
    shadow percentages;
  * `render-traefik-config.py` took the string and interpolated it into a
    backend URL, so `APP_PORT=8080/../admin` rendered
    `http://app-prod:8080/../admin` and `APP_PORT=not-a-port` rendered a URL
    the proxy rejects at startup — hours from the file that caused it.

Neither was right, and a customer switching proxies on one `.env` got different
behaviour from the same bundle. Port parsing lives in `_env.port` now.

These run the scripts as a customer does — as files, in a bundle directory —
because `HERE` is the bundle root and the first version of this probe put `.env`
beside the scripts instead, where nothing read it and every case rendered the
default. That looked like "no validation anywhere" and was a broken probe.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BUNDLE = REPO / "templates" / "onprem-deploy"
RENDERERS = ("render-traefik-config.py", "render-envoy-config.py")


@pytest.fixture()
def bundle(tmp_path: Path) -> Path:
    """A throwaway copy of the bundle, laid out the way it ships."""
    shutil.copytree(BUNDLE / "scripts", tmp_path / "scripts")
    for sub in ("proxy/traefik", "proxy/envoy"):
        (tmp_path / sub).mkdir(parents=True)
    return tmp_path


def _render(bundle: Path, script: str, env_text: str) -> subprocess.CompletedProcess:
    (bundle / ".env").write_text(env_text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(bundle / "scripts" / script)],
        capture_output=True, text=True, check=False,
    )


def test_the_fixture_lays_the_bundle_out_the_way_the_scripts_expect(bundle: Path) -> None:
    """The control. `HERE` is the bundle root; a `.env` beside the scripts is
    read by nothing, and every case would render the default and look clean."""
    proc = _render(bundle, "render-traefik-config.py", "APP_PORT=9999\n")
    assert proc.returncode == 0, proc.stderr
    rendered = (bundle / "proxy" / "traefik" / "dynamic.rendered.yml").read_text()
    assert "app-prod:9999" in rendered, "the .env was not read — probe is wrong"


@pytest.mark.parametrize("script", RENDERERS)
@pytest.mark.parametrize(
    "bad", ["not-a-port", "8080 extra", "8080/../admin", "0", "99999", "-1"]
)
def test_both_renderers_refuse_the_same_bad_port(bundle: Path, script: str, bad: str) -> None:
    proc = _render(bundle, script, f"APP_PORT={bad}\n")
    assert proc.returncode != 0, f"{script} accepted APP_PORT={bad!r}"
    assert "APP_PORT" in proc.stdout + proc.stderr, "the message does not name the variable"
    assert "Traceback" not in proc.stderr, (
        f"{script} failed with a traceback rather than a stated reason"
    )


@pytest.mark.parametrize("script", RENDERERS)
def test_a_valid_port_still_renders(bundle: Path, script: str) -> None:
    """The other control: the guard must not have made every port invalid."""
    proc = _render(bundle, script, "APP_PORT=8080\n")
    assert proc.returncode == 0, proc.stderr


def test_a_bad_port_never_reaches_a_rendered_url(bundle: Path) -> None:
    """The consequence, not the exit code. Traefik interpolates the port into a
    backend URL, so an unvalidated value becomes a URL pointing somewhere
    nobody chose."""
    _render(bundle, "render-traefik-config.py", "APP_PORT=8080/../admin\n")
    out = bundle / "proxy" / "traefik" / "dynamic.rendered.yml"
    if out.exists():
        assert "../admin" not in out.read_text(), "a path traversal reached the config"
