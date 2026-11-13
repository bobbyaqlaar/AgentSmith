#!/usr/bin/env python3
"""scripts/trace_graph.py — a traceability graph from requirement to commit, file and test
(.agent-rfc/designs/pass3-root-causes.md; phase 0 of .agent-rfc/designs/traceability-graph.md).

    trace_graph.py [--out PATH] [--since REF]

Report only: it decides nothing and no gate reads it. It joins what the repository
already holds and says how each link is known:

    observed  git says so (a commit's trailers, the files it changed)
    declared  a file says so (a backlog evidence column, a catalogue mechanism, a scope)
    derived   computed from the two above (imports from the knowledge graph, design → file
              through the commits that cite it, test → file through imports)
    inferred  a reading by this script (requirement → design through the files both touch);
              no requirement links to a design in the repository yet

Imports come from `.agent-rfc/fixtures/knowledge_graph.json`, never resolved a second time
here. Written by the third review of 4.1.0 as a throwaway, and kept at the owner's request.
"""

from __future__ import annotations

import argparse
import collections
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

OUT = ".agent-rfc/fixtures/trace_graph.json"
SRC_EXT = (".py", ".ts", ".tsx", ".js", ".mjs", ".sh")
KINDS = ("observed", "declared", "derived", "inferred")
ENTRY = re.compile(
    r"portal/app/.*/(page|route|layout|loading|error|not-found)\.tsx?$|portal/app/(page|layout|not-found|error|global-error)\.tsx$"
    r"|portal/(proxy|instrumentation|next\.config|postcss\.config|tailwind\.config|eslint\.config)[^/]*$|portal/scripts/"
    r"|__init__\.py$|^hooks/|^\.githooks/|conftest\.py$|next-env")


def is_test(path: str) -> bool:
    return bool(re.search(r"(^|/)(test|tests)/|(^|/)test_[^/]*\.py$|\.test\.tsx?$|(^|/)conftest\.py$", path))


