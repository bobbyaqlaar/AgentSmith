---
status: active
scope:
  - runtime/cli.py
  - runtime/architectures.py
  - templates/architectures.yaml
  - scripts/process_gate.py
  - scripts/test/test_governed_tenant.py
  - scripts/test/test_scaffold_review.py
  - runtime/test/test_architectures.py
  - .agent-rfc/fixtures/knowledge_graph.json
---
# A new tenant starts from its architecture, and its first commit can go in

## Problem

`agentsmith tenant init` arms the design and review gates, and the scaffold it writes touches
gated paths — so a new tenant's very first commit is refused for having no design and no review,
and nothing tells the user how to make one. The test named
`test_a_scaffolded_tenant_can_commit_a_governed_change` only asserts the refusal; no test shows a
governed first commit succeeding.

And the scaffold says nothing about the application's shape. `docs/DESIGN.md` is written as
"The living picture of this system" and nothing more, so the first design an agent writes starts
from no structural decision — and structure is the decision every later design depends on.

Owner decisions, 2026-09-18:

1. `tenant init` writes the design, from an input naming the kind of application.
2. Five structural styles, plus an agentic overlay usable with any of them.
3. The scaffold commit passes the review gate only when its files are verifiably what `tenant
   init` wrote — a hash of every file, recorded at scaffold time. Nothing claims a review happened.

## Approach

### Two inputs, framed the way the industry frames them

"Agentic" is a kind of application; layered, hexagonal and the rest are **structural styles**. An
agentic application still has a structure, so they are separate:

- **`--architecture STYLE`** — `layered` (n-tier), `modular-monolith`, `hexagonal` (clean
  architecture, ports and adapters, onion), `microservice`, `event-driven`. The common names are
  accepted as aliases: `clean`, `ports-and-adapters` and `onion` resolve to `hexagonal`, `n-tier`
  to `layered`.
- **`--agentic`** — adds the agent layer on top of the style: agents, tools behind an allowlist,
  every model call through the gateway, durable workflows with a human in the loop, evaluation
  suites with an independent judge, and retrieved content treated as data.

Both are optional. Without `--architecture` the scaffold still writes its design and the first
commit still goes in; the design says no style was chosen, and `docs/DESIGN.md` says to choose one.

### One catalogue

`templates/architectures.yaml` holds every style and the overlay: a name, what the style is for
and when it fits, its layers with where each lives and what each may depend on, its rules, where
its tests go, and what to watch for. Paths are relative to the stack's source root —
`app/` for `python-fastapi`, `src/` for `ts-react`, `internal/` for `go`. `runtime/architectures.py`
loads and validates it (Pydantic) and renders it; nothing else reads it.

### What `tenant init` writes

- **`docs/DESIGN.md › Architecture`** — the chosen style: why, the layers and the direction
  dependencies may point, where tests go, what to watch for; with `--agentic`, **The agent layer**
  and where it sits in that style. A `docs/DESIGN.md` the tenant already has is left alone and the
  run says so — never overwritten without `--force`.
- **`.agent-rfc/designs/scaffold.md`** — the design for the scaffold commit itself: what it sets up,
  every registry pillar answered truthfully for a scaffold (most are "the scaffold adds no code
  this governs; the first design that adds some answers it"), no deviations, no dependencies.
  Its **scope is exactly the files `tenant init` wrote**, and its status is **`done`** — it covers
  the scaffold commit and authorises no edit after it. The next change needs its own design.
- **`.agenticframework/scaffold.json`** — a SHA-256 of every file `tenant init` wrote, with the
  framework version, stack, style and whether it is agentic.
- **One session-start line** in `.agenticframework/process-gates.json` (`extends.session_start`):
  the style and its dependency rule, so every agent session starts knowing the shape.
- The run ends by printing the exact first commit:
  `git commit -m "chore: scaffold <id>" -m "Design: .agent-rfc/designs/scaffold.md" -m "Review: n/a: generated scaffold"`.

### The gate: `Review: n/a: generated scaffold`

Accepted, whatever the commit's size, only when all of:

1. the commit is the repository's **root commit** (no parent);
2. `.agenticframework/scaffold.json` is in it and parses;
3. **every gated file in the commit** is listed in the manifest with a matching SHA-256.

Anything else — an edited scaffold file, an added gated file, a later commit — falls back to the
normal rule, with an error that says which file differs. When it is accepted it is a **note**, not
silence: the commit's verdict is `passed_with_notes`, CI lists it, and the portal's Dev workspace
shows it.

**Stated limit.** The manifest is written by `tenant init` and not signed, so a person who edits a
scaffold file *and* rewrites its hash defeats this — deliberately, once, on the root commit, and
visibly in the manifest. That is the same class of escape as `Design: n/a` for a small change,
which is also self-declared and also listed by CI.

## Pillars

- P1 applies — this design precedes the code; the owner's three decisions are recorded in `.agent-rfc/designs/tenant-architecture.md`.
- P2 applies — no dependency added: YAML is read with `pyyaml` and validated with `pydantic`, both already in `runtime/requirements-runtime.txt`.
- P3 n/a — `tenant init` is a local command with no service path; the gate's own spans are unchanged.
- P4 applies — tests first: `runtime/test/test_architectures.py` for the catalogue and rendering, `scripts/test/test_scaffold_review.py` for the gate rule, and `scripts/test/test_governed_tenant.py` for a first commit that succeeds.
- P7 applies — the catalogue is validated by Pydantic models in `runtime/architectures.py`.
- P8 n/a — no telemetry wiring.
- P9 applies — the agentic overlay records where agents, tools and workflows sit in each style, in `templates/architectures.yaml`; it writes no agent.
- P10 applies — the overlay requires every model call to go through the gateway; recorded in `templates/architectures.yaml`, enforced where it already is.
- P11 applies — the overlay states retrieved content and tool output are data, never instructions, in `templates/architectures.yaml`.
- P12 applies — nothing generated holds a credential; `.agenticframework/scaffold.json` holds hashes of files, not secrets.
- P13 applies — the review escape is narrow (root commit, every gated file hash-verified) and visible as a note; its limit is stated above, in `scripts/process_gate.py`.
- P14 applies — the generated design and manifest are pinned by tests that commit a real scaffold through the real hooks, in `scripts/test/test_governed_tenant.py`.
- P15 applies — "accepted as the generated scaffold" is a note of its own, distinct from a small-change `n/a`, in `scripts/process_gate.py`.
- P16 applies — a scaffold that no longer matches its manifest gets the normal review rule and an error naming the file, never a silent pass (`scaffold_problems` in `scripts/process_gate.py`).

## Deviations

none

## Dependencies

None added.

## Levers

- `design-before-code` — the first commit gets a real design, and the structural decision is written before any code.
- `declared-vs-enforced` — the review escape is enforced by hashes the gate checks, not by the message claiming it.
- `gate-integrity` — the escape is scoped to the root commit and to files the manifest vouches for; an edit falls back to the normal rule.
- `one-catalog` — every style lives in one YAML file, read by one module.
- `test-the-contract` — the tests commit a real scaffold through the real hooks, and assert it succeeds.
- `failure-mode-visibility` — an accepted scaffold is a note CI and the portal show.
