"""
scripts/test/test_gate_models.py — the records a design and a review must carry
beyond Problem/Approach/Levers (.agent-rfc/designs/governance-enforcement.md G1):
one answer per pillar, deviations that resolve to an owner approval, and the
validation-checklist sign-off. Each rule is tested by forcing its violation.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import gate_models as gm

RULES = yaml.safe_load((REPO / "templates" / "agent-rules.yaml").read_text(encoding="utf-8"))
REGISTRY_PATH = REPO / "templates" / "governance.json"


def _registry() -> gm.Registry:
    return gm.Registry.model_validate_json(REGISTRY_PATH.read_text(encoding="utf-8"))


# ── Registry: one source, compiled ───────────────────────────────────────────


def test_the_committed_registry_is_what_agent_rules_compiles_to():
    """governance.json is generated; a hand edit, or a rules edit without
    regenerating, would give the hooks and the rule files two different rule sets."""
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "generate-ide-config.py"), "--registry", "--check-only",
         "--repo-root", str(REPO)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_append_only_records_are_the_ones_whose_numbers_never_move():
    """A bare number in a pointer is a name only in these (process_gate.cross_reference_problems):
    everywhere else it labels a numbered heading or row, which moves."""
    registry = _registry()
    assert {a.id for a in registry.artifacts.types if a.append_only} == {"archive", "review_log", "changelog"}


def test_every_pillar_says_where_it_is_enforced():
    registry = _registry()
    assert [p.id for p in registry.pillars] == [p["id"] for p in RULES["pillars"]]
    for pillar in registry.pillars:
        assert pillar.check, pillar.name
        if "design" in pillar.check:
            assert pillar.design_question, f"P{pillar.id} is answered at design time but asks nothing"


def test_a_registry_with_an_unknown_check_kind_is_rejected():
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    data["pillars"][0]["check"] = ["vibes"]
    with pytest.raises(gm.ValidationError):
        gm.Registry.model_validate(data)


def test_extends_adds_pillars_but_cannot_redefine_one():
    registry = _registry()
    merged = registry.merged(gm.Extends(pillars=[gm.Pillar(id=90, name="Tenant rule", check=["design"],
                                                          design_question="Tenant question?")]))
    assert merged.pillar_ids() == registry.pillar_ids() | {90}
    with pytest.raises(ValueError, match="P1"):
        registry.merged(gm.Extends(pillars=[gm.Pillar(id=1, name="Mine", check=["review"])]))


# ── ## Pillars ───────────────────────────────────────────────────────────────


def _all_design_answers(registry: gm.Registry, skip: int | None = None) -> str:
    return "\n".join(
        f"- P{p.id} applies — because" for p in registry.pillars if "design" in p.check and p.id != skip
    )


def test_a_complete_pillars_section_passes():
    registry = _registry()
    assert gm.check_pillars(_all_design_answers(registry), registry, deviations=[]) == []


def test_a_missing_pillar_is_named():
    registry = _registry()
    errors = gm.check_pillars(_all_design_answers(registry, skip=3), registry, deviations=[])
    assert any("P3" in e and "Tracing" in e for e in errors), errors


def test_grouped_answers_count_for_each_pillar():
    registry = _registry()
    ids = [p.id for p in registry.pillars if "design" in p.check]
    text = f"- {', '.join(f'P{i}' for i in ids)} n/a — a docs-only change"
    assert gm.check_pillars(text, registry, deviations=[]) == []


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("- P3 applies", "says why"),
        ("- P3 n/a —   ", "says why"),
        ("- P3 gap — later", "backlog id"),
        ("- P3 **deviation D9**", "D9"),
        ("- P99 applies — x", "P99"),
        ("- P3 maybe — x", "applies, n/a, gap or deviation"),
    ],
)
def test_a_pillar_answer_that_says_nothing_is_rejected(line, expected):
    registry = _registry()
    text = _all_design_answers(registry, skip=3) + "\n" + line
    errors = gm.check_pillars(text, registry, deviations=[])
    assert any(expected in e for e in errors), errors


def test_a_gap_with_a_backlog_id_and_a_known_deviation_pass():
    registry = _registry()
    deviations = gm.parse_deviations("- D1 — P3 — no spans yet — approval: A-0123abcd")[0]
    text = _all_design_answers(registry, skip=3)
    assert gm.check_pillars(text + "\n- P3 gap — PB-103", registry, deviations=[]) == []
    assert gm.check_pillars(text + "\n- P3 **deviation D1** — see Deviations", registry, deviations) == []


# ── ## Deviations and approvals ──────────────────────────────────────────────


def test_none_means_no_deviations():
    assert gm.parse_deviations("none\n") == ([], [])
    assert gm.parse_deviations("- none — nothing deviates") == ([], [])


def test_withdrawn_deviations_are_not_active():
    found, errors = gm.parse_deviations(
        "- ~~D1 — P3 no spans~~ — withdrawn 2026-09-15\n- T-D2 — P7 — x — approval: A-00000001")
    assert errors == []
    assert [d.id for d in found] == ["T-D2"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", "none"),
        ("- D1 — P3 — no spans", "approval"),
        ("- D1 — P3 — no spans — approval: pending", "approval"),
        ("- D1 — x — approval: A-00000001\n- D1 — y — approval: A-00000002", "twice"),
    ],
)
def test_a_deviation_without_an_approval_id_is_rejected(text, expected):
    errors = gm.parse_deviations(text)[1]
    assert any(expected in e for e in errors), errors


def _approval(**over) -> str:
    data = {
        "id": "A-0123abcd", "design": ".agent-rfc/designs/x.md", "deviation": "D1",
        "approver": "Owner <owner@example.com>", "approved_at": "2026-09-15T10:00:00+00:00",
        "channel": "tty", "statement": "approved: hooks need no spans",
    }
    data.update(over)
    return json.dumps(data)


def test_a_deviation_resolves_only_to_its_own_approval():
    deviations = gm.parse_deviations("- D1 — P3 — x — approval: A-0123abcd")[0]
    approvals, errors = gm.parse_approvals(_approval() + "\n")
    assert errors == []
    assert gm.check_approvals(deviations, approvals, ".agent-rfc/designs/x.md") == []
    other_design = gm.check_approvals(deviations, approvals, ".agent-rfc/designs/y.md")
    assert any("A-0123abcd" in e and "y.md" in e for e in other_design), other_design
    wrong_deviation = gm.check_approvals(gm.parse_deviations("- D2 — P3 — x — approval: A-0123abcd")[0],
                                         approvals, ".agent-rfc/designs/x.md")
    assert any("D2" in e for e in wrong_deviation), wrong_deviation
    missing = gm.check_approvals(gm.parse_deviations("- D1 — P3 — x — approval: A-ffffffff")[0],
                                 approvals, ".agent-rfc/designs/x.md")
    assert any("A-ffffffff" in e and "agentsmith approve" in e for e in missing), missing


@pytest.mark.parametrize("over", [{"channel": "chat"}, {"statement": ""}, {"id": "A-1"}, {"approved_at": "yesterday"}])
def test_an_approval_record_not_made_by_the_command_is_rejected(over):
    approvals, errors = gm.parse_approvals(_approval(**over))
    assert approvals == [] and errors


def test_a_malformed_approvals_line_is_named_not_skipped():
    approvals, errors = gm.parse_approvals(_approval() + "\n{not json\n")
    assert len(approvals) == 1
    assert any("line 2" in e for e in errors), errors


# ── Review sign-off ──────────────────────────────────────────────────────────

SIGNOFF = """## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked
Group 2 · Quality / safety            [x] checked
Group 3 · Architecture / hygiene      [x] checked
Group 4 · Process                     [x] checked
Group 5 · Intuitive UI                [x] n/a — no screen
Group 6 · Signal integrity            [x] gap: PB-9 spans not exported in CI
Group 7 · Auth & session integrity    [x] n/a — no session

