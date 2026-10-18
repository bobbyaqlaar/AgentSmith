---
status: active
scope:
  - .agenticframework/process-gates.json
---
# The agentic 42001 coverage page is declared reference documentation

## Problem

`docs/agentic-42001-coverage.md` was committed in `65ecccc` and the artifacts gate reported it:

```
artifacts (enforce): 1 problem(s)
  - docs/agentic-42001-coverage.md is neither an artifact nor declared reference documentation —
    fold it into the artifact that owns it, or declare it in `extends.artifacts.reference`
```

The gate is right, and this is the rule working: a document that is not an artifact of a known type
and is not declared is a document nothing owns — the way a repository accumulates pages no one
maintains. CI enforces the same check, so the commit must not be pushed as it stands.

## Approach

**Declare it, rather than fold it.** The gate offers both. Folding would put a 200-line answer to a
third-party briefing inside `docs/iso-42001-control-map.md`, which is this repository's own thematic
map — two different documents with two different owners of the question. The repository already
keeps `uae-regulatory.md`, `security-framework-map.md` and `iso-42001-control-map.md` apart for the
same reason.

**Declare it repo-locally**, in `.agenticframework/process-gates.json` under
`extends.artifacts.reference`, beside the nine contract protocols — **not** in
`templates/governance.json`. That file is the registry tenants receive: a path listed there is a
path tenants are told about, and this page is about AgentSmith's own coverage. The three ISO and
UAE documents are in the shipped list because a tenant inherits those maps; this one it does not.

One line. No code, no behaviour, no tenant-visible change.

## Pillars

- P1 applies — this note precedes the edit; the gate's own message is quoted in `## Problem`.
- P2 n/a — no dependency; a JSON list gains a string.
- P3 n/a — no runtime path.
- P4 applies — the check is the gate itself: `python3 -m runtime.cli gates run --only "Every gated commit"` and the artifacts run report the problem before the edit and none after. No unit test is added, because the rule being satisfied is `scripts/gate_artifacts.py`'s, already covered by `scripts/test/test_gate_artifacts.py`.
- P7 applies — `.agenticframework/process-gates.json` is read by the Pydantic config model in `scripts/gate_models.py`; the edit keeps the existing shape (a list of path strings under `extends.artifacts.reference`).
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 n/a — no new input is read; the declared path is a file this repository tracks.
- P12 n/a — no credentials.
- P13 applies — this file **is** gate configuration, so the risk is weakening a gate. The change adds one path to a reference allowlist: it does not alter `gated`, `not_gated`, `pillars.mode`, `artifacts` or the changelog paths, and `git diff` on the commit shows exactly one added line.
- P14 n/a — no fixture; the knowledge graph is regenerated because a tracked file changes.
- P15 applies — "undeclared document" and "document of a known type" were the gate's two answers in `scripts/gate_artifacts.py`; declaring `docs/agentic-42001-coverage.md` in `.agenticframework/process-gates.json` resolves it to the second rather than silencing the check.
- P16 n/a — no failure path.

## Deviations

none

## Dependencies

None added.

## Levers

- `declared-vs-enforced` — the page is now owned by the registry that the gate reads, instead of existing outside it.
- `single-source-of-truth` — one declaration, repo-local, where the document actually lives.
- `two-owners-two-cadences` — the tenant-facing registry (`templates/governance.json`) and this repository's own list ship on different cadences; a page only this repository has belongs in the latter.
