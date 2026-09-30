"""
runtime/test/test_chosen_ides.py — the tenant's IDE choice is recorded once and
honoured by everything that writes a hook config.

Four commands write those configs — `tenant init`, `tenant adopt`,
`agentsmith sync` and `generate-ide-config.py --hooks`. Before this slice each
read `gate_ides.GENERATED` directly, so a tenant on one IDE was handed the
other's config and `sync` restored it on every run. The reader has to be shared
by all four or `workspace.ides` is a declaration nothing reads — the failure
runtime/config.py's own header is about, and the one
scripts/test/test_fail_closed_declared.py was written for one slice earlier
(.agent-rfc/designs/chosen-ide-is-recorded.md).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from runtime.cli import init_tenant, tenant_yaml
from runtime.config import chosen_ides

REPO = Path(__file__).resolve().parents[2]
AVAILABLE = ("claude", "cursor")

CLAUDE_CFG = ".claude/settings.json"
CURSOR_CFG = ".cursor/hooks.json"


def _declare(root: Path, body: str) -> Path:
    (root / ".agenticframework").mkdir(parents=True, exist_ok=True)
    (root / ".agenticframework" / "tenant.yaml").write_text(body, encoding="utf-8")
    return root


# ── the reader ───────────────────────────────────────────────────────────────

def test_a_declared_subset_is_honoured(tmp_path: Path):
    _declare(tmp_path, "workspace:\n  ides: [cursor]\n")
    assert chosen_ides(tmp_path, AVAILABLE) == ("cursor",)


@pytest.mark.parametrize(
    "body, why",
    [
        ('tenant:\n  id: "a"\n', "no workspace key at all"),
        ("workspace:\n  ides: []\n", "declared empty"),
        ("workspace:\n  ides: [gemini]\n", "names only an IDE with no verified schema"),
        ('workspace:\n  ides: "cursor"\n', "a string where a list belongs"),
        ("workspace: [1,2\n", "malformed YAML — the whole file is ignored"),
        ("", "an empty file"),
    ],
)
def test_every_unreadable_declaration_falls_back_to_all(tmp_path: Path, body: str, why: str):
    """The fallback direction is the one that matters. A declaration that cannot
    be read must leave every verified editor WIRED, never none: the safe failure
    is a config the tenant ignores, not a gate their editor never consults."""
    _declare(tmp_path, body)
    assert chosen_ides(tmp_path, AVAILABLE) == AVAILABLE, why


def test_the_result_is_always_the_frameworks_own_constants(tmp_path: Path):
    """These names become paths (`ADAPTERS[ide].config_path`). The reader
    intersects, so what comes back is from `available`, never a string the file
    supplied — a file a portal or a hand-edit may have written."""
    _declare(tmp_path, "workspace:\n  ides: [cursor, '../../etc/passwd', gemini]\n")
    assert chosen_ides(tmp_path, AVAILABLE) == ("cursor",)


def test_the_reader_sees_a_file_written_after_the_process_started(tmp_path: Path):
    """`tenant init` writes tenant.yaml and then provisions in the SAME process.
    tenant_config caches per root, so a cached read from before the file existed
    would report no declaration and silently restore the default."""
    assert chosen_ides(tmp_path, AVAILABLE) == AVAILABLE  # primes the cache: no file
    _declare(tmp_path, "workspace:\n  ides: [cursor]\n")
    assert chosen_ides(tmp_path, AVAILABLE) == ("cursor",)


# ── what tenant.yaml carries ─────────────────────────────────────────────────

def test_no_choice_writes_no_key(tmp_path: Path):
    """An absent key reads as "every verified IDE" — which is the fallback — so
    writing the full list by default would turn a default into a pin, and a
    later framework that verifies a third schema would not reach this tenant."""
    assert "workspace" not in yaml.safe_load(tenant_yaml("acme"))


def test_a_choice_is_recorded_where_the_other_commands_read_it(tmp_path: Path):
    doc = yaml.safe_load(tenant_yaml("acme", ides=["cursor"]))
    assert doc["workspace"]["ides"] == ["cursor"]


# ── the commands ─────────────────────────────────────────────────────────────

def test_init_with_a_choice_writes_only_that_ides_config(tmp_path: Path):
    written = init_tenant("acme", tmp_path, ides=["cursor"])
    assert CURSOR_CFG in written
    assert CLAUDE_CFG not in written
    assert not (tmp_path / CLAUDE_CFG).exists()


def test_init_without_a_choice_is_unchanged(tmp_path: Path):
    """Every existing invocation, fixture and scratch-tenant scenario passes no
    --ide. If this breaks, the slice was not additive."""
    written = init_tenant("acme", tmp_path)
    assert CURSOR_CFG in written and CLAUDE_CFG in written


def test_init_refuses_an_ide_it_cannot_write_a_config_for(tmp_path: Path):
    with pytest.raises(ValueError) as caught:
        init_tenant("acme", tmp_path, ides=["gemini"])
    message = str(caught.value)
    assert "gemini" in message
    for alternative in AVAILABLE:
        assert alternative in message, "the refusal must name what IS available"


def test_a_typo_and_an_unverified_ide_get_different_answers(tmp_path: Path):
    """`denied-vs-missing`. `gemini` is a real IDE whose config SHAPE is
    unconfirmed; `cursro` is a misspelling. Telling someone their spelling is an
    unverified schema sends them to the wrong fix."""
    with pytest.raises(ValueError) as unverified:
        init_tenant("acme", tmp_path, ides=["gemini"])
    with pytest.raises(ValueError) as unknown:
        init_tenant("acme", tmp_path, ides=["cursro"])

    assert "verified config schema" in str(unverified.value)
    assert "does not know" in str(unknown.value) or "not an IDE this framework knows" in str(unknown.value)
    assert str(unverified.value) != str(unknown.value)


def test_the_contract_profile_is_not_an_ide_you_can_choose(tmp_path: Path):
    """`neutral` is contract/gate/v1 — a profile a provider implements, with an
    empty config_path. Accepting it would write a config to the repo root."""
    with pytest.raises(ValueError):
        init_tenant("acme", tmp_path, ides=["neutral"])


def test_the_gate_itself_is_armed_whatever_the_ide_choice_says(tmp_path: Path):
    """P13's proven half. An IDE config decides which editor ALSO consults the
    gate before an edit; it is not the gate. The shell hooks are what every
    other editing path — a terminal `sed`, vim, another agent — still meets, so
    narrowing the IDE configs must not narrow those."""
    def hooks(written: list[str]) -> set[str]:
        return {p for p in written if p.startswith(".githooks/")}

    narrowed = hooks(init_tenant("acme", tmp_path, ides=["cursor"]))
    every = hooks(init_tenant("acme", tmp_path.parent / "wide", ides=None))
    assert narrowed, "no gate hooks installed at all — this test checked nothing"
    assert narrowed == every


# ── no fifth site ────────────────────────────────────────────────────────────

WRITERS = (
    "runtime/cli.py",
    "runtime/sync.py",
    "runtime/adopt.py",
    "scripts/generate-ide-config.py",
)


def test_every_writer_routes_the_verified_set_through_the_reader():
    """The regression this slice exists to prevent: a fifth site, or a restored
    fourth, selecting IDEs straight from `GENERATED` and undoing the tenant's
    recorded choice on its next run. Source-level, because the drift is
    invisible at runtime until someone's `.claude/settings.json` reappears.

    Per FILE rather than per loop: `generate-ide-config.py` resolves the set into
    a local first, so it needs a fail-open `except` around the import, and a
    check that read only the loop's iterator would see nothing there.
    """
    for rel in WRITERS:
        source = (REPO / rel).read_text(encoding="utf-8")
        assert "GENERATED" in source, (
            f"{rel}: no longer names GENERATED — it either stopped writing IDE configs, "
            f"in which case drop it from WRITERS, or it now gets the set from somewhere "
            f"this guard cannot see"
        )
        assert "chosen_ides" in source, (
            f"{rel}: writes IDE configs without reading the tenant's declared "
            f"workspace.ides, so the choice is reverted on its next run"
        )
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.For):
                iterated = ast.unparse(node.iter)
                assert not ("GENERATED" in iterated and "chosen_ides" not in iterated), (
                    f"{rel}: `for … in {iterated}` iterates the verified set directly"
                )