Tests added/updated:      test_x.py (3)
Mutation-checked:          yes — removed the guard, 2 tests fail
Fixtures re-pinned:        n/a
Gates run locally:         pytest scripts/test
```
"""


def test_a_complete_signoff_passes():
    assert gm.check_signoff(SIGNOFF, _registry()) == []


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda s: s.replace("## Sign-off (validation-checklist Step 4)", "## Notes"), "no '## Sign-off'"),
        (lambda s: s.replace("Group 5 · Intuitive UI                [x] n/a — no screen\n", ""), "Group 5"),
        (lambda s: s.replace("[x] n/a — no screen", "[ ] checked  [ ] n/a"), "Group 5"),
        (lambda s: s.replace("[x] n/a — no screen", "[x] checked [x] n/a"), "Group 5"),
        (lambda s: s.replace("[x] n/a — no screen", "[x] n/a"), "Group 5"),
        (lambda s: s.replace("gap: PB-9 spans not exported in CI", "gap: ____"), "Group 6"),
        (lambda s: s.replace("yes — removed the guard, 2 tests fail", "____"), "Mutation-checked"),
        (lambda s: s.replace("Gates run locally:         pytest scripts/test\n", ""), "Gates run"),
    ],
)
def test_an_incomplete_signoff_is_named(mutate, expected):
    errors = gm.check_signoff(mutate(SIGNOFF), _registry())
    assert any(expected in e for e in errors), errors


def test_a_malformed_pillar_answer_is_quoted_not_read_as_missing():
    """`_ANSWER` drops a line it cannot parse, and `check_pillars` then reported
    the pillar as unanswered — telling the author they omitted something that is
    on the page. Sibling of the `_PASS` defect in scripts/process_gate.py
    (.agent-rfc/designs/sibling-sweep.md).
    """
    section = "- P1 applies — `scripts/x.py`\n- P3: applies — `scripts/x.py`\n"
    registry = gm.Registry.model_validate(json.loads(REGISTRY_PATH.read_text(encoding="utf-8")))
    errors = gm.check_pillars(section, registry, "")
    assert any("did not parse as a pillar answer" in e for e in errors), errors
    assert any("- P3: applies" in e for e in errors), (
        "the message must quote the line the author wrote", errors)


def test_a_pillar_that_is_genuinely_absent_is_still_reported_as_absent():
    """The diagnosis above must not swallow the case it was confused with."""
    registry = gm.Registry.model_validate(json.loads(REGISTRY_PATH.read_text(encoding="utf-8")))
    errors = gm.check_pillars("- P1 applies — `scripts/x.py`\n", registry, "")
    assert any("does not answer P3" in e for e in errors), errors
    assert not any("did not parse" in e for e in errors), errors