class Builder:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = []
        self.tracked = [f for f in self.git("ls-files").splitlines() if f]
        self.tset = set(self.tracked)

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, check=True).stdout

    def node(self, ident: str, kind: str, **fields: object) -> None:
        self.nodes[ident] = {"id": ident, "type": kind, **fields}

    def edge(self, source: str, target: str, kind: str, how: str, **fields: object) -> None:
        assert how in KINDS, how
        self.edges.append({"from": source, "to": target, "type": kind, "kind": how, **fields})

    def lines(self, path: str) -> int:
        try:
            with (self.root / path).open(encoding="utf-8", errors="ignore") as handle:
                return sum(1 for _ in handle)
        except OSError:
            return 0

    # ── files and imports, from the knowledge graph ──
    def code(self) -> dict[str, set[str]]:
        kg = json.loads((self.root / ".agent-rfc/fixtures/knowledge_graph.json").read_text(encoding="utf-8"))
        kgfiles = {n["id"]: n for n in kg["nodes"] if n.get("node_type") == "CodebaseFile"}
        for f in self.tracked:
            if f.endswith(SRC_EXT) or f in kgfiles:
                self.node(f, "test" if is_test(f) else "file", loc=self.lines(f), in_kg=f in kgfiles,
                          symbols=len(kgfiles.get(f, {}).get("symbols", [])))
        imports: dict[str, set[str]] = collections.defaultdict(set)
        for e in kg["edges"]:
            if e["source"] in self.tset and e["target"] in self.tset and e["source"] != e["target"]:
                imports[e["source"]].add(e["target"])
                self.edge(e["source"], e["target"], "imports", "derived")
        return imports

    # ── requirements: the backlog's table and the compliance catalogue ──
    def requirements(self) -> list[str]:
        backlog = (self.root / "docs/PRODUCT_BACKLOG.md").read_text(encoding="utf-8")
        ids = []
        if "### The requirements, and where each stands" in backlog:
            table = backlog.split("### The requirements, and where each stands", 1)[1].split("\n---", 1)[0]
            for line in table.splitlines():
                if not line.startswith("| ") or line.startswith(("| Requirement", "|---")):
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                rid = f"REQ-B{len(ids) + 1}"
                evidence = re.findall(r"`([^`]+)`", cells[2]) if len(cells) > 2 else []
                self.node(rid, "requirement", title=cells[0], source="docs/PRODUCT_BACKLOG.md requirements table")
                ids.append(rid)
                for path in evidence:
                    hits = [f for f in self.tracked if f == path or f.startswith(path.rstrip("/") + "/")]
                    self.edge(rid, path, "evidence", "declared", resolves=len(hits))
        catalogue = json.loads((self.root / "fixtures/compliance/catalogue.json").read_text(encoding="utf-8"))
        checks = (self.root / "scripts/compliance_checks.py").read_text(encoding="utf-8")
        check_names = set(re.findall(r'"([\w-]+)":\s*\w+,', checks.split("CHECKS:", 1)[-1]))
        for row in catalogue:
            self.node(row["id"], "requirement", title=row.get("title"), source="fixtures/compliance/catalogue.json",
                      layer=row.get("layer"), mechanism=row.get("mechanism"), blocks=row.get("blocks"))
            ids.append(row["id"])
            mechanism = row.get("mechanism") or ""
            if mechanism.startswith("release:"):
                cited = mechanism.split(":", 1)[1]
                self.edge(row["id"], cited, "evidence", "declared", resolves=int(cited in self.tset))
            elif mechanism.startswith("check:"):
                name = mechanism.split(":", 1)[1]
                self.edge(row["id"], "scripts/compliance_checks.py", "evidence", "declared", check=name,
                          resolves=int(name in check_names))
            elif mechanism:
                self.edge(row["id"], f"mechanism:{mechanism}", "evidence", "declared", resolves=1)
        return ids

    # ── designs and reviews ──
    def records(self) -> None:
        for f in self.tracked:
            if f.startswith(".agent-rfc/designs/") and f.endswith(".md"):
                text = (self.root / f).read_text(encoding="utf-8")
                front = re.match(r"---\n(.*?)\n---\n", text, re.S)
                status = scope = None
                if front:
                    found = re.search(r"^status:\s*(\S+)", front.group(1), re.M)
                    status = found.group(1) if found else None
                    scope = re.findall(r"^\s+-\s+(\S.*)$", front.group(1), re.M)
                scope = scope or []
                unmatched = [g for g in scope if not any(t == g or fnmatch.fnmatch(t, g) for t in self.tracked)]
                self.node(f, "design", status=status, scope=scope, scope_unmatched=unmatched)
            elif f.startswith(".agent-rfc/reviews/") and f.endswith(".md"):
                text = (self.root / f).read_text(encoding="utf-8")
                passes = re.findall(r"^## Pass (\d+) — findings: (\d+)", text, re.M)
                self.node(f, "review", passes=[[int(a), int(b)] for a, b in passes], signoff="## Sign-off" in text)

    # ── commits, from git ──
    def commits(self, since: str) -> dict[str, set[str]]:
        fmt = ("%x1e%H%x00%s%x00%(trailers:key=Design,valueonly,separator=%x2C)"
               "%x00%(trailers:key=Review,valueonly,separator=%x2C)")
        raw = self.git("log", f"--format={fmt}", "--name-only", "HEAD")
        in_range = set(self.git("rev-list", f"{since}..HEAD").split()) if since else set()
        changed: dict[str, set[str]] = {}
        for record in raw.split("\x1e")[1:]:
            head, _, rest = record.partition("\n")
            sha, subject, designs, reviews = head.split("\0")
            cid = f"c:{sha[:10]}"
            files = {x for x in rest.splitlines() if x.strip()}
            changed[cid] = files
            self.node(cid, "commit", subject=subject, in_range=sha in in_range, files=len(files),
                      fix=subject.startswith("fix"))
            for d in filter(None, (x.strip() for x in designs.split(","))):
                self.edge(cid, d, "implements", "observed", resolves=int(d in self.tset))
            for r in filter(None, (x.strip() for x in reviews.split(","))):
                self.edge(cid, r, "reviewed_by", "observed", resolves=int(r in self.tset))
            for f in sorted(files):
                self.edge(cid, f, "changes", "observed")
        return changed

    def build(self, since: str) -> dict:
        imports = self.code()
        requirement_ids = self.requirements()
        self.records()
        changed = self.commits(since)

        # design → file, through the commits that cite the design (derived)
        cites = collections.defaultdict(set)
        for e in self.edges:
            if e["type"] == "implements":
                cites[e["from"]].add(e["to"])
        built = collections.defaultdict(set)
        designs_of = collections.defaultdict(set)
        for commit, designs in cites.items():
            for d in designs:
                for f in changed.get(commit, ()):
                    if f.startswith(".agent-rfc/") or f in ("CHANGELOG.md", "docs/PRODUCT_BACKLOG.md"):
                        continue
                    built[d].add(f)
                    designs_of[f].add(d)
        for d, files in built.items():
            for f in sorted(files):
                self.edge(d, f, "built", "derived")
        # test → file, through imports (derived)
        tests_of = collections.defaultdict(set)
        for source, targets in imports.items():
            if is_test(source):
                for t in targets:
                    if not is_test(t):
                        tests_of[t].add(source)
                        self.edge(source, t, "exercises", "derived")
        # requirement → design, through the files both touch (inferred)
        evidence = collections.defaultdict(set)
        for e in self.edges:
            if e["type"] == "evidence":
                prefix = e["to"].rstrip("/") + "/"
                evidence[e["from"]] |= {f for f in self.tracked if f == e["to"] or f.startswith(prefix)}
        matrix = {}
        for rid in requirement_ids:
            files = evidence.get(rid, set())
            designs = set().union(*(designs_of.get(f, set()) for f in files)) if files else set()
            for d in sorted(designs):
                self.edge(rid, d, "designed_by", "inferred")
            code = {f for f in files if not is_test(f) and f.endswith(SRC_EXT)}
            tests = {f for f in files if is_test(f)} | set().union(*(tests_of.get(f, set()) for f in code))
            matrix[rid] = {"title": self.nodes[rid].get("title"), "evidence_files": len(files), "designs": len(designs),
                           "code_files": len(code), "tests": len(tests)}

        imported = collections.defaultdict(set)
        for source, targets in imports.items():
            for t in targets:
                imported[t].add(source)
        sources = [f for f, n in self.nodes.items()
                   if n["type"] == "file" and not f.startswith(".github/scratch-tenants/")]
        hot = collections.Counter()
        for commit, files in changed.items():
            if self.nodes[commit]["in_range"] and self.nodes[commit]["fix"]:
                hot.update(f for f in files if self.nodes.get(f, {}).get("type") in ("file", "test"))
        summary = {
            "counts": dict(collections.Counter(n["type"] for n in self.nodes.values())),
            "edges": dict(collections.Counter(f"{e['type']}:{e['kind']}" for e in self.edges)),
            "requirements": matrix,
            "requirements_without_design": sorted(r for r, m in matrix.items() if not m["designs"]),
            "requirements_without_test": sorted(r for r, m in matrix.items() if not m["tests"]),
            "designs_never_cited": sorted(d for d, n in self.nodes.items() if n["type"] == "design" and d not in built
                                          and not any(e["to"] == d and e["type"] == "implements" for e in self.edges)),
            "designs_with_unmatched_scope": {d: n["scope_unmatched"] for d, n in self.nodes.items()
                                             if n["type"] == "design" and n["scope_unmatched"]},
            "dangling_trailers": sorted({e["to"] for e in self.edges
                                         if e["type"] in ("implements", "reviewed_by") and not e["resolves"]}),
            "files_no_importer_or_entry": sorted(f for f in sources if not imported.get(f) and not ENTRY.search(f)),
            "files_no_test": sorted(f for f in sources if f.endswith((".py", ".ts", ".tsx")) and not tests_of.get(f)
                                    and not ENTRY.search(f)),
            "files_no_design": sorted(f for f in sources if not designs_of.get(f)),
            "hot_fixes_since": hot.most_common(30),
        }
        return {"about": __doc__.split("\n\n", 1)[0], "built_from": self.git("rev-parse", "--short=10", "HEAD").strip(),
                "since": since, "kinds": list(KINDS), "nodes": sorted(self.nodes.values(), key=lambda n: n["id"]),
                "edges": sorted(self.edges, key=lambda e: (e["type"], e["from"], e["to"])), "summary": summary}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--out", default=OUT)
    parser.add_argument("--since", default=None,
                        help="the release whose fixes count as hot spots (default: the latest tag)")
    args = parser.parse_args(argv)
    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                               check=True).stdout.strip())
    builder = Builder(root)
    since = args.since or subprocess.run(["git", "-C", str(root), "describe", "--tags", "--abbrev=0"],
                                         capture_output=True, text=True, check=False).stdout.strip()
    document = builder.build(since)
    out = root / args.out
    out.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")
    s = document["summary"]
    print(f"trace graph at {document['built_from']}: {s['counts']}; "
          f"{len(s['requirements_without_design'])} requirement(s) with no design, "
          f"{len(s['files_no_design'])} file(s) no design built; wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
