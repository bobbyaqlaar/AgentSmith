"""
scripts/test/test_gate_contract_v3.py — gate contract 3: a tenant's commit and
push ask its declared provider, and the knowledge graph is the gate's
(.agent-rfc/designs/gate-local-events.md).

The published files are held to the models and to version 2; AgentSmith is held
to the contract as a provider; and real `git commit` and `git push` run through
the tenant's hooks at contract 3, and at 2, so the difference is observed rather
than assumed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git required")

V2 = REPO / "contract" / "gate" / "v2"
V3 = REPO / "contract" / "gate" / "v3"
PROVIDER = f"{sys.executable} -m runtime.cli gate"
HOOKS = ("process-gate", "commit-msg", "pre-commit", "pre-push")


# ── The published contract ────────────────────────────────────────────────────


def test_agentsmith_passes_contract_3(tmp_path, monkeypatch):
    from runtime import conformance

    monkeypatch.setenv("AGENTSMITH_DIR", str(REPO))
    monkeypatch.setenv("PYTHONPATH", str(REPO))

    report = conformance.run(PROVIDER, tmp_path / "work", contract=3)

    assert report.passed, report.render()
    assert {r.case.event_name for r in report.results} >= {"commit", "push", "kg"}


@pytest.mark.parametrize("name, model", [
    ("event.schema.json", "GateEventV3"),
    ("decision.schema.json", "DecisionV2"),
    ("knowledge_graph.schema.json", "KnowledgeGraph"),
    ("kg_impact.schema.json", "KgImpact"),
])
def test_the_v3_schemas_are_the_models(name, model):
    import gate_models as gm

    published = json.loads((V3 / name).read_text(encoding="utf-8"))
    generated = getattr(gm, model).model_json_schema()
    for key in ("description", "$schema", "$id"):
        published.pop(key, None)
        generated.pop(key, None)
    assert published == generated, f"contract/gate/v3/{name} no longer matches {model}"


def test_version_3_carries_version_2_unchanged():
    v2_cases = json.loads((V2 / "cases.json").read_text())["cases"]
    v3_cases = json.loads((V3 / "cases.json").read_text())["cases"]
    assert v3_cases[: len(v2_cases)] == v2_cases
    assert {c["event_name"] for c in v3_cases[len(v2_cases):]} == {"commit", "push", "kg"}
    assert json.loads((V3 / "fixture.json").read_text()) == json.loads((V2 / "fixture.json").read_text())


def test_this_repositorys_graph_is_a_valid_graph():
    """The schema is published for tenants' graphs; this repository's own, built
    by the same builder, must satisfy it — or the schema describes nothing real."""
    import gate_models as gm

    graph = gm.KnowledgeGraph.model_validate_json(
        (REPO / ".agent-rfc" / "fixtures" / "knowledge_graph.json").read_text(encoding="utf-8"))
    assert graph.nodes and (graph.edges or graph.links)


def test_what_adopt_declares_is_a_valid_contract_3_declaration():
    import jsonschema

    from runtime.adopt import providers_declaration

    declared = json.loads(providers_declaration())
    jsonschema.validate(declared, json.loads((V3 / "providers.schema.json").read_text()))
    assert declared["contract"] == 3


def test_the_subject_rule_is_one_rule_in_two_places():
    """Below contract 3 the hook applies it in bash; at 3 the provider does in
    Python. Two copies that must not drift (`pin-unremovable-duplicates`)."""
    import process_gate as pg

    hook = (REPO / ".githooks" / "commit-msg").read_text(encoding="utf-8")
    bash = re.search(r'=~ (\^.*\$) \]\]', hook).group(1).replace("\\ ", " ")
    assert bash == pg.COMMIT_SUBJECT


# ── The provider answers with its own gate ────────────────────────────────────


def test_the_provider_never_answers_with_a_tenants_vendored_gate(tmp_path):
    """A vendored tenant holds its own, possibly stale, scripts/process_gate.py.
    The provider used to prefer it; judged by it, a tenant on contract 2 or 3 was
    still judged by framework code it holds (gate-local-events.md)."""
    tenant = tmp_path / "tenant"
    (tenant / "scripts").mkdir(parents=True)
    (tenant / "scripts" / "process_gate.py").write_text(
        'print(\'{"decision": "deny", "text": "THE TENANT\\\'S VENDORED COPY"}\')\n')
    subprocess.run(["git", "init", "-q", "--template=", str(tenant)], check=True)

    done = subprocess.run([sys.executable, "-m", "runtime.cli", "gate", "pre-edit"], cwd=tenant,
                          input=json.dumps({"kind": "edit", "paths": ["docs/x.md"]}), capture_output=True, text=True,
                          env={**os.environ, "AGENTSMITH_DIR": str(REPO), "PYTHONPATH": str(REPO)}, check=False)

    assert "VENDORED COPY" not in done.stdout, "the provider ran the tenant's copy of the gate"
    assert json.loads(done.stdout)["decision"] == "allow"


# ── The knowledge-graph verbs ─────────────────────────────────────────────────


def _env(**extra: str) -> dict:
    env = {**os.environ, "AGENTSMITH_DIR": str(REPO), "PYTHONPATH": str(REPO), "AGENTSMITH_PYTHON": sys.executable,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x",
           **extra}
    env.pop("GOVERNANCE_PROVIDER", None)
    return env


@pytest.fixture()
def repo(tmp_path):
    """The contract's fixture at `clean`, the tags to the commit that skipped the
    gate dropped, and the tenant's own copies of the gate hooks, armed."""
    from runtime.conformance import build_fixture

    root = build_fixture(tmp_path / "repo", 3)
    subprocess.run(["git", "-C", str(root), "checkout", "-q", "--detach", "clean"], check=True)
    for tag in ("undesigned", "after"):
        subprocess.run(["git", "-C", str(root), "tag", "-d", tag], check=True, capture_output=True)
    (root / ".githooks").mkdir()
    for hook in HOOKS:
        shutil.copy(REPO / ".githooks" / hook, root / ".githooks" / hook)
        (root / ".githooks" / hook).chmod(0o755)
    subprocess.run(["git", "-C", str(root), "config", "core.hooksPath", ".githooks"], check=True)
    return root


