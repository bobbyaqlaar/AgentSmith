"""
scripts/test/test_framework_python_env.py — the Python environment AgentSmith
owns (.agent-rfc/designs/framework-python-env.md).

install-ai-stack.sh used to `pip install` a hand-kept package list into
whatever python3 was first on PATH — Homebrew's externally-managed 3.14 on the
machine this was found on, reachable only through --break-system-packages, and
a list that had drifted from requirements.txt. It now builds
~/.agent-framework/.venv from requirements.lock, the same file Self-Test
installs, at the Python version that lock was compiled for.

The Step 3 tests run the installer's real Step 3 section with uv, python3 and
curl replaced by recording stubs, so nothing is installed.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from packaging.requirements import Requirement

REPO = Path(__file__).resolve().parents[2]
INSTALLER = REPO / "install-ai-stack.sh"
LOCK = REPO / "requirements.lock"

bash_required = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


def _installer_code() -> str:
    """The installer without its comments — several explain what it no longer does."""
    lines = INSTALLER.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def _lock_pins() -> dict[str, str]:
    pins = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)", line)
        if m:
            pins[m.group(1).lower().replace("_", "-")] = m.group(2)
    return pins


def _direct_requirements() -> list[Requirement]:
    reqs = []
    for line in (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            reqs.append(Requirement(line))
    return reqs


# ── the catalog, the lock and the interpreter version agree ─────────────────


def test_the_lock_was_compiled_for_the_python_version_in_dot_python_version():
    header = re.search(r"uv pip compile .*--python-version (\S+)", LOCK.read_text(encoding="utf-8"))
    assert header, "requirements.lock has no `uv pip compile --python-version` header"
    assert header.group(1) == (REPO / ".python-version").read_text(encoding="utf-8").strip()


def test_every_direct_requirement_is_pinned_in_the_lock_within_its_range():
    pins = _lock_pins()
    reqs = _direct_requirements()
    assert len(reqs) > 10, "parsed too few requirements — the parser is broken, not the lock"
    for req in reqs:
        name = req.name.lower().replace("_", "-")
        assert name in pins, f"{req.name} is in requirements.txt but not requirements.lock — recompile the lock"
        assert req.specifier.contains(pins[name], prereleases=True), (
            f"requirements.lock pins {req.name}=={pins[name]}, outside requirements.txt's {req.specifier}"
        )


def test_the_lock_is_hashed():
    text = LOCK.read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=[A-Za-z0-9])", text.split("\n", 2)[2])
    assert len(blocks) == len(_lock_pins()) > 10
    for block in blocks:
        assert "--hash=sha256:" in block, f"unhashed pin: {block.splitlines()[0]}"


def test_unused_packages_stay_out_of_the_catalog():
    names = {r.name.lower() for r in _direct_requirements()}
    assert not names & {"arize-phoenix", "langchain-community", "prophet"}
    assert not any(n.startswith("openinference-") for n in names)


# ── the installer builds the environment, and only from the lock ────────────


def test_the_installer_no_longer_installs_into_the_system_interpreter():
    text = _installer_code()
    assert "--break-system-packages" not in text
    assert "PACKAGES=(" not in text, "a second dependency catalog in the installer"
    assert "python3 -m pip install" not in text
    assert "pip freeze" not in text


def _step3(tmp_path: Path, *, stubs: dict[str, str], installer_dir: Path | None) -> subprocess.CompletedProcess:
    text = INSTALLER.read_text(encoding="utf-8")
    m = re.search(r'^INSTALLER_DIR=.*?(?=^# ═+\n# SECTION 4)', text, re.S | re.M)
    assert m, "Step 3 section not found in install-ai-stack.sh"
    section = re.sub(r"^INSTALLER_DIR=.*$", f'INSTALLER_DIR="{installer_dir or ""}"', m.group(0), count=1, flags=re.M)
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name, body in stubs.items():
        stub = bindir / name
        stub.write_text("#!/bin/bash\n" + body)
        stub.chmod(0o755)
    framework = tmp_path / "home" / ".agent-framework"
    framework.mkdir(parents=True, exist_ok=True)
    script = "\n".join([
        'header() { :; }; info() { echo "$*"; }; warn() { echo "$*"; }; success() { echo "$*"; }',
        'error() { echo "$*" >&2; }',
        "command_exists() { command -v \"$1\" >/dev/null 2>&1; }",
        f'FRAMEWORK_DIR="{framework}"',
        'FRAMEWORK_REPO="https://example.invalid/AgentSmith"',
        section,
    ])
    env = {"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(tmp_path / "home"), "LOG": str(tmp_path / "calls.log")}
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False, env=env)


# A venv's python: reports the version it was "built" at, from a file beside it.
_FAKE_PYTHON = '''#!/bin/bash
if [ "$1" = "-c" ]; then cat "$(dirname "$0")/version"; exit 0; fi
echo "venv-python $*" >> "$LOG"
'''

_UV = '''echo "uv $*" >> "$LOG"
if [ "$1" = "venv" ]; then
  for last; do :; done
  mkdir -p "$last/bin"
  cat > "$last/bin/python" <<'PY'
''' + _FAKE_PYTHON + '''PY
  chmod +x "$last/bin/python"
  echo "3.11" > "$last/bin/version"
fi
'''

_NO_CURL = 'echo "curl $*" >> "$LOG"; exit 22\n'


def _calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


@bash_required
def test_with_uv_the_environment_is_built_at_the_locks_version_and_synced_to_it(tmp_path):
    result = _step3(tmp_path, stubs={"uv": _UV, "curl": _NO_CURL}, installer_dir=REPO)

    assert result.returncode == 0, result.stderr
    venv = tmp_path / "home" / ".agent-framework" / ".venv"
    lock = tmp_path / "home" / ".agent-framework" / "requirements.lock"
    assert lock.read_text() == LOCK.read_text(), "the checkout's lock was not installed"
    assert _calls(tmp_path) == [
        f"uv venv --quiet --allow-existing --python 3.11 {venv}",
        f"uv pip sync --quiet --require-hashes --python {venv}/bin/python {lock}",
    ]


@bash_required
def test_an_environment_on_another_python_version_is_rebuilt(tmp_path):
    venv = tmp_path / "home" / ".agent-framework" / ".venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "bin" / "python").write_text(_FAKE_PYTHON)
    (venv / "bin" / "python").chmod(0o755)
    (venv / "bin" / "version").write_text("3.14")
    (venv / "stale-marker").write_text("from the old environment")

    result = _step3(tmp_path, stubs={"uv": _UV, "curl": _NO_CURL}, installer_dir=REPO)

    assert result.returncode == 0, result.stderr
    assert not (venv / "stale-marker").exists(), "a 3.14 environment was patched instead of rebuilt"
    assert "3.14 → 3.11" in result.stdout


@bash_required
def test_without_uv_it_falls_back_to_venv_and_hashed_pip(tmp_path):
    python3 = '''echo "python3 $*" >> "$LOG"
if [ "$1" = "-m" ] && [ "$2" = "venv" ]; then
  mkdir -p "$3/bin"
  cat > "$3/bin/python" <<'PY'
''' + _FAKE_PYTHON + '''PY
  chmod +x "$3/bin/python"; echo "3.12" > "$3/bin/version"
fi
'''
    result = _step3(tmp_path, stubs={"python3": python3, "curl": _NO_CURL}, installer_dir=REPO)

    assert result.returncode == 0, result.stderr
    venv = tmp_path / "home" / ".agent-framework" / ".venv"
    lock = tmp_path / "home" / ".agent-framework" / "requirements.lock"
    assert _calls(tmp_path) == [
        f"python3 -m venv {venv}",
        f"venv-python -m pip install --quiet --require-hashes -r {lock}",
    ]
    assert "lock compiled for 3.11" in result.stdout


@bash_required
def test_a_failed_build_stops_the_install(tmp_path):
    failing_uv = 'echo "uv $*" >> "$LOG"; exit 1\n'
    result = _step3(tmp_path, stubs={"uv": failing_uv, "curl": _NO_CURL}, installer_dir=REPO)

    assert result.returncode == 1
    assert "could not build" in result.stderr


@bash_required
def test_a_failed_pip_fallback_stops_the_install(tmp_path):
    python3 = '''echo "python3 $*" >> "$LOG"
mkdir -p "$3/bin"; printf '#!/bin/bash\\nexit 1\\n' > "$3/bin/python"; chmod +x "$3/bin/python"
'''
    result = _step3(tmp_path, stubs={"python3": python3, "curl": _NO_CURL}, installer_dir=REPO)

    assert result.returncode == 1
    assert "could not build" in result.stderr


@bash_required
def test_an_old_pip_freeze_is_never_mistaken_for_the_lock(tmp_path):
    framework = tmp_path / "home" / ".agent-framework"
    framework.mkdir(parents=True)
    (framework / "requirements.lock").write_text("arize-phoenix==17.9.0\nprophet==1.1\n")

    result = _step3(tmp_path, stubs={"uv": _UV, "curl": _NO_CURL}, installer_dir=None)

    assert result.returncode == 1
    assert "No requirements.lock" in result.stderr
    assert not [c for c in _calls(tmp_path) if c.startswith("uv ")], "uv ran against a pip freeze"


@bash_required
def test_offline_reinstall_reuses_a_previously_installed_lock(tmp_path):
    framework = tmp_path / "home" / ".agent-framework"
    framework.mkdir(parents=True)
    shutil.copy(LOCK, framework / "requirements.lock")

    result = _step3(tmp_path, stubs={"uv": _UV, "curl": _NO_CURL}, installer_dir=None)

    assert result.returncode == 0, result.stderr
    assert "reusing the one from the previous install" in result.stdout
    assert any(c.startswith("uv pip sync") for c in _calls(tmp_path))


def _installer_dir_block() -> str:
    text = INSTALLER.read_text(encoding="utf-8")
    m = re.search(r'^INSTALLER_DIR="\$\(cd .*?^fi$', text, re.S | re.M)
    assert m, "INSTALLER_DIR detection not found"
    return m.group(0) + '\necho "$INSTALLER_DIR"'


@bash_required
def test_a_piped_install_run_inside_a_tenant_does_not_treat_the_tenant_as_the_checkout(tmp_path):
    tenant = tmp_path / "tenant"
    (tenant / "scripts").mkdir(parents=True)
    (tenant / "requirements.lock").write_text("# someone else's lock\n")
    # `curl … | bash`: the script arrives on stdin, so BASH_SOURCE is empty.
    piped = subprocess.run(["bash"], input=_installer_dir_block(), cwd=tenant,
                           capture_output=True, text=True, check=True)
    assert piped.stdout.strip() == ""


@bash_required
@pytest.mark.parametrize("has_hooks", [True, False])
def test_run_as_a_file_the_directory_is_a_checkout_only_if_it_looks_like_one(tmp_path, has_hooks):
    checkout = tmp_path / "AgentSmith"
    checkout.mkdir()
    # Run as a file inside the directory, the way `./install-ai-stack.sh` is.
    (checkout / "install-ai-stack.sh").write_text(_installer_dir_block())
    if has_hooks:
        (checkout / "hooks").mkdir()
        (checkout / "hooks" / "post-checkout").write_text("")
    elsewhere = tmp_path / "cwd"
    elsewhere.mkdir()
    out = subprocess.run(["bash", str(checkout / "install-ai-stack.sh")], cwd=elsewhere,
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == (str(checkout.resolve()) if has_hooks else "")


def test_the_verification_step_imports_from_the_framework_environment():
    text = INSTALLER.read_text(encoding="utf-8")
    step9 = text[text.index('header "Step 9'):]
    assert '"$VENV_PYTHON" -c "import yaml, networkx' in step9
    assert 'python3 -c "import phoenix"' not in _installer_code()


def test_the_release_ships_the_lock_the_installer_downloads():
    assert "releases/latest/download/requirements.lock" in INSTALLER.read_text(encoding="utf-8")
    assert "cp requirements.lock dist/requirements.lock" in (REPO / ".github/workflows/release.yml").read_text()


# ── the environment is actually used ────────────────────────────────────────


_RESOLUTION = re.compile(
    r'^AF_PYTHON="\$HOME/\.agent-framework/\.venv/bin/python"\n\[ -x "\$AF_PYTHON" \] \|\| AF_PYTHON="python3"$',
    re.M,
)


@pytest.mark.parametrize("hook", ["post-commit", "post-checkout"])
def test_hooks_run_third_party_scripts_with_the_framework_environment(hook):
    text = (REPO / "hooks" / hook).read_text(encoding="utf-8")
    assert len(_RESOLUTION.findall(text)) == 1, f"{hook} lacks the shared AF_PYTHON resolution"
    for script in ("MAP_SCRIPT", "GEN_SCRIPT"):
        assert f'python3 "${script}"' not in text, f"{hook} runs ${script} with bare python3"
    assert '"$AF_PYTHON" "$MAP_SCRIPT"' in text


@bash_required
@pytest.mark.parametrize("present", [True, False])
def test_the_hook_resolution_prefers_the_environment_and_falls_back(tmp_path, present):
    snippet = _RESOLUTION.search((REPO / "hooks" / "post-commit").read_text(encoding="utf-8")).group(0)
    if present:
        py = tmp_path / ".agent-framework" / ".venv" / "bin" / "python"
        py.parent.mkdir(parents=True)
        py.write_text("#!/bin/sh\n")
        py.chmod(0o755)
    out = subprocess.run(
        ["bash", "-c", snippet + '\necho "$AF_PYTHON"'],
        capture_output=True, text=True, check=True, env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
    ).stdout.strip()
    assert out == (str(tmp_path / ".agent-framework/.venv/bin/python") if present else "python3")


def test_self_test_installs_the_lock_at_the_pinned_version():
    text = (REPO / ".github/workflows/self-test.yml").read_text(encoding="utf-8")
    assert "pip install -r requirements.txt" not in text
    assert text.count("pip install --require-hashes -r requirements.lock") == 2
    assert "python-version:" not in text, "a literal Python version beside .python-version"
    assert text.count('python-version-file: ".python-version"') == text.count("actions/setup-python@")


def test_the_standalone_phoenix_fallback_uses_a_subcommand_phoenix_has():
    text = _installer_code()
    assert "phoenix.server.main launch" not in text
    assert "uvx --from arize-phoenix phoenix serve" in text
