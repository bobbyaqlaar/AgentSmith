"""An agent may edit `.agenticframework/compliance.json`; a change that weakens a duty
needs the owner's approval, and every change is logged
(.agent-rfc/designs/declaration-ratchet-and-atomic-test.md, the 4.1.0 review's second
pass, P2-R12)."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import gate_models as gm
import gate_pillars as gp
import gate_shell
import test_process_gate as tpg
from test_process_gate import _commit, _write, needs_git

FILLED = {
    "profile": "dubai-gov",
    "app_owner": "owner@entity.ae",
    "data_classes": ["open", "internal", "confidential", "secret"],
    "classified_from": "confidential",
    "boundary": {"hosts": ["*.entity.ae"],
                 "sinks": {"database": "db.entity.ae", "traces": "phoenix.entity.ae", "blobs": "s3.entity.ae",
                           "embeddings": "db.entity.ae", "portal": "ops.entity.ae"}},
    "session": {"idle_minutes": 15, "absolute_hours": 8},
    "retention_days": {"audit": 1095, "runs": 365, "traces": 180},
    "continuity": {"rpo_minutes": 60, "rto_minutes": 240, "drill_every_days": 365, "backup_host": "bk.entity.ae"},
    "languages": ["ar", "en"],
    "agents": [{"name": "triage", "accountable_owner": "lead@entity.ae"}],
    "user_calls_per_minute": 30,
}


def _with(change) -> dict:
    new = copy.deepcopy(FILLED)
    change(new)
    return new


@pytest.mark.parametrize("change, expected", [
    (lambda d: d["languages"].remove("ar"), "languages"),
    (lambda d: d["boundary"]["hosts"].append("*.example.com"), "boundary.hosts"),
    (lambda d: d["boundary"]["sinks"].update(traces="cloud.example.com"), "boundary.sinks.traces"),
    (lambda d: d.update(classified_from="secret"), "classified"),
    (lambda d: d["session"].update(idle_minutes=60), "session.idle_minutes"),
    (lambda d: d["session"].update(absolute_hours=24), "session.absolute_hours"),
    (lambda d: d["retention_days"].update(audit=30), "retention_days.audit"),
    (lambda d: d["retention_days"].pop("traces"), "retention_days.traces"),
    (lambda d: d["continuity"].update(rto_minutes=1440), "continuity.rto_minutes"),
    (lambda d: d["continuity"].update(backup_host="elsewhere.example"), "continuity.backup_host"),
    (lambda d: d.update(agents=[]), "agents"),
    (lambda d: d["agents"][0].update(accountable_owner="someone@else"), "agents"),
    (lambda d: d.pop("user_calls_per_minute"), "user_calls_per_minute"),
    (lambda d: d.update(user_calls_per_minute=300), "user_calls_per_minute"),
    (lambda d: d.update(app_owner="other@entity.ae"), "app_owner"),
])
def test_each_weakening_is_named(change, expected):
    found = gp.declaration_weakenings(FILLED, _with(change))
    assert any(expected in item for item in found), found


def test_deleting_the_declaration_is_a_weakening():
    assert gp.declaration_weakenings(FILLED, None) == ["the declaration is deleted"]


@pytest.mark.parametrize("change", [
    lambda d: d["languages"].append("fr"),
    lambda d: d["boundary"]["hosts"].remove("*.entity.ae"),
    lambda d: d["session"].update(idle_minutes=5),
    lambda d: d["retention_days"].update(audit=2000),
    lambda d: d.update(classified_from="internal"),
    lambda d: d.update(user_calls_per_minute=10),
    lambda d: d["agents"].append({"name": "second", "accountable_owner": "x@entity.ae"}),
])
def test_a_strengthening_needs_nothing(change):
    assert gp.declaration_weakenings(FILLED, _with(change)) == []


def test_filling_a_placeholder_is_not_a_weakening():
    template = json.loads((HERE.parents[1] / "templates" / "compliance" / "dubai-gov" / "compliance.json").read_text())
    filled = {**FILLED, "languages": template["languages"], "session": template["session"],
              "retention_days": template["retention_days"]}
    filled["continuity"] = {**template["continuity"], "backup_host": "bk.entity.ae"}
    assert gp.declaration_weakenings(template, filled) == []


APPROVAL = gm.Approval(id="A-0123abcd", design="d", deviation="D1", approver="owner",
                       approved_at="2026-11-13T00:00:00Z", channel="tty",
                       statement="drop Arabic: the service is English-only")


def test_a_weakening_needs_a_cited_approval_the_owner_recorded():
    old, new = json.dumps(FILLED), json.dumps(_with(lambda d: d["languages"].remove("ar")))
    problems, summary = gp.declaration_transition(old, new, [], "feat: drop Arabic\n")
    assert problems and "Approval: A-" in problems[0] and summary["weakened"]
    problems, _ = gp.declaration_transition(old, new, [], "feat: drop Arabic\n\nApproval: A-0123abcd\n")
    assert problems  # cited, but never recorded
    problems, summary = gp.declaration_transition(old, new, [APPROVAL], "feat: drop Arabic\n\nApproval: A-0123abcd\n")
    assert problems == [] and summary["approval"] == "A-0123abcd"


def test_the_shell_no_longer_refuses_the_declaration():
    """The owner's decision: agents may edit it with any tool; the ratchet judges what they did."""
    assert not gate_shell._protects(".agenticframework/compliance.json")


