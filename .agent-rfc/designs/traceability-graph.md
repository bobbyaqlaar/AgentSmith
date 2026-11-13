---
status: proposed
scope:
  - contract/trace/**
  - scripts/trace_graph.py
  - scripts/gate_models.py
  - scripts/process_gate.py
  - scripts/send_dev_record.py
  - agentsmith/cli.py
  - portal/lib/trace*.ts
  - portal/app/dev/apps/[app]/trace/**
  - portal/app/ops/apps/[id]/trace/**
  - portal/db/schema.sql
  - workflow-templates/agentsmith-gates.yml
  - .github/workflows/self-test.yml
---
# A traceability graph, from requirement to operation, for AgentSmith and every tenant

A programme-level design, written 2026-11-13 at the owner's request, for the owner to review. The gate reads only
`active` designs, so this document authorises no edit: once approved it becomes `approved`, and each phase below is
built under its own `active` design scoped to what that phase touches, as `portal-control-plane.md` was.

## The owner's intent

In the owner's words (2026-11-13): the knowledge graph should not only make the impact of a change easy to see, for
designing, building and testing it, but also give the **traceability matrix from requirements to design to build to
test to operate**, so that people act on it. It is for AgentSmith's own repository and, as a framework, for every
tenant; and the tenant's viewer belongs in the **Ops Portal**, to find defects quickly in production.

## Decisions for the owner

These are the choices this design makes provisionally. Each is marked where it is used.

- **D1. Two graphs, one model.** The knowledge graph that `agentsmith gate kg impact` reads stays as it is: a code
  graph whose hash the commit gate recomputes. Traceability is a separate document built from the same sources, with
  the code graph as one of its layers. The alternative, growing `knowledge_graph.json`, is rejected below.
- **D2. Requirements get ids, and the compliance obligations are already requirements.** A tenant writes
  `.agent-rfc/requirements.yaml`; AgentSmith writes its own the same way. `OB-*` obligations from the catalogue join
  as requirements without being copied.
- **D3. A design names its requirements**, as a `requirements:` field in its front matter, and the gate refuses an
  active design that names none (after a migration period, D7).
- **D4. Every link says how it is known**: observed, declared or derived. The matrix shows the difference.
- **D5. The trace is built per commit in CI and sent through the existing Dev ingest.** The portal joins it to runs
  and incidents by commit. Nothing new leaves the tenant's machines.
- **D6. Incidents gain a link to the run or commit they concern** (today they carry neither).
- **D7. Migration.** Existing designs are not rewritten. For one release, a design without `requirements:` is listed
  as a gap, not refused.

## Problem

### What exists, and what it already links

| Link | Where it lives today | Kind |
|---|---|---|
| file → file (imports) | `.agent-rfc/fixtures/knowledge_graph.json`: 468 files, 246 `IMPORTS` edges | derived |
| design and review records | the same file: 134 designs, 145 reviews, as nodes with no edges | declared |
| design → files it may touch | each design's `scope:` globs, read by the edit gate, not by the graph | declared |
| commit → design, review | `Design:` and `Review:` trailers, checked by the commit gate and CI; ingested per commit (`dev_commits.design`, `.review`) | observed |
| commit → agent, tokens | `Agent:` and `Agent-Tokens:` trailers | observed |
| design → owner approval | `.agenticframework/approvals.jsonl`, cited by deviations | observed |
| obligation → evidence | `fixtures/compliance/catalogue.json`: `mechanism` (`check:`, `release:<test file>`, `SEC-*`, `declaration:`) | declared |
| run → commit | `agent_runs.app_commit`, reported from `APP_COMMIT`; the portal's run view links run, commit, design and approvals | observed |
| requirement → anything | prose only: the backlog's requirements table, each design's `## Problem`, intake records | none |
| test → file or requirement | none: a test's name and a design's review describe it | none |
| manual section → design | none: the manual's 138 sections have no ids anything cites | none |
| incident → run or commit | none: `incidents` holds title, severity and details | none |

The links that matter most for the matrix (requirement → design, test → anything, manual → anything,
incident → anything) are the ones that do not exist. The links that do exist are spread across five stores and three
formats.

### Why `knowledge_graph.json` should not simply grow

- **It is the commit gate's input.** `kg impact` takes the changed files and one hop of dependents, and the sign-off's
  `KG query:` hash is recomputed from that set at every commit. A design's scope often covers a folder
  (`scripts/**` is 175 files), so adding scope edges would pull a design into every change under it, and through it
  most of the repository. Every hash would change, and impact lists would stop meaning anything.
- **A scope is a permission, not a fact.** What a design built is the set of commits that cite it. A matrix that shows
  scope as "implemented by" overstates the trace by an order of magnitude (the viewer derived 6,898 scope links; the
  commits that cite a design touch far fewer files).
- **It is regenerated from file modification times** (`last_modified`), which the second-pass review found makes the
  check rewrite the tracked file. That is tolerable for a cache and wrong for a record people act on.

### What the current data already shows

Of 134 designs, 18 cover no source file. Eleven are release designs and two are CI designs whose scope names
`pyproject.toml`, `install-ai-stack.sh` and workflow files, which the code graph does not model. Three
(`governance-contracts`, `governance-providers`, `compliance-readiness`) are umbrella designs whose scope is
themselves; `compliance-readiness` is active and names 23 source files in its text and none in its scope. One
(`version-marker-test`) scopes `runtime/test/test_cli.py`, which no longer exists. None of the 18 cites a step of the
operations manual, and only three mention the manual at all. A traceability graph should surface each of these as a
gap, not hide them.

## Approach

### The model (`contract/trace/v1`)

One document per commit, `trace.json`, versioned like the other contracts (`schema_version`, additive changes only
within v1).

**Nodes**, each with a stable id:

| Type | Id | Source |
|---|---|---|
| `requirement` | `REQ-<n>` from `.agent-rfc/requirements.yaml`; `OB-*` from the compliance catalogue | declared by the owner; the catalogue |
| `design` | its path | `.agent-rfc/designs/*.md` front matter |
| `review` | its path | `.agent-rfc/reviews/*.md`, with its last pass and sign-off |
| `commit` | the SHA | git, with its trailers |
| `file` | its path, every tracked file (not only code) | git; language and symbols from the code graph where it has them |
| `test` | `path::name` (pytest node id; `path > name` for Node's runner) | the test runner's collection |
| `gate` | the gate step, as Self-Test tags it (`# agentsmith:gate`) | the workflow files |
| `manual` | `docs/UserManual.md#<anchor>` | the manual's headings |
| `release` | the tag | git |

**Edges**, each with a `kind` (D4):

| Edge | From → to | Kind | How it is known |
|---|---|---|---|
| `satisfies` | design → requirement | declared | the design's `requirements:` (D3) |
| `refines` | requirement → requirement, design → design | declared | `parent:` in the requirements file; a design's `parent:` for umbrella designs |
| `authorises` | design → file | declared | `scope:` globs, expanded against tracked files |
| `implements` | commit → design | observed | `Design:` trailer the gate accepted |
| `reviewed_by` | commit → review | observed | `Review:` trailer |
| `changes` | commit → file | observed | git |
| `imports` | file → file | derived | the code graph |
| `covers` | test → file | observed | per-test coverage (phase 3); until then, none |
| `verifies` | test → requirement | declared | a marker on the test (`@pytest.mark.requirement("REQ-12")`) or the obligation's `release:` mechanism |
| `evidences` | file or test → requirement (`OB-*`) | declared | the catalogue's `mechanism` |
| `documents` | design → manual | declared | the design's `manual:` front matter |
| `released_in` | commit → release | observed | git tags |

Two rules keep it honest. A `declared` edge is never drawn as an `observed` one, and the viewer can filter by kind.
A link whose target does not exist (a scope with no file, a requirement id nobody defined, a manual anchor that is
gone) is kept and marked `dangling`, because it is a defect.

### Build side

- **`scripts/trace_graph.py`**, reached as `agentsmith trace build`, writes `trace.json` for a commit from the
  repository, its git history and the code graph. It is deterministic: dates come from git, never from file times.
  It runs in CI after the gates and is sent with the commit's Dev record (`scripts/send_dev_record.py`), so the
  portal holds one per commit, as it already holds the gate's verdict.
- **Gate checks** (each its own phase design):
  - an active design names at least one requirement that exists (D3, D7);
  - every `scope:` path or glob matches a tracked file (would have caught `version-marker-test`);
  - a `manual:` anchor exists in the manual;
  - a test's `requirement` marker names a requirement that exists.
- **`agentsmith trace gaps`** prints the gap list at a terminal, so a developer sees it before the portal does.

### Operate side (the Ops Portal)

- **Ingest.** The trace arrives with each commit's Dev record (tables beside `dev_commits` and
  `dev_design_snapshots`). Runs already carry `app_commit`; incidents gain an optional `run_id` and `app_commit`
  (D6), set when an incident is opened from a run or a dead letter.
- **Three views**, for both the Dev and Ops workspaces, scoped by the existing permissions:
  - **Matrix**: one row per requirement; columns design, review sign-off, commits, tests, last release, deployed
    commit, runs in the last 30 days, open incidents. Each cell is a state, not a count: met, partial, gap.
  - **Defect trace**, from an incident, failed run or dead letter: run → deployed commit → the designs those commits
    implement → their reviews' sign-off claims and the tests that cover the changed files → the requirements. The
    question it answers: which promise did this break, and who reviewed it.
  - **Graph**: the viewer built for AgentSmith's own graph (2026-11-13), reading `trace.json`, with layers by edge
    kind.
- **Gap states**, each a filter and a count on the matrix:
  - a requirement with no design, or no test that verifies it;
  - an active design with no requirement, or a design with no review sign-off;
  - a commit that changed gated files with no design (already a gate failure; shown for commits made with
    `--no-verify`);
  - a file changed but not in any citing design's scope;
  - a deployed commit not reviewed, or a release with an obligation not evidenced;
  - a dangling link of any kind.

### For tenants

The builder ships with the gate and runs in every tenant's CI through `agentsmith-gates.yml`. The contract is the
same, so a tenant's portal reads its own trace exactly as AgentSmith's reads AgentSmith's. Nothing is sent outside the
tenant's network: the trace goes to the tenant's own portal through its own Dev ingest token (sovereign first).

## Phases

Each phase is its own `active` design; this one stays `proposed` until the owner approves it, then `approved`.

1. **Requirements and links in the repository.** `.agent-rfc/requirements.yaml` (AgentSmith's own, seeded from the
   backlog's requirements table and gap list); `requirements:`, `parent:` and `manual:` in design front matter; the
   four gate checks, reporting only for one release (D7); `agentsmith trace build` and `trace gaps`;
   `contract/trace/v1`. Backfill the 20 active designs.
2. **The portal.** Ingest, the matrix, the defect trace and the graph view; the incident link (D6).
3. **Tests as observed evidence.** Per-test coverage contexts (coverage.py's `dynamic_context = test_function`) give `covers`;
   requirement markers give `verifies`. TypeScript tests get file-level coverage first: Node's runner reports
   coverage per run, not per test, which is stated in the matrix.
4. **Tenants.** The builder in the tenant templates; the scratch tenants assert a trace is produced and ingested.

Phase 1 alone makes the matrix answerable at a terminal; phases 2 to 4 make it visible and observed.

## What this does not do

- It does not change `knowledge_graph.json` or `kg impact`, so no commit's `KG query:` changes (D1).
- It does not infer requirements from prose. A requirement exists when someone gave it an id.
- It does not claim a test proves a requirement because the test exists: `verifies` is declared, and `covers` is
  observed only once phase 3 runs coverage.

## Risks and limits

- **Declared links can be wrong.** A design can name a requirement it does not meet. The matrix shows the kind of each
  link, and the review's sign-off is where a person attests it; this design does not pretend otherwise.
- **Volume.** Scope expansion is large (6,898 links today). The document stores globs and their expansion once; the
  views draw scope only on selection, as the viewer does.
- **Two cadences.** Tenants pin framework releases and move at their own pace, so `trace/v1` must stay readable by a
  newer portal for a written window, as `ops/v1` is.
- **Migration effort.** 134 designs exist; only the 20 active ones are backfilled. Done designs stay visible as nodes
  with a "no requirement recorded" gap, which is true.

## Open questions

1. Where tenant requirements come from first: the portal's intake form (`contract/intake/v1`) or the file in the
   repository? This design takes the file as the source and lets the intake seed it.
2. Whether the matrix's "deployed commit" is the latest `app_commit` reported by runs, or a deploy record from
   `cd-production.yml`. Runs are what exist today; a deploy record would be evidence rather than a claim (the first
   review's note on `APP_COMMIT`).
3. Whether gaps should ever block a release (for example, a requirement with no verifying test), or only be shown. This
   design shows them, and leaves blocking to the compliance profile's existing `production` stage.

## Pillars

- P1 applies — the owner's intent, quoted above, is the requirement; `.agent-rfc/designs/traceability-graph.md` is the programme, its requirements seeded from `docs/PRODUCT_BACKLOG.md`, and each phase gets its own design.
- P2 applies — `scripts/trace_graph.py` and `contract/trace/v1` are new; the code graph (`scripts/gate_kg.py`) is reused as a layer, not changed.
- P3 applies — `contract/trace/v1` links runs (traces) to commits, designs and requirements, extending the run-to-commit join in `portal/lib/devRead.ts`; per-test coverage in phase 3 makes test evidence observed.
- P4 applies — each phase design names its tests; the scratch tenants (`.github/scratch-tenants/build.sh`) assert a trace is produced in phase 4.
- P7 applies — `agentsmith trace build` reads Python and TypeScript tests, with symbols from `scripts/gate_kg.py`; TypeScript coverage is per run, not per test, and the matrix says so.
- P8 applies — `scripts/send_dev_record.py` carries the trace with each commit's Dev record to the portal.
- P9 n/a — no multi-agent orchestration changes.
- P10 n/a — no model routing.
- P11 applies — `portal/lib/trace*.ts`, like `portal/lib/devRead.ts` today: commit messages, design titles and test names are repository text shown in the portal, rendered as text, never as markup.
- P12 applies — `scripts/send_dev_record.py` sends the trace with the tenant's existing Dev ingest token; the trace holds paths, ids and SHAs, never file contents or secrets.
- P13 applies — `scripts/process_gate.py` gains the four link checks in phase 1, reporting for one release, then enforcing.
- P14 applies — `scripts/trace_graph.py` takes dates from git, never from file times as `scripts/gate_kg.py` does, so the document does not drift on a fresh checkout.
- P15 applies — `contract/trace/v1`: every edge carries `observed`, `declared` or `derived`, and a missing target is `dangling`, never dropped.
- P16 applies — `contract/trace/v1` is additive within v1, sent by `scripts/send_dev_record.py`; a portal that cannot read a trace shows the commit without it, and says why.

## Deviations

none

## Dependencies

none in phase 1 (the standard library and git). Phase 3 needs `coverage`, which `mutmut` (pinned in
`requirements-lint.txt`) pulls in today without a pin of its own; that phase's design pins it and lists it.

## Levers

- `single-source-of-truth` — requirements get one home and one id; obligations are reused, not copied.
- `provenance-and-precedence` — every link says how it is known, and observed outranks declared.
- `declared-vs-enforced` — a declared link is shown as declared, and the gate checks that what it names exists.
- `implemented-not-invoked` — the trace is built in CI and ingested, not written and left on disk.
- `aggregates-name-their-scope` — every matrix count says which requirements, commits and tests it covered.
- `two-owners-two-cadences` — `trace/v1` is versioned, with a compatibility window for tenants on older releases.
- `failure-is-not-a-result` — "no test", "not measured" and "dangling" are separate states in the matrix.
