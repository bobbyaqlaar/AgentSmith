"""
scripts/test/test_no_hardcoded_model_ids.py — model ids live in models.yaml,
not scattered through the code.

Before this guard there were four independent copies of "which model is the
architect tier", and all four disagreed: runtime/models.yaml said one thing,
scripts/cost_router.py another, scripts/multi_agent_system.py a third, and the
CI templates pinned a fourth via `AGENT_JUDGE_MODEL || 'claude-sonnet-4-6'`.
Each was individually plausible and none was checked against the registry, so
changing models.yaml changed almost nothing and nobody found out.

The rule: an executable line may name a model only where it is resolving one
from the registry — `role_model(...)`, `_tier(...)`, `provider_models(...)` —
i.e. as the documented fallback for a scripts-only install with no runtime/ on
the path. Anything else needs `# model-literal-ok: <reason>`, following the
repo's existing `# fail-open:` convention.

Prose in comments and docstrings is exempt: recording that a default USED to be
`gpt-4o` is history, not configuration.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Deliberately requires version/tag specificity: bare family names appear in
# legitimate provider-routing substring checks ("llama" in model_id.lower())
# and are not model identifiers.
_MODEL_ID = re.compile(
    r"""\b(
        qwen[\d.]+
      | llama[\d][\w.]*(?::\w+)?
      | llama-\d[\w.-]*
      | falcon\d(?::\w+)?
      | smollm\d
      | gemma\d
      | gpt-[\d][\w.-]*
      | claude-[\w.-]*\d[\w.-]*
      | gemini-[\d][\w.-]*
    )\b""",
    re.IGNORECASE | re.VERBOSE,
)

# A literal is allowed on a line that is resolving it from the registry.
_RESOLVERS = ("role_model(", "_tier(", "provider_models(", "DEFAULT_JUDGE_MODEL")
_ESCAPE_HATCH = "# model-literal-ok:"

_SCANNED_DIRS = ("scripts", "runtime")


def _scannable_files() -> list[Path]:
    files: list[Path] = []
    for directory in _SCANNED_DIRS:
        for path in sorted((REPO / directory).rglob("*.py")):
            parts = path.relative_to(REPO).parts
            if "test" in parts or "__pycache__" in parts:
                continue
            files.append(path)
    return files


def _docstring_lines(source: str) -> set[int]:
    """Line numbers covered by module/class/function docstrings.

    Parsed rather than pattern-matched: a class docstring whose opening line
    also carries text defeats a naive triple-quote scanner, and
    runtime/provider_dispatch.py has exactly that shape.
    """
    import ast

    covered: set[int] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return covered
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                covered.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return covered


def _offending_lines(path: Path) -> list[tuple[int, str]]:
    source = path.read_text(encoding="utf-8")
    docstrings = _docstring_lines(source)
    lines = source.splitlines()
    out: list[tuple[int, str]] = []

    for lineno, raw in enumerate(lines, 1):
        if lineno in docstrings:
            continue
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        code = line.split("#", 1)[0]
        if not _MODEL_ID.search(code):
            continue
        # A wrapped call puts the literal on a later line than its resolver, so
        # look at a small window rather than the single line.
        window = "\n".join(lines[max(0, lineno - 4) : lineno + 1])
        if any(marker in window for marker in _RESOLVERS) or _ESCAPE_HATCH in raw:
            continue
        out.append((lineno, line[:120]))
    return out


def test_no_unresolved_model_ids_in_scripts_or_runtime() -> None:
    offenders: list[str] = []
    for path in _scannable_files():
        for lineno, line in _offending_lines(path):
            offenders.append(f"{path.relative_to(REPO)}:{lineno}: {line}")
    assert not offenders, (
        "model ids must come from models.yaml (role_model/_tier/provider_models), "
        "or carry `# model-literal-ok: <reason>`:\n  " + "\n  ".join(offenders)
    )


def test_ci_templates_do_not_pin_a_judge_model() -> None:
    """`AGENT_JUDGE_MODEL: ${{ secrets.X || 'claude-sonnet-4-6' }}` looked like
    a harmless default, but the env var WINS over the registry — so every tenant
    CI run overrode its own declared judge route with a framework literal."""
    offenders: list[str] = []
    for path in sorted((REPO / "workflow-templates").glob("*.yml")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "AGENT_JUDGE_MODEL" in line and _MODEL_ID.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()[:120]}")
    assert not offenders, (
        "CI templates must leave AGENT_JUDGE_MODEL unset so the `judge` role in "
        "models.yaml decides:\n  " + "\n  ".join(offenders)
    )


def test_the_guard_actually_catches_a_hardcoded_id(tmp_path: Path) -> None:
    """A guard nobody has seen fail is a guard nobody should trust."""
    probe = tmp_path / "probe.py"
    probe.write_text('MODEL = "gpt-4o"\n', encoding="utf-8")
    assert _offending_lines(probe) == [(1, 'MODEL = "gpt-4o"')]

    probe.write_text('MODEL = role_model("developer", "gpt-4o")\n', encoding="utf-8")
    assert _offending_lines(probe) == []

    probe.write_text('MODEL = "gpt-4o"  # model-literal-ok: pinned by vendor\n', encoding="utf-8")
    assert _offending_lines(probe) == []
