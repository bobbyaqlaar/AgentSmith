"""
runtime/test/test_architectures.py — the structural styles `tenant init
--architecture` offers, and the agentic overlay (.agent-rfc/designs/
tenant-architecture.md).

The catalogue is data a person edits, so its internal references are checked
here rather than trusted: every dependency names a layer of the same style, and
every style says where the agent layer sits in it.
"""

from __future__ import annotations

import pytest

from runtime import architectures as arch

STYLES = ("layered", "modular-monolith", "hexagonal", "microservice", "event-driven")


def test_the_catalogue_offers_the_five_styles():
    assert tuple(arch.catalogue().styles) == STYLES


@pytest.mark.parametrize(("alias", "style"), [
    ("clean", "hexagonal"), ("ports-and-adapters", "hexagonal"), ("onion", "hexagonal"),
    ("n-tier", "layered"), ("Hexagonal", "hexagonal"), ("modular-monolith", "modular-monolith"),
])
def test_the_names_people_use_resolve_to_a_style(alias, style):
    assert arch.resolve_style(alias) == style


def test_an_unknown_style_is_refused_with_the_choices():
    with pytest.raises(ValueError, match=r"layered.*hexagonal"):
        arch.resolve_style("big-ball-of-mud")


@pytest.mark.parametrize("style", STYLES)
def test_every_dependency_names_a_layer_of_the_same_style(style):
    layers = arch.catalogue().styles[style].layers
    names = {layer.name for layer in layers}
    for layer in layers:
        assert set(layer.may_depend_on) <= names, f"{style}: {layer.name} depends on an unknown layer"


def test_every_style_says_where_the_agent_layer_sits():
    catalogue = arch.catalogue()
    assert set(catalogue.agentic.placement) == set(catalogue.styles)


@pytest.mark.parametrize(("stack", "root"), [("python-fastapi", "app/"), ("ts-react", "src/"), ("go", "internal/")])
def test_the_design_section_names_real_paths_for_the_stack(stack, root):
    text = arch.render_design_md("demo", stack, "hexagonal", agentic=False)
    assert "## Architecture" in text and "Hexagonal" in text
    assert f"`{root}domain/`" in text
    assert "<src>" not in text
    assert "## The agent layer" not in text, "the overlay appears only when asked for"


def test_the_agentic_overlay_adds_the_agent_layer_and_where_it_sits():
    text = arch.render_design_md("demo", "python-fastapi", "hexagonal", agentic=True)
    assert "## The agent layer" in text
    assert "`app/agents/`" in text
    assert arch.catalogue().agentic.placement["hexagonal"] in text


def test_without_a_style_the_design_says_one_is_still_to_choose():
    text = arch.render_design_md("demo", "python-fastapi", None, agentic=False)
    assert "No structural style was chosen" in text
    assert "--architecture" in text


PILLARS = [
    {"id": 1, "name": "Requirements and Design", "check": ["design"]},
    {"id": 5, "name": "Operations and Self-Improvement", "check": ["review"]},
    {"id": 9, "name": "Multi-Agent Orchestration", "check": ["design"]},
    {"id": 99, "name": "A pillar added later", "check": ["design"]},
]


def test_the_scaffold_design_answers_every_design_pillar_and_scopes_exactly_the_scaffold():
    files = [".githooks/commit-msg", ".github/workflows/ci-python-fastapi.yml"]
    text = arch.render_scaffold_design("demo", "python-fastapi", "layered", False, files, PILLARS)
    head, body = text.split("\n---\n", 1)
    assert "status: done" in head, "the scaffold's design authorises nothing after the scaffold"
    assert all(f"  - {f}" in head for f in files)
    for pillar in (1, 9, 99):
        assert f"- P{pillar} " in body, f"P{pillar} is not answered"
    assert "- P5 " not in body, "a review-only pillar is not answered in a design"
    assert "- P9 n/a" in body, "multi-agent orchestration does not apply to a non-agentic scaffold"


def test_an_agentic_scaffold_design_says_the_agent_rules_are_recorded():
    text = arch.render_scaffold_design("demo", "python-fastapi", "hexagonal", True, [".githooks/x"], PILLARS)
    assert "- P9 applies" in text


def test_the_session_start_line_names_the_style_and_its_rule():
    line = arch.session_start_line("hexagonal", agentic=True)
    assert "Hexagonal" in line and "docs/DESIGN.md" in line and "agent" in line.lower()
    assert arch.session_start_line(None, agentic=False) is None


# ── tenant adopt (.agent-rfc/designs/tenant-adopt.md) ────────────────────────


def test_a_target_architecture_is_a_direction_and_starts_at_the_repositorys_code():
    text = arch.render_architecture("python-fastapi", "hexagonal", agentic=True, target=True, source_root="mypkg/")
    assert text.startswith("## Architecture (target)")
    assert "may not follow it yet" in text
    assert "`mypkg/domain/`" in text and "`mypkg/agents/`" in text and "`app/" not in text


def test_a_target_without_a_style_does_not_point_at_tenant_init():
    text = arch.render_architecture("go", None, agentic=False, target=True)
    assert "No structural style was chosen at adoption" in text and "tenant init" not in text


def test_the_adoption_design_describes_an_adoption():
    text = arch.render_scaffold_design("legacy", "python-fastapi", "layered", False, ["CLAUDE.md"], PILLARS,
                                       adopted=True)
    assert "# Adopt legacy" in text and "tenant adopt" in text and "tenant init" not in text
    assert "`.github/workflows/agentsmith-gates.yml`" in text and "ci-python-fastapi" not in text
    assert "status: done" in text