def _declare(root: Path, contract: int, command: str = PROVIDER) -> None:
    (root / ".agenticframework" / "providers.json").write_text(
        json.dumps({"contract": contract, "providers": {"gate": {"command": command}}}) + "\n")


def _commit(root: Path, subject: str, rel: str, body: str) -> subprocess.CompletedProcess:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(body)
    subprocess.run(["git", "-C", str(root), "add", "--", rel], check=True)
    return subprocess.run(["git", "-C", str(root), "commit", "-m", subject], cwd=root, env=_env(),
                          capture_output=True, text=True, check=False)


def test_kg_impact_names_the_staged_scope_as_the_contract_shapes_it(repo):
    import gate_models as gm

    (repo / "src" / "covered.py").write_text("VALUE = 8\n")
    subprocess.run(["git", "-C", str(repo), "add", "src/covered.py"], check=True)

    done = subprocess.run([sys.executable, "-m", "runtime.cli", "gate", "kg", "impact"], cwd=repo, env=_env(),
                          capture_output=True, text=True, check=False)

    found = gm.KgImpact.model_validate_json(done.stdout)
    assert "src/covered.py" in found.files


def test_kg_impact_scopes_the_commit_not_the_working_tree(repo):
    """An unstaged edit is not in the commit, and not in the scope the commit
    gate checks the review against. `git diff <base>` counted it — which is how a
    review's hash used to disagree with the gate's."""
    import gate_models as gm

    (repo / "src" / "covered.py").write_text("VALUE = 8\n")
    subprocess.run(["git", "-C", str(repo), "add", "src/covered.py"], check=True)
    (repo / "src" / "other.py").write_text("VALUE = 77\n")  # edited, not staged

    done = subprocess.run([sys.executable, "-m", "runtime.cli", "gate", "kg", "impact"], cwd=repo, env=_env(),
                          capture_output=True, text=True, check=False)

    found = gm.KgImpact.model_validate_json(done.stdout)
    assert "src/covered.py" in found.files and "src/other.py" not in found.files


