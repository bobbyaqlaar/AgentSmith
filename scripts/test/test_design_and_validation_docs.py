"""
scripts/test/test_design_and_validation_docs.py — the design/validation
playbooks stay in step with review-levers.md, agent-rules.yaml, the
generator, and the installer.

WHY THIS EXISTS. `docs/design-review-checklist.md` reframes every lever in
`docs/review-levers.md` as build-time guidance — the same discipline
`scripts/test/test_lever_notes.py` already holds `review-lever-notes.md` to,
applied to a second derived document. A lever added to review-levers.md
without its design-phase counterpart added here is the exact
`no-redundant-artifacts` / `declared-vs-enforced` failure this checklist set
exists to catch, aimed at itself — so this is checked mechanically rather
than trusted to be remembered.

Four separate things are verified, because each is a distinct way this could
quietly stop being true: the docs could fall out of step with the levers: the
YAML could stop declaring the two playbook skills; the generator could stop
rendering them into every target file; the installer could stop vendoring the
two docs, which would make every generated pointer resolve to nothing outside
a live framework checkout (see generate-ide-config.py's _playbook_location).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from _shared import load_script

LEVERS = ROOT / "docs" / "review-levers.md"
DESIGN_DOC = ROOT / "docs" / "design-review-checklist.md"
VALIDATION_DOC = ROOT / "docs" / "validation-checklist.md"
AGENT_RULES = ROOT / "templates" / "agent-rules.yaml"
INSTALLER = ROOT / "install-ai-stack.sh"

yaml = pytest.importorskip("yaml")


def _lever_slugs() -> dict[str, bool]:
    """{slug: is_legacy} — same parse as test_lever_notes.py's `_levers()`.
    Not imported from there: that module is a test file, and test files in
    this repo do not import each other (see the other self-contained
    extractors, e.g. test_verify_system_modes.py, test_documented_env_vars_
    exist.py). The regex is small enough that duplicating it is cheaper than
    a new shared-helper module for a two-caller utility."""
    return {
        m.group(1): "(legacy)" in m.group(2)
        for m in re.finditer(
            r"^- `([a-z][a-z0-9-]*)` — (.*)$", LEVERS.read_text(encoding="utf-8"), re.M
        )
    }


def test_the_source_files_exist_and_are_substantial() -> None:
    """Guard the guard — a missing or near-empty file makes every assertion
    below vacuous rather than a real check."""
    assert len(_lever_slugs()) > 30, "review-levers.md parsed too small — has it moved?"
    assert DESIGN_DOC.exists(), DESIGN_DOC
    assert VALIDATION_DOC.exists(), VALIDATION_DOC
    assert DESIGN_DOC.stat().st_size > 4000
    assert VALIDATION_DOC.stat().st_size > 2000


def test_every_lever_has_a_design_phase_counterpart() -> None:
    """Every slug in review-levers.md — legacy included, since a legacy lever
    still needs a build-time reframe even though it is exempt from the
    evidence requirement `review-lever-notes.md` enforces — must appear as a
    backtick-quoted citation in design-review-checklist.md."""
    design_text = DESIGN_DOC.read_text(encoding="utf-8")
    cited = set(re.findall(r"`([a-z][a-z0-9-]*)`", design_text))
    missing = sorted(s for s in _lever_slugs() if s not in cited)
    assert not missing, (
        "these levers have no design-phase counterpart in "
        f"design-review-checklist.md: {missing}"
    )


def test_design_doc_does_not_cite_an_unknown_slug() -> None:
    """The reverse direction — a citation left behind after a lever was
    renamed or removed, the same failure test_lever_notes.py's
    test_no_note_is_orphaned catches for review-lever-notes.md."""
    design_text = DESIGN_DOC.read_text(encoding="utf-8")
    cited = set(re.findall(r"`([a-z][a-z0-9-]*)`", design_text))
    slugs = set(_lever_slugs())
    # Only flag tokens that look lever-shaped AND are plausibly lever
    # references (appear immediately after a "- **`" heading marker or a
    # markdown link target) — plain backtick code spans for things like file
    # names would otherwise false-positive. Restrict to the checklist's own
    # bold-bullet citation shape: `**\`slug\`**` or a bare "`slug`" at a
    # bullet start, which is the only shape this doc actually uses for lever
    # references (verified by test_every_lever_has... finding >30 matches).
    orphans = sorted(
        s for s in cited
        if s not in slugs
        and re.search(rf"\*\*`{s}`\*\*", design_text)
    )
    assert not orphans, (
        f"design-review-checklist.md cites slug(s) not in review-levers.md: {orphans}"
    )


def test_validation_doc_points_at_review_levers_rather_than_restating_it() -> None:
    """The validation doc deliberately does NOT re-derive the levers —
    `single-source-of-truth` applied to itself.

    Citing a slug for traceability is fine and expected — review-levers.md's
    own header sanctions exactly that ("Cite one from code as `review-levers:
    grep-for-siblings`"), and Step 4's sign-off block names several by design.
    What must NOT happen is the RULE TEXT itself getting copied in — that
    would be the second copy `single-source-of-truth` warns against, not the
    citation. So this checks for verbatim duplication of a lever's rule
    sentence, not for the presence of its slug.
    """
    text = VALIDATION_DOC.read_text(encoding="utf-8")
    assert "review-levers.md" in text

    lever_lines = re.findall(
        r"^- `[a-z][a-z0-9-]*` — (?:\*\*\([^)]*\)\*\* )?(.+)$",
        LEVERS.read_text(encoding="utf-8"),
        re.M,
    )
    duplicated = [rule for rule in lever_lines if len(rule) > 20 and rule in text]
    assert not duplicated, (
        "validation-checklist.md contains a lever's RULE TEXT verbatim — cite "
        f"the slug instead of restating the rule: {duplicated}"
    )


def test_agent_rules_yaml_declares_both_playbooks() -> None:
    rules = yaml.safe_load(AGENT_RULES.read_text(encoding="utf-8"))
    skills_by_id = {s["id"]: s for s in rules.get("skills", [])}
    for skill_id, doc_name in (
        ("design_review", "design-review-checklist.md"),
        ("validation_review", "validation-checklist.md"),
    ):
        assert skill_id in skills_by_id, f"{skill_id} missing from agent-rules.yaml skills:"
        entry = skills_by_id[skill_id]
        for field in ("title", "trigger", "doc", "summary"):
            assert entry.get(field), f"{skill_id}.{field} is missing or empty"
        assert entry["doc"] == f"docs/{doc_name}", entry["doc"]
        # The doc it points at must actually exist under docs/ — a typo'd
        # filename here would be a broken pointer shipped to every tenant.
        assert (ROOT / entry["doc"]).exists(), entry["doc"]


def test_generator_renders_both_playbooks_into_every_target() -> None:
    """End to end: run the real generator against a scratch repo and confirm
    every target file actually contains both playbooks, not just that the
    YAML declares them. A drift-check pass alone (test_lever_notes.py-style)
    would not catch a renderer that silently dropped a section."""
    import subprocess

    ide = load_script("generate-ide-config")
    rules = ide._load_rules(AGENT_RULES)
    ctx = {
        "project_name": "coverage-probe",
        "owner_id": "probe@example.test",
        "otel_endpoint": "http://localhost:6006",
        "test_cmd": "pytest",
        "framework_version": "0.0.0-test",
    }

    checks = {
        ".cursorrules": ide._render_cursorrules(rules, "python-fastapi", ctx),
        "CLAUDE.md": ide._render_claude_md(rules, ctx),
        "AGENTS.md": ide._render_agents_md(rules, "python-fastapi", ctx),
        "GEMINI.md": ide._render_gemini_md(rules, "python-fastapi", ctx),
        ".github/copilot-instructions.md": ide._render_copilot_instructions(
            rules, "python-fastapi", ctx
        ),
    }
    for name, body in checks.items():
        assert "design-review-checklist.md" in body or "design_review" in body.lower() \
            or "Design Review" in body, f"{name} has no trace of the design playbook"
        assert "Validation & Test Checklist" in body or "validation-checklist.md" in body, (
            f"{name} has no trace of the validation playbook"
        )

    for skill_id in ("design_review", "validation_review"):
        skill = next(s for s in rules["skills"] if s["id"] == skill_id)
        body = ide._render_skill(skill, rules, ctx)
        assert skill["doc"] in body, f".agents/skills/{skill_id}/skill.md missing its doc pointer"

    # And --check-only reports clean on what the generator itself just wrote —
    # the actual CI gate, exercised rather than inferred from the pieces above.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / ".agenticframework").mkdir()
        (tmp_path / "requirements.txt").write_text("fastapi\npytest\n")
        env_ok = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "generate-ide-config.py"),
                "--repo-root", str(tmp_path), "--rules-file", str(AGENT_RULES),
            ],
            capture_output=True, text=True, timeout=60, check=False,
        )
        assert env_ok.returncode == 0, env_ok.stderr

        drift = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "generate-ide-config.py"),
                "--repo-root", str(tmp_path), "--rules-file", str(AGENT_RULES),
                "--check-only",
            ],
            capture_output=True, text=True, timeout=60, check=False,
        )
        assert drift.returncode == 0, (
            f"--check-only reported drift on freshly generated output:\n{drift.stdout}"
        )
        for skill_id in ("design_review", "validation_review"):
            assert f".agents/skills/{skill_id}/skill.md matches" in drift.stdout, drift.stdout


def test_installer_vendors_the_two_docs() -> None:
    """Without this step the pointer in every generated file resolves against
    $AGENTSMITH_DIR only, which is unset for a tenant on the installed
    package rather than a live checkout — see _playbook_location's docstring
    in generate-ide-config.py."""
    text = INSTALLER.read_text(encoding="utf-8")
    assert "design-review-checklist.md" in text
    assert "validation-checklist.md" in text
    assert "FRAMEWORK_DIR/docs" in text