def _history(repo: Path) -> list[dict]:
    log = repo / ".agent-history.log"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.is_file() else []


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A repository with the gate's real hooks, as `test_process_gate.gated_repo` builds it."""
    return tpg._make_repo(tmp_path, "repo", {
        **tpg.GATE_FILES, **tpg.AGENTSMITH_MARKERS,
        "docs/review-levers.md": tpg.REPO / "docs/review-levers.md",
        tpg.pg.CONFIG: json.dumps(tpg.FIXTURE_CONFIG, indent=2) + "\n",
        **tpg.HOOK_FILES,
    }, monkeypatch)


@needs_git
def test_a_commit_that_weakens_the_declaration_is_refused_then_allowed_with_approval_and_logged(repo):
    gated_repo = repo
    _write(gated_repo, ".agenticframework/compliance.json", json.dumps(FILLED, indent=2) + "\n")
    assert _commit(gated_repo, "docs: declare the profile").returncode == 0
    assert _history(gated_repo)[-1]["event"] == "compliance_declaration_changed"

    _write(gated_repo, ".agenticframework/compliance.json",
           json.dumps(_with(lambda d: d["languages"].remove("ar")), indent=2) + "\n")
    refused = _commit(gated_repo, "docs: drop Arabic")
    assert refused.returncode != 0 and "languages" in refused.stderr
    entry = _history(gated_repo)[-1]
    assert entry["event"] == "compliance_declaration_weakening_refused" and entry["hitl_resolved"] is False
    assert "languages" in entry["detail"]

    _write(gated_repo, gm.APPROVALS_FILE, APPROVAL.model_dump_json() + "\n")
    allowed = _commit(gated_repo, "docs: drop Arabic\n\nApproval: A-0123abcd")
    assert allowed.returncode == 0, allowed.stderr
    entry = _history(gated_repo)[-1]
    assert entry["event"] == "compliance_declaration_weakened" and "A-0123abcd" in entry["detail"]
    assert entry["level"] == "MAJOR" and entry["hitl_resolved"] is True


@pytest.mark.parametrize("artifacts", ["report", "enforce"])
@pytest.mark.parametrize("gated", [False, True])
def test_the_ratchet_holds_in_every_mode_gated_or_not(artifacts, gated):
    """Whether or not a config gates the declaration, and in either artifacts mode, a
    weakening without an approval is refused, here and in CI (`check_change` is both)."""
    config = tpg.pg.Config({**tpg.FIXTURE_CONFIG, "artifacts": artifacts,
                            "gated": [".agenticframework/**"] if gated else ["nothing/**"]})
    old = {gp.DECLARATION_FILE: json.dumps(FILLED)}
    new = {gp.DECLARATION_FILE: json.dumps(_with(lambda d: d["languages"].remove("ar")))}
    errors, _notes = tpg.pg.check_change([gp.DECLARATION_FILE], 3, "docs: drop Arabic\n", new.get,
                                         config, [], old.get)
    assert any("weakens a compliance duty" in error for error in errors), errors
