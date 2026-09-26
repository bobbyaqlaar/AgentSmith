---
status: done
scope:
  - README.md
  - runtime/cli.py
  - scripts/test/test_tenant_adopt.py
  - docs/UserManual.md
  - docs/DESIGN.md
  - docs/process-gates.md
  - docs/PRODUCT_BACKLOG.md
  - CHANGELOG.md
---
# The front door describes the architecture that shipped

Owner, 2026-09-25/26: "Is documentation current? Should we run one more review pass?" — then, on the
answer: rewrite the front door. AgentSmith goes public, and `README.md` becomes what a stranger
reads first.

## Problem

A documentation-currency pass found four things, two of them tied to the flip.

1. **Three surviving copies of a note that is about to become false.** `README.md:141`,
   `docs/UserManual.md:59` and `:1341` all say *"While this repository is private (until it is
   product-ready) the release URL below returns 404"*. The `public-provider-checkout` slice fixed a
   fourth at `:791` and missed these, because the sweep grepped `AgentSmith is private` and these
   say `this repository is private`. A sweep that cannot match its own siblings.
2. **Going public unblocks the enforcement the gates have never had.** `docs/process-gates.md`
   states as current fact that "a private repository on a free plan does not have [branch
   protection]", and `docs/PRODUCT_BACKLOG.md` carries "**the process gates report a bad push; they
   cannot refuse one**", whose trigger is *"upgrading to Pro or making the repo public"*. After the
   flip `process-gates` can be a required check on `main`. Both statements go false, and the
   opportunity is worth more than the correction.
3. **`providers.json` is in no user-facing document.** Not `README.md`, not `docs/UserManual.md`,
   not `docs/DESIGN.md`. It is the file that declares who governs a repository — the centre of the
   architecture closed out yesterday — documented only in `contract/gate/v1/protocol.md` and in
   design records nobody outside this repository reads.
4. **`README.md` documents only the vendored path.** Its onboarding is `git init` → `touch
   .agenticframework/enabled` → `git checkout` → "vendored scripts/ + runtime/". `tenant adopt`,
   `agentsmith sync`, `agentsmith gate` and `conformance` appear nowhere in 306 lines. A visitor
   with an existing repository — the common case — is told the wrong thing by omission.

## Approach

### The front door leads with the contract, not with the copy

A new section before Quick Start: **how a repository is governed**. A repository declares a provider
in `.agenticframework/providers.json`; the hooks resolve it at run time; AgentSmith is the reference
implementation of `contract/gate/v1`, and `agentsmith conformance --provider "<command>"` is how any
other platform proves it satisfies the same contract. That is the architecture, and it is what makes
the rest of the README something other than a feature list.

### Two onboarding paths, the common one first

`agentsmith tenant adopt` — an existing repository, nothing vendored into it — becomes the primary
Quick Start. The opt-in vendoring path stays, named as what it is: the transport for a repository
that wants the framework's code in its tree, kept working deliberately and not the default.

### Staying current is one merged pull request

The claim worth making, and the one the closing review established: everything a tenant holds is
framework-owned, hash-verified, and proposed weekly by `agentsmith-sync.yml`. A major AgentSmith
release costs a tenant one merged PR.

### Honest about the boundary

Only the gate port is declared and resolved; contract v1 covers three events (`session-start`,
`pre-edit`, `stop`), so a third-party provider can govern an editing session and not yet a commit.
The five-port table says which is which. A front door that oversells is worse than one that omits,
because the second is fixed by reading further and the first by losing trust.

### The two flip-tied corrections

The three stale install notes go. The branch-protection statements become what they are after the
flip — an action available, not a limitation — and the backlog item's trigger is marked as fired,
with what to do about it.

## Pillars

- P1 applies — this design precedes the edit and names the four findings it answers, recorded in `.agent-rfc/reviews/public-front-door.md`.
- P2 applies — no dependency and no new document: `README.md` is restructured, and `docs/DESIGN.md` gains the provider declaration beside the architecture it already describes.
- P3 n/a — documentation only; no execution path.
- P4 applies — the README's claims were checked by ADOPTING a throwaway repository, not by reading the templates, which is what found the `_templates_dir` precedence defect. `test_the_gates_workflow_runs_the_gate_from_a_framework_checkout` in `scripts/test/test_tenant_adopt.py` is strengthened to require the token fallback in the file a tenant receives.
- P7 applies — one code change, `_templates_dir` in `runtime/cli.py`: candidate order only, no new type or boundary.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 n/a — no untrusted content is read.
- P12 applies — `README.md` and `docs/UserManual.md` name `AGENTSMITH_READ_TOKEN` as optional and never carry a value.
- P13 applies — no check changes. The branch-protection correction makes an enforcement **available** that the documents said was not; nothing is weakened, and the design states that requiring `process-gates` on `main` is the owner's action.
- P14 n/a — no fixture or baseline; the knowledge graph indexes code, and no code changes.
- P15 applies — the five-port table distinguishes "declared and resolved" from "a contract in place", so a reader cannot mistake the second for the first (`README.md`).
- P16 applies — both onboarding paths stay documented, so a repository on the vendored transport has somewhere to read about itself. `_templates_dir` still falls back to the machine install when a checkout has no `workflow-templates/`, which is the vendored-tenant case (`runtime/cli.py`).

## Deviations

none

## Dependencies

None added.

## Levers

- `docs-match-behaviour` — four documents state things that are either already false or false the moment the repository flips.
- `grep-for-siblings` — the finding that started this: one note fixed, three identical ones left, because the sweep matched the wrong phrase.
- `declared-vs-enforced` — the README must not present the four unresolved ports as if they were resolved.
- `single-source-of-truth` — `providers.json` is described once, in `docs/DESIGN.md`, and pointed at from the README rather than re-explained.
- `intuitive-journey` — the first path a visitor reads should be the one most of them need.
