---
status: done
scope:
  - workflow-templates/agentsmith-gates.yml
  - workflow-templates/agentsmith-sync.yml
  - runtime/cli.py
  - scripts/mutation_check.py
  - scripts/test/**
  - docs/process-gates.md
  - docs/UserManual.md
  - docs/PRODUCT_BACKLOG.md
  - CHANGELOG.md
  - .agent-rfc/fixtures/knowledge_graph.json
---
# A tenant checks the provider out whether or not it is private

Owner, 2026-09-25: AgentSmith is about to go public again. Before that flip, the thing the tenants
depend on has to be true.

## Problem

`.agent-rfc/designs/governance-providers.md` records decision 4: *"the gate workflow uses the token
when it is set and a plain checkout when the provider repository is public, so going public later
removes a step without changing a tenant."* That decision is not implemented. Both tenant-facing
workflows pass the secret unconditionally:

- `workflow-templates/agentsmith-gates.yml` — `token: ${{ secrets.AGENTSMITH_READ_TOKEN }}`;
- `workflow-templates/agentsmith-sync.yml` — the same on its checkout, and `GH_TOKEN` on the
  `releases/latest` lookup.

An unset secret renders as the **empty string**, which does not fall back to the workflow's default
token — it replaces it. So on the day AgentSmith goes public, a tenant that does the sensible thing
and removes a secret it no longer needs gets a broken checkout, and a tenant that keeps it is
carrying a credential for a public repository. The comment at the top of the gates workflow states
"AgentSmith is private" as a fact about the world, which it is about to stop being.

This was reviewed and passed. `.agent-rfc/reviews/governance-providers.md` Pass 3 asserted that all
four recorded decisions hold; three were checked against the code and this one was taken from the
decision list. A decision list is a plan, not evidence — that is the finding, and the review is
corrected in the same commit.

## Approach

### The token becomes an optimisation, not a requirement

`${{ secrets.AGENTSMITH_READ_TOKEN || github.token }}` in all three places. GitHub expressions treat
the empty string as falsy, so:

- **private AgentSmith, secret set** — unchanged, the fine-grained token reads it;
- **public AgentSmith, no secret** — `github.token` is issued to every run and can read any public
  repository, so the checkout and the release lookup both work with nothing configured;
- **private AgentSmith, no secret** — still fails, and must: `github.token` is scoped to the tenant
  and cannot read another private repository. The error a tenant sees names the secret.

That is what makes the flip a no-op for tenants in both directions. A repository adopted while
AgentSmith is public keeps working if it ever goes private again, once the secret is set.

### The workflows stop asserting a fact that can change

The comment says AgentSmith is private. It becomes a statement about what the token is *for* — a
private provider — so the file does not go stale the moment the flip happens. Same for the manual,
`docs/process-gates.md`, and the message `runtime/cli.py` prints after adoption, which currently
tells every tenant the secret is needed.

### What this does not do

It does not remove the secret from anything, or make the repository public. The owner flips
visibility; this makes the flip safe to do.

## Pillars

- P1 applies — this design precedes the code and names the decision it repairs, in `.agent-rfc/designs/governance-providers.md`.
- P2 applies — no dependency added; the change is an expression fallback in `workflow-templates/agentsmith-gates.yml` and `workflow-templates/agentsmith-sync.yml`.
- P3 n/a — no traced execution path.
- P4 applies — tests first in `scripts/test/test_workflow_template_wiring.py`: every checkout of the provider falls back, and no template states its visibility as a fact. The `framework_sync` mutation suite gains that file and a mutation that puts the bare secret back (`scripts/mutation_check.py`).
- P7 n/a — no typed boundary; the workflows are data the tests parse.
- P8 n/a — no telemetry.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — nothing executes content the tenant supplies; `workflow-templates/agentsmith-gates.yml` still runs only the framework's own checked-out code.
- P12 applies — the credential is named, never valued, and this change makes it **optional** rather than storing it more widely: a public provider needs no secret in any tenant (`workflow-templates/agentsmith-gates.yml`).
- P13 applies — no check gets weaker. `workflow-templates/agentsmith-gates.yml` still runs the gate from a checkout of the pinned release; only how that checkout authenticates changes, and a private provider without the secret still fails closed. `test_the_provider_checkout_falls_back_to_the_runs_own_token` sweeps both templates so the fallback cannot be dropped from one of them.
- P14 applies — `.agent-rfc/fixtures/knowledge_graph.json` is re-pinned with this change.
- P15 applies — a failed checkout of a private provider still names `AGENTSMITH_READ_TOKEN`, so "no secret" and "wrong secret" do not collapse into one message (`workflow-templates/agentsmith-sync.yml`).
- P16 applies — the fallback IS the recovery path: when the secret is absent the run continues on `github.token` rather than stopping, and when that cannot read the provider the error says which secret to set.

## Deviations

none

## Dependencies

None added.

## Levers

- `declared-vs-enforced` — a decision recorded in a design that no code implemented, found by reading the code back against the decision.
- `provenance-and-precedence` — two credentials can authenticate this checkout; the tenant's own secret wins, and the run's default token is the fallback.
- `denied-vs-missing` — "no secret, public provider, fine" and "no secret, private provider, blocked" stay different outcomes with different messages.
- `environment-parity` — a tenant behaves the same whether the provider it points at is public or private.
- `docs-match-behaviour` — three documents and one CLI message state the provider's visibility as a fact; they become statements about what the secret is for.
