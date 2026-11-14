"""
map_codebase.py — AST-based codebase walker that populates the Knowledge Graph.

Walks .py, .ts, .tsx, .js, .jsx, and .go files in the repo root.
Extracts top-level symbols (functions, classes, exports, interfaces).
Detects import relationships and writes edges to the graph.
Purges stale CodebaseFile nodes for deleted files.
Wires Guardrail nodes from .cursorrules and .agent-rfc/ markdown files, and
from docs/superpowers/{specs,plans}/ when a repo uses Anthropic's superpowers
skill for its spec-before-code artifacts instead of (or alongside) .agent-rfc/
— see _extract_guardrails_from_superpowers. Both sources are indexed
unconditionally, keyed by a source-tagged rule_id (`rfc:*` vs
`superpowers:*`), rather than the walker picking one convention for a repo:
which one is a given repo's actual spec authority is a fact about that repo
(often "whichever directory has content"), not something this script should
decide on its own.

Called by the post-commit and post-checkout hooks automatically.
Also runnable directly: python3 scripts/map_codebase.py
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Optional

# ── Helpers ───────────────────────────────────────────────────────────────────

from _shared import _repo_root


IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".agent-rfc",
    ".agents",
    ".github",
    # Framework/tooling build output. `dist` and `build` were here but not the
    # JS framework equivalents, so the portal's Next.js output put 297 minified
    # bundle files into the graph — two thirds of every node in it — and they
    # rode into the agent context window that fetch_subgraph_context_window
    # builds. Generated artifacts are never the code an agent should reason
    # about.
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".turbo",
    "out",
    "coverage",
    ".ruff_cache",
    ".tox",
    "site-packages",
}

EXTENSION_TO_LANG = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
}


def _nested_checkouts(root: Path) -> set[Path]:
    """Directories below `root` that are their own git checkout.

    A git worktree's `.git` is a file, a clone's is a directory; either says
    the code below it belongs to another tree. This IDE opens worktrees at
    `.claude/worktrees/<name>/`, and before they were skipped one of them put
    196 foreign nodes — another branch's copy of the portal — into the
    committed graph, which then differed by machine.
    """
    found: set[Path] = set()
    for path in root.rglob(".git"):
        try:
            if path.parent != root and path.exists():
                found.add(path.parent)
        except OSError:  # fail-open: an unreadable directory stays part of the repo
            pass
    return found


def _mapped(root: Path) -> Optional[set[str]]:
    """The repository-relative paths git holds under `root`: tracked files,
    plus untracked ones no ignore rule covers, so a design not yet added still
    maps. A generated, ignored file is not the repository's, and became a node
    anyway: the evidence pack's `delivery_evidence.md` read as a rule in force
    (.agent-rfc/designs/kg-maps-what-git-tracks.md).

    None when git cannot say — no checkout, no git, a failed `ls-files` — and
    then every file maps, as before: unknown is not "nothing is tracked", which
    would purge every node."""
    try:
        listed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True, check=False,
        )
    except OSError:  # fail-open: no git on PATH — map everything, as the walk always did
        return None
    if listed.returncode != 0:
        return None
    return {p for p in listed.stdout.decode("utf-8", "surrogateescape").split("\0") if p}


def _held(path: Path, root: Path, mapped: Optional[set[str]]) -> bool:
    return mapped is None or path.relative_to(root).as_posix() in mapped


def _iter_source_files(root: Path, mapped: Optional[set[str]] = None):
    nested = _nested_checkouts(root)
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if any(checkout in path.parents for checkout in nested):
            continue
        if path.suffix in EXTENSION_TO_LANG and path.is_file() and _held(path, root, mapped):
            yield path


# ── Language-specific parsers ─────────────────────────────────────────────────


def _parse_python(path: Path) -> tuple[list[str], list[str]]:
    """Return (symbols, imported_modules)."""
    symbols: list[str] = []
    imports: list[str] = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Only top-level (parent == Module)
                if isinstance(getattr(node, "_parent", None), type(None)):
                    symbols.append(node.name)
            elif isinstance(node, ast.Import):
                # The full module path: `agentsmith.compliance`, never just
                # `agentsmith`, or nothing resolves (the 4.1.0 review's third pass, P3-R17).
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                # `from a.b import c` may import the module `a.b.c` or a name in `a.b`:
                # both are offered and the resolver keeps what exists. A relative import
                # keeps its leading dots.
                base = "." * node.level + (node.module or "")
                if node.module:
                    imports.append(base)
                joiner = "" if base.endswith(".") or not base else "."
                imports.extend(base + joiner + alias.name for alias in node.names if alias.name != "*")

        # Fix: mark parent on top-level nodes only
        symbols = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
    # fail-open: one unparsable file must not abort the whole codebase scan; it just
    # contributes no symbols/imports
    except SyntaxError:
        pass
    return list(dict.fromkeys(symbols)), list(dict.fromkeys(imports))


def _parse_typescript(path: Path) -> tuple[list[str], list[str]]:
    symbols: list[str] = []
    imports: list[str] = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        # Exported declarations
        for m in re.finditer(
            r"^export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var|interface|type|enum)\s+(\w+)",
            source,
            re.MULTILINE,
        ):
            symbols.append(m.group(1))
        # Every module specifier: `import … from`, `export … from`, side-effect
        # `import "…"` and `import("…")`. Packages are kept here and dropped by the
        # resolver, which knows the relative and `tsconfig` alias forms (P3-R17).
        for m in re.finditer(r"""(?:\bfrom\s+|\bimport\s+|\bimport\s*\(\s*)['"]([^'"]+)['"]""", source):
            imports.append(m.group(1))
    # fail-open: one unparsable file must not abort the whole codebase scan; it just
    # contributes no symbols/imports
    except Exception:
        pass
    return list(dict.fromkeys(symbols)), list(dict.fromkeys(imports))


def _parse_go(path: Path) -> tuple[list[str], list[str]]:
    symbols: list[str] = []
    imports: list[str] = []
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        # Exported identifiers (start with uppercase)
        for m in re.finditer(
            r"^func\s+(\([^)]*\)\s+)?([A-Z]\w*)\s*\(", source, re.MULTILINE
        ):
            symbols.append(m.group(2))
        for m in re.finditer(r"^type\s+([A-Z]\w*)\s+", source, re.MULTILINE):
            symbols.append(m.group(1))
        # Import paths
        for m in re.finditer(r'"([^"]+)"', source):
            pkg = m.group(1)
            if "/" in pkg:
                imports.append(pkg.split("/")[-1])
    # fail-open: one unparsable file must not abort the whole codebase scan; it just
    # contributes no symbols/imports
    except Exception:
        pass
    return list(dict.fromkeys(symbols)), list(dict.fromkeys(imports))


_PARSERS = {
    "python": _parse_python,
    "typescript": _parse_typescript,
    "javascript": _parse_typescript,  # same parser works
    "go": _parse_go,
}


# ── Guardrail extraction from .cursorrules ────────────────────────────────────

_PILLAR_RE = re.compile(r"^##\s+(\d+)\.\s+(.+)$", re.MULTILINE)


def _extract_guardrails_from_cursorrules(path: Path, root: Path) -> list[dict]:
    guardrails = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in _PILLAR_RE.finditer(text):
            pillar_num = int(m.group(1))
            title = m.group(2).strip()
            guardrails.append(
                {
                    "rule_id": f"cursorrules:pillar:{pillar_num}",
                    "title": title,
                    "pillar": pillar_num,
                    "source_file": path.relative_to(root).as_posix(),
                }
            )
    # fail-open: one unparsable .cursorrules file must not abort the whole codebase scan;
    # it just contributes no guardrails
    except Exception:
        pass
    return guardrails


def _extract_guardrails_from_rfc(rfc_dir: Path, root: Path, mapped: Optional[set[str]] = None) -> list[dict]:
    guardrails = []
    for md_file in rfc_dir.glob("**/*.md"):
        if not _held(md_file, root, mapped):
            continue
        try:
            text = md_file.read_text(encoding="utf-8", errors="replace")
            # Extract first H1 or H2 as the rule title
            m = re.search(r"^#{1,2}\s+(.+)$", text, re.MULTILINE)
            title = m.group(1).strip() if m else md_file.stem
            guardrails.append(
                {
                    "rule_id": f"rfc:{md_file.relative_to(rfc_dir)}",
                    "title": title,
                    "pillar": None,
                    "source_file": md_file.relative_to(root).as_posix(),
                }
            )
        except Exception:  # fail-open: one unparsable RFC file must not abort scanning the rest of the directory
            pass
    return guardrails


def _extract_guardrails_from_superpowers(superpowers_dir: Path, root: Path,
                                         mapped: Optional[set[str]] = None) -> list[dict]:
    """Mirror of `_extract_guardrails_from_rfc` for the superpowers skill's own
    spec-before-code convention (`docs/superpowers/specs/`,
    `docs/superpowers/plans/`). A repo that adopted superpowers before — or
    instead of — AgentSmith's `.agent-rfc/` still has its design history
    somewhere; this makes it visible in the graph rather than invisible next
    to an empty `.agent-rfc/`."""
    guardrails = []
    for kind in ("specs", "plans"):
        kind_dir = superpowers_dir / kind
        if not kind_dir.exists():
            continue
        for md_file in kind_dir.glob("**/*.md"):
            if not _held(md_file, root, mapped):
                continue
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
                m = re.search(r"^#{1,2}\s+(.+)$", text, re.MULTILINE)
                title = m.group(1).strip() if m else md_file.stem
                guardrails.append(
                    {
                        "rule_id": f"superpowers:{kind[:-1]}:{md_file.relative_to(superpowers_dir)}",
                        "title": title,
                        "pillar": None,
                        "source_file": md_file.relative_to(root).as_posix(),
                    }
                )
            except Exception:  # fail-open: one unreadable skill file must not lose
                # the rest of the map, same as the RFC extractor above.
                pass
    return guardrails


# ── Resolve local import to file path ─────────────────────────────────────────


def _tsconfig_aliases(source_file: Path, root: Path) -> list[tuple[str, Path]]:
    """`compilerOptions.paths` of the nearest `tsconfig.json`, as (prefix, directory):
    `"@/*": ["./*"]` in `portal/tsconfig.json` is ("@/", portal/)."""
    folder = source_file.parent
    while True:
        config = folder / "tsconfig.json"
        if config.is_file():
            try:
                options = json.loads(config.read_text(encoding="utf-8")).get("compilerOptions") or {}
            except ValueError:
                return []
            base = folder / (options.get("baseUrl") or ".")
            out = []
            for pattern, targets in (options.get("paths") or {}).items():
                if pattern.endswith("*") and targets and str(targets[0]).endswith("*"):
                    out.append((pattern[:-1], (base / str(targets[0])[:-1]).resolve()))
            return out
        if folder == root or folder.parent == folder:
            return []
        folder = folder.parent


def _inside(path: Path, root: Path) -> Optional[str]:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return None


def _resolve_local_import(
    source_file: Path,
    import_path: str,
    root: Path,
    lang: str,
) -> Optional[str]:
    """
    Resolve one import to a repo-relative path, or None when it is not a file of this
    repository (a package, the standard library, a name rather than a module).

    Python: a relative import from the importing file's package; an absolute one
    against the repository root, the importing file's own directory and `scripts/`,
    which the scripts put on `sys.path`. TypeScript: relative specifiers, and the
    `paths` aliases of the nearest `tsconfig.json` (P3-R17).
    """
    if lang in ("python",):
        dots = len(import_path) - len(import_path.lstrip("."))
        parts = [p for p in import_path[dots:].split(".") if p]
        if dots:
            base = source_file.parent
            for _ in range(dots - 1):
                base = base.parent
            roots = [base]
        else:
            roots = [root, source_file.parent, root / "scripts"]
        for base in roots:
            target = base.joinpath(*parts) if parts else base
            for candidate in (Path(str(target) + ".py"), target / "__init__.py"):
                if candidate.is_file():
                    found = _inside(candidate, root)
                    if found:
                        return found
        return None
    if import_path.startswith("."):
        bases = [(source_file.parent / import_path)]
    else:
        bases = [directory / import_path[len(prefix):] for prefix, directory in _tsconfig_aliases(source_file, root)
                 if import_path.startswith(prefix)]
    for base in bases:
        for ext in ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", "/index.ts", "/index.tsx", "/index.js"):
            candidate = Path(str(base.resolve()) + ext)
            if candidate.is_file():
                found = _inside(candidate, root)
                if found:
                    return found
    return None


# ── Main walker ───────────────────────────────────────────────────────────────


# Raised whenever what the parsers extract changes. A graph built by another version is
# re-parsed whole: the incremental path keeps a file's edges until the file changes, so a
# parser fix never reached the graph (the 4.1.0 review's third pass, P3-R17).
PARSER_VERSION = 2


def run_map(verbose: bool = False, force: bool = False) -> dict:
    """Walk the repo into the Knowledge Graph.

    `force` re-parses every file instead of skipping those whose stored mtime
    still matches. The incremental path is right for the post-commit hook, but
    it can only ever repair a node whose FILE changed — a graph that is wrong
    for any other reason (a hand edit, a bad merge, a truncated write) is
    invisible to it and survives every subsequent run. One was committed and
    pushed on 2026-08-24 with a node's symbols replaced by a test string; three
    regenerations later it was still there, because middleware.ts had not been
    touched. Callers that VERIFY the graph should force.
    """
    try:
        from local_knowledge_graph import AgentKnowledgeGraph
    except ImportError:
        from scripts.local_knowledge_graph import AgentKnowledgeGraph

    root = _repo_root()
    kg = AgentKnowledgeGraph()
    if kg._g.graph.get("parser_version") != PARSER_VERSION:
        force = True
    kg._g.graph["parser_version"] = PARSER_VERSION

    # Track which files we see during this walk
    seen_files: set[str] = set()
    # …and which guardrails this walk produces, for the purge after extraction.
    seen_guardrails: set[str] = set()
    stats = {"upserted": 0, "unchanged": 0, "edges": 0, "guardrails": 0, "purged": 0}

    # What git holds, decided once for the walk and the three extractions below.
    mapped = _mapped(root)

    # ── Walk source files ─────────────────────────────────────────────────────
    for abs_path in _iter_source_files(root, mapped):
        lang = EXTENSION_TO_LANG.get(abs_path.suffix, "unknown")
        rel_path = str(abs_path.relative_to(root))
        seen_files.add(rel_path)

        last_modified = abs_path.stat().st_mtime

        from datetime import datetime, timezone

        mtime_str = datetime.fromtimestamp(last_modified, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        # Incremental skip (ReviewFindings-2026-07-18 C2): a node whose stored
        # last_modified matches the file's current mtime was already parsed by
        # a previous run — its symbols and import edges are in the graph.
        # Skipping unchanged files turns the per-commit rebuild from
        # "re-parse the whole repo" into "re-parse what the commit touched",
        # and also skips the per-upsert graph save each node would trigger.
        # (mtime granularity is 1s ISO here — a same-second rewrite is caught
        # on the next run once the clock ticks; commits are slower than that.)
        existing = None if force else (
            kg._g.nodes[rel_path] if kg._g.has_node(rel_path) else None
        )
        if (
            existing is not None
            and existing.get("node_type") == "CodebaseFile"
            and existing.get("last_modified") == mtime_str
            and existing.get("language") == lang
        ):
            stats["unchanged"] += 1
            if verbose:
                print(f"  [{lang}] {rel_path} — unchanged, skipped")
            continue

        parser = _PARSERS.get(lang)
        symbols, raw_imports = parser(abs_path) if parser else ([], [])

        kg.upsert_file(
            rel_path, language=lang, symbols=symbols, last_modified=mtime_str
        )
        stats["upserted"] += 1

        # Resolve and wire import edges
        for raw_imp in raw_imports:
            resolved = _resolve_local_import(abs_path, raw_imp, root, lang)
            if resolved and resolved != rel_path:
                kg.add_import(rel_path, resolved)
                stats["edges"] += 1

        if verbose:
            print(
                f"  [{lang}] {rel_path} — {len(symbols)} symbols, {len(raw_imports)} imports"
            )

    # ── Purge CodebaseFile nodes this walk did not claim ──────────────────────
    # "Not seen by this walk" is the whole question. It used to also require the
    # file to be GONE from disk, which kept every node the walker had stopped
    # claiming for any other reason — an ignored directory, or a checkout living
    # inside the repo. That is why adding an ignore rule could not clean a graph
    # that already held 196 nodes from an IDE worktree: the files were still
    # there, so they were never stale. `seen_files` holds every file the walk
    # included, skipped-as-unchanged ones too, so nothing of ours is in here.
    stale = [
        node_id
        for node_id, attrs in kg._g.nodes(data=True)
        if attrs.get("node_type") == "CodebaseFile" and node_id not in seen_files
    ]
    for node_id in stale:
        kg.remove_node(node_id)
        stats["purged"] += 1
        if verbose:
            print(f"  🗑  Purged stale node: {node_id}")

    # ── Extract guardrails from .cursorrules ──────────────────────────────────
    cursorrules = root / ".cursorrules"
    if cursorrules.exists() and _held(cursorrules, root, mapped):
        for gr in _extract_guardrails_from_cursorrules(cursorrules, root):
            kg.upsert_guardrail(
                gr["rule_id"], gr["title"], gr["source_file"], gr["pillar"]
            )
            seen_guardrails.add(gr["rule_id"])
            stats["guardrails"] += 1

    # ── Extract guardrails from .agent-rfc/ markdown ──────────────────────────
    rfc_dir = root / ".agent-rfc"
    if rfc_dir.exists():
        for gr in _extract_guardrails_from_rfc(rfc_dir, root, mapped):
            kg.upsert_guardrail(
                gr["rule_id"], gr["title"], gr["source_file"], gr["pillar"]
            )
            seen_guardrails.add(gr["rule_id"])
            stats["guardrails"] += 1

    # ── Extract guardrails from docs/superpowers/ (specs + plans) ─────────────
    superpowers_dir = root / "docs" / "superpowers"
    if superpowers_dir.exists():
        for gr in _extract_guardrails_from_superpowers(superpowers_dir, root, mapped):
            kg.upsert_guardrail(
                gr["rule_id"], gr["title"], gr["source_file"], gr["pillar"]
            )
            seen_guardrails.add(gr["rule_id"])
            stats["guardrails"] += 1

    # ── Purge Guardrail nodes this walk did not produce ───────────────────────
    # A design, review, RFC or `.cursorrules` pillar becomes a Guardrail node,
    # and nothing removed one: delete the document and the node stayed forever,
    # read by fetch_subgraph_context_window as a rule still in force.
    #
    # After the three extractions, never beside the file purge above — run it
    # before them and it deletes everything this run is about to add. Filtered
    # by node type, because ProductionIncident nodes come from
    # inject_production_learning rather than from a walk, and "not seen" alone
    # would delete another tool's data (.agent-rfc/designs/kg-purges-guardrails.md).
    stale_guardrails = [
        node_id
        for node_id, attrs in kg._g.nodes(data=True)
        if attrs.get("node_type") == "Guardrail" and node_id not in seen_guardrails
    ]
    for node_id in stale_guardrails:
        kg.remove_node(node_id)
        stats["purged"] += 1
        if verbose:
            print(f"  🗑  Purged stale guardrail: {node_id}")

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Map codebase into Knowledge Graph")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Re-parse every file, ignoring the mtime skip (repairs a wrong graph)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress the summary line (CI usage)",
    )
    args = parser.parse_args()

    stats = run_map(verbose=args.verbose, force=args.force)
    if not args.quiet:
        print(json.dumps({"status": "ok", **stats}, indent=2))
