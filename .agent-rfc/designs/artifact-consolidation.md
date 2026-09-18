---
status: done
scope:
  - .agenticframework/process-gates.json
  - templates/**
  - caddy/**
  - docker-compose*.yml
  - install-ai-stack.sh
  - scripts/**
  - runtime/**
  - portal/**
  - hooks/**
  - .githooks/**
  - .github/**
  - enterprise/**
  - examples/**
  - workflow-templates/**
  - fixtures/**
---
# One artifact per type, and each one for its own reader

## Problem

This repo has four documents of two types and eleven strays: `FIXES_AND_CLEANUP.md` and a backlog,
`SPECS.md` and a design, `OPERATIONS.md` and a user manual, three dated review files, three session
handoffs, two `docs/superpowers` plans and their specs. `process_gate.py artifacts` lists 21
problems, and `verify_system.py --governed` reports two of them as provisioning gaps. An agent
opening this repo cannot tell which document governs.

The documents also carry the wrong *kind* of content for their readers. `SPECS.md` is 2,645 lines
in which the current design is interleaved with the history of how it got there — "observed
2026-08-24", "ReviewFindings-2026-07-18 A2 said", an incident and its fix. A person reading it to
understand the system has to separate the two as they go.

And they point at each other by number: 214 references to `SPECS.md` and 110 to `OPERATIONS.md`
across 91 files, many of the form `SPECS.md §30`. <!-- xref: example --> Those numbers move whenever either document is
edited — which this change is about to do to both.

## Approach

**The owner's rule, 2026-09-18, which decides the shape of every move below:**

- **Cross-references between documents are minimised.** Where one is genuinely needed, name a
  *section*, never a number. Most of the 300+ pointers do not survive this migration: a fact worth
  stating is restated where it is needed, and a pointer is kept only where the other document is
  genuinely the place to go.
- **Documentation is for humans to understand without ambiguity.** The logic an agent needs to
  design a change is in the knowledge graph and the code; prose exists to explain the system to a
  person.
- **History lives in the archive and the logs, nowhere else.** `docs/PRODUCT_ARCHIVE.md` holds the
  decision history and `docs/REVIEW_LOG.md` the review history. `docs/DESIGN.md`,
  `docs/UserManual.md` and `README.md` carry the **distilled rationale** — why the system is the
  way it is — and not the record of how it got there.

**The moves**, each one whole-document so nothing is lost in transit:

| From | To | Why |
|---|---|---|
| `FIXES_AND_CLEANUP.md` | `docs/PRODUCT_BACKLOG.md` | it is the backlog |
| `Product_Archive.md` | `docs/PRODUCT_ARCHIVE.md` | it is the archive |
| `UserManual.md` | `docs/UserManual.md` | it is the manual |
| `SPECS.md` | `docs/DESIGN.md` | it is the design |
| `ReviewFindings-*`, `TestCoverageReview-*`, `TestbedFeedback-*` | `docs/REVIEW_LOG.md` | review history |
| `docs/session-handoff/*` | `docs/PRODUCT_ARCHIVE.md` | decision history |
| `docs/superpowers/specs/*`, `docs/superpowers/plans/*` | `docs/DESIGN.md` + archive | a design and its history |
| `docs/observability-audit.md` | `docs/DESIGN.md` + archive | a design and its findings |
| `OPERATIONS.md` | README, `docs/UserManual.md`, `docs/DESIGN.md` | overview, procedures, architecture |

**In two commits, because one is not reviewable.** First the moves and the reference rewrite, with
every `§`-pointer resolved or removed — the repo ends with one file per type and a green
`artifacts` check. Second the distillation: the history that came with `SPECS.md` and
`OPERATIONS.md` moves to the archive, leaving the rationale. Splitting it this way means no step
both moves text and rewrites it, so a reviewer can check each one.

**Not in this change:** `records: single`. Moving `.agent-rfc/designs` and `.agent-rfc/reviews`
into the two artifacts changes the convention every future commit's trailers use, which is a
change to the gate's behaviour rather than to the documents. It is declared reference
documentation in the registry today, so `artifacts` passes without it.

## Pillars

- P1 applies — this note precedes the moves and records the owner's rule that shapes them; the checks it has to satisfy are in `scripts/process_gate.py`.
- P2 applies — no new dependency; the moves are `git mv` and the reference rewrite is a script in `scripts/` run once.
- P3 n/a — documentation, no execution path and no span.
- P4 applies — the contract is mechanical: `process_gate.py artifacts` reports zero, and no reference resolves to a moved path. Both are checked by `scripts/test/test_gate_artifacts.py` and a reference test added here.
- P7 n/a — no models, no handlers, no TypeScript changes beyond comment text.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model calls.
- P11 applies — the documents are data being moved, not instructions being followed; `scripts/process_gate.py` reads them the same way afterwards.
- P12 applies — no credential moves with the text; `docs/process-gates.md` and the security docs stay where they are.
- P13 applies — `artifacts` goes from `report` to `enforce` in the same change, so the check that listed 21 problems starts refusing new ones.
- P14 applies — `SPECS.md`'s repository tree is a pinned baseline read by CI; it moves with the file and the step that reads it moves with it.
- P15 applies — a moved document leaves no stub, so a reference to its old path names nothing rather than something plausible, and `artifact_problems` reports a second copy by name rather than passing it.
- P16 applies — every move keeps its history, so any step is revertible by one commit, and nothing leaves the repo: what is not the current design goes to `docs/PRODUCT_ARCHIVE.md`.

## Deviations

none

## Dependencies

None added.

## Levers

- `no-redundant-artifacts` — one file per type is the whole point.
- `pin-unremovable-duplicates` — the `artifacts` check goes to `enforce`, so a second backlog cannot come back quietly.
- `single-source-of-truth` — a fact is stated where its reader is, rather than pointed at across three documents.
- `docs-match-behaviour` — the commands and paths in the manual are re-read against what the code does while each section moves.
- `provenance-and-precedence` — history moves to the archive and the review log; the design keeps the rationale, so a reader knows which document answers which question.