def test_kg_build_writes_a_graph_the_contract_describes(repo):
    import gate_models as gm

    done = subprocess.run([sys.executable, "-m", "runtime.cli", "gate", "kg", "build"], cwd=repo, env=_env(),
                          capture_output=True, text=True, check=False)

    assert done.returncode == 0, done.stderr
    graph = gm.KnowledgeGraph.model_validate_json((repo / ".agent-rfc/fixtures/knowledge_graph.json").read_text())
    assert any(node.id == "src/covered.py" for node in graph.nodes)


# ── The hooks: `git commit` and `git push` at contract 3, and at 2 ────────────


def test_at_contract_3_a_commit_of_nothing_governed_is_made(repo):
    _declare(repo, 3)
    result = _commit(repo, "docs: a note", "docs/note.md", "a note\n")
    assert result.returncode == 0, result.stdout + result.stderr


def test_at_contract_3_a_governed_commit_with_no_design_is_refused_by_the_provider(repo):
    _declare(repo, 3)
    result = _commit(repo, "feat: change covered", "src/covered.py", "VALUE = 6\n")
    assert result.returncode != 0
    assert "Design" in result.stderr


def test_at_contract_3_the_subject_rule_is_the_providers(repo):
    """The same rule refuses at 2 and at 3 — but from different places: at 3 the
    hook holds no policy and the refusal is the provider's answer."""
    _declare(repo, 3)
    at3 = _commit(repo, "a subject that breaks the rule", "docs/a.md", "a\n")
    assert at3.returncode != 0 and "process gate:" in at3.stderr and "Conventional Commit" in at3.stderr

    subprocess.run(["git", "-C", str(repo), "reset", "-q"], check=True)
    _declare(repo, 2)
    at2 = _commit(repo, "a subject that breaks the rule", "docs/b.md", "b\n")
    assert at2.returncode != 0 and "commit blocked: subject must be" in at2.stderr


@pytest.mark.parametrize("command, why", [("false", "printed no decision"),
                                           ("no-such-gate-provider-xyz", "not installed")])
def test_at_contract_3_no_decision_blocks_the_commit_and_never_falls_back(repo, command, why):
    """The commit touches nothing governed: the framework's own gate would let it
    through. Being blocked proves nothing fell back to it."""
    _declare(repo, 3, command)
    result = _commit(repo, "docs: a note", "docs/note.md", "a note\n")
    assert result.returncode != 0
    assert "gave no decision for `commit`" in result.stderr and why in result.stderr


def test_at_contract_3_pre_commit_asks_nothing(repo):
    """`commit` runs the sweep and decides; pre-commit's report would only repeat it."""
    _declare(repo, 3)
    at3 = _commit(repo, "docs: a note", "docs/note.md", "a note\n")
    _declare(repo, 2)
    at2 = _commit(repo, "docs: another note", "docs/other.md", "another\n")
    assert "sweep:" not in at3.stdout + at3.stderr
    assert "sweep:" in at2.stdout + at2.stderr, "below 3 pre-commit's report still runs"


@pytest.fixture()
def remote(repo, tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "--template=", str(bare)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(bare)], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "work"], check=True)
    return bare


def _push(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", "work"], env=_env(),
                          capture_output=True, text=True, check=False)


def _skip_the_gate(repo: Path) -> None:
    """A commit from an unarmed clone: the hooks path unset for one commit."""
    subprocess.run(["git", "-C", str(repo), "config", "--unset", "core.hooksPath"], check=True)
    (repo / "src" / "other.py").write_text("VALUE = 9\n")
    subprocess.run(["git", "-C", str(repo), "commit", "-qam", "feat: no gate met"], env=_env(), check=True)
    subprocess.run(["git", "-C", str(repo), "config", "core.hooksPath", ".githooks"], check=True)


def test_at_contract_3_a_clean_history_is_pushed(repo, remote):
    _declare(repo, 3)
    assert _commit(repo, "docs: a note", "docs/note.md", "a note\n").returncode == 0
    result = _push(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_at_contract_3_a_history_with_a_commit_that_skipped_the_gate_is_not_pushed(repo, remote):
    _declare(repo, 3)
    assert _commit(repo, "docs: a note", "docs/note.md", "a note\n").returncode == 0  # the sweep's starting point
    _skip_the_gate(repo)

    result = _push(repo)

    assert result.returncode != 0
    assert "push blocked by the gate" in result.stderr


def test_a_provider_older_than_the_declared_contract_is_named_with_the_fix(repo, tmp_path):
    """What happens when a tenant moves to contract 3 ahead of a machine's
    install: the installed provider does not know `commit` and exits 2 with a
    usage error. The developer is told that, and what to do — not "exit 2"."""
    old = tmp_path / "old-provider"
    old.write_text('#!/usr/bin/env bash\necho "usage: old-provider {session-start,pre-edit,stop,ci}" >&2\nexit 2\n')
    old.chmod(0o755)
    _declare(repo, 3, str(old))

    result = _commit(repo, "docs: a note", "docs/note.md", "a note\n")

    assert result.returncode != 0
    assert "older than the gate contract this repository declares" in result.stderr
    assert "install-ai-stack.sh" in result.stderr



def test_a_launcher_too_old_to_name_the_contract_keeps_the_subject_rule(repo):
    """A tenant's commit-msg newer than its launcher: `declared-contract` answers
    with anything but a number. The rule is dropped only for a plain 3 or more,
    so an unreadable answer keeps it — failing safe, not silently open."""
    old = repo / ".githooks" / "process-gate"
    old.write_text('#!/usr/bin/env bash\necho "usage: process-gate <subcommand>"\nexit 0\n')
    old.chmod(0o755)
    _declare(repo, 3)

    result = _commit(repo, "a subject that breaks the rule", "docs/a.md", "a\n")

    assert result.returncode != 0
    assert "commit blocked: subject must be" in result.stderr

# ── The hooks themselves ──────────────────────────────────────────────────────


@pytest.mark.parametrize("hook", sorted(p.name for p in (REPO / ".githooks").iterdir() if p.is_file()))
def test_every_gate_hook_parses(hook):
    """A launcher that does not parse fails closed everywhere at once — every
    edit, every turn, every commit — and nothing can repair it from inside a
    session it governs. That happened while this slice was built: an apostrophe
    in a comment inside the launcher's single-quoted Python ended the quote."""
    done = subprocess.run(["bash", "-n", str(REPO / ".githooks" / hook)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr


def test_the_launchers_inline_python_is_quoted_whole_and_compiles():
    """Each `python3 -c '...'` block must end at a quote on a line of its own;
    one ending mid-line was cut short by a quote inside it — an apostrophe in
    a comment or a string — even where bash still parses the result."""
    text = (REPO / ".githooks" / "process-gate").read_text(encoding="utf-8")
    marker = "python3 -c '"
    blocks = 0
    start = text.find(marker)
    while start != -1:
        body_start = start + len(marker)
        end = text.index("'", body_start)
        line = text.count("\n", 0, start) + 1
        assert text[end - 1] == "\n", (
            f"the inline Python starting at line {line} ends mid-line — a quote inside it closes the shell's quoting")
        compile(text[body_start:end], f"process-gate inline python at line {line}", "exec")
        blocks += 1
        start = text.find(marker, end + 1)
    assert blocks >= 2, "the launcher's decision and event-encoding blocks were found"
