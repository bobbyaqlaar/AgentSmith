# Review — a tenant checks the provider out whether or not it is private

Design: `.agent-rfc/designs/public-provider-checkout.md`. Owner, 2026-09-25: "yes, do that slice
before I flip it" — AgentSmith goes public, and the thing tenants depend on has to be true first.

**How it was found.** The owner said they were about to make the repository public. Before advising
on it I read `governance-providers.md` decision 4 back against the code instead of quoting it, and
the code did not implement it. That is the same check Pass 3 of `.agent-rfc/reviews/
governance-providers.md` claimed to have done a few hours earlier and had not; the correction is in
that review, as Pass 4, in this commit.

**Built evidence (2026-09-25):**

- **Failing tests first.** `scripts/test/test_workflow_template_wiring.py` gained two sweeps over
  both provider templates — every use of the secret offers a fallback, and no template states the
  provider's visibility as a fact. Three of the four parametrised cases failed before the change and
  the fourth (`agentsmith-sync.yml`, which never made the claim) passed, which is the sweep working.
- **The fallback, at all three sites**: the gates workflow's checkout, and the sync workflow's
  release lookup and checkout. `${{ secrets.X || github.token }}` — GitHub treats the empty string
  as falsy, so an unset secret now yields the run's own token instead of replacing it with nothing.
- **Mutation-checked**: `framework_sync` gained the wiring test file and a mutation that puts the
  bare secret back. 11 mutations, all caught.

## Pass 1 — findings: 2

1. `denied-vs-missing` — my first pass at the sync workflow's error message left it reading "is
   AGENTSMITH_READ_TOKEN set, with Contents: read?" for every failure of the release lookup. Once
   the secret is optional that question is wrong half the time: against a public provider the
   lookup can fail for reasons that have nothing to do with a secret the tenant should not need.
   Rewritten to "if the provider is private, set AGENTSMITH_READ_TOKEN with Contents: read" — a
   conditional instruction, not an accusation.
2. `docs-match-behaviour` — the change makes a *fourth* site stale that the design had not listed:
   `docs/PRODUCT_BACKLOG.md`'s open item "every release-download install path is broken while
   AgentSmith is private". It is not closed by this slice and must not be marked so — it closes on
   the flip, verified anonymously. Annotated with that, and with the fact that the tenant workflows
   no longer wait on it.

## Pass 2 — findings: 0

Re-read the three expressions and the four prose sites. Considered and declined:

- **Removing `AGENTSMITH_READ_TOKEN` from the templates entirely.** The repository is not public
  yet, no tenant has been told to drop the secret, and a private provider genuinely needs it. The
  fallback makes the secret optional; deleting it would make the private case impossible.
- **Making `runtime/cli.py` detect the provider's visibility and print only the relevant line.**
  That would need a network call during `tenant adopt`, to tell a tenant something that costs one
  clause to say unconditionally.
- **A test asserting what an empty `token:` does to `actions/checkout`.** That is GitHub's
  behaviour, not this repository's, and it cannot be exercised here. The tests assert the fallback
  exists — which is correct whatever an empty token would have done.

**Stated limits:**

- **Still never run on GitHub.** Like everything in these two templates, this is verified by reading
  the workflow as data. The first adopted repository proves it, and the first one adopted *after*
  the flip proves the no-secret path specifically.
- **`SCRATCH_TENANTS_TOKEN` is untouched and still required** — it pushes to other repositories, so
  no fallback applies.
- **The flip itself is the owner's**, and so is verifying afterwards that the anonymous
  release-download path works (`curl -sI` the asset with no credential), which is what closes the
  backlog item this slice only annotated.

## Sign-off (validation-checklist Step 4)

```
Group 1 · DRY & shared code           [x] checked — one expression, three sites, one sweep test that
                                          covers both templates rather than naming each
Group 2 · Quality / safety            [x] checked — a private provider without the secret still
                                          fails, and says which secret
Group 3 · Architecture / hygiene      [x] checked — four prose sites stop asserting a visibility
                                          that is about to change
Group 4 · Process                     [x] checked — the review that passed the unimplemented
                                          decision is corrected in this commit
Group 5 · Intuitive UI                [x] checked — the sync workflow's error tells a tenant what to
                                          do only in the case where it applies
Group 6 · Signal integrity            [x] checked — "no secret needed" and "secret missing" stay
                                          different outcomes
Group 7 · Auth & session integrity    [x] n/a — no cookie, bearer or session; the credential is
                                          named, never valued

Tests added/updated:      scripts/test/test_workflow_template_wiring.py (+2 sweeps, 4 cases)
Mutation-checked:          yes — framework_sync, 11 mutations including a new one that puts the bare
                          secret back, all caught
Fixtures re-pinned:        .agent-rfc/fixtures/knowledge_graph.json
KG query:                 kg:a3ad70301931
Gates run locally:         ruff, mypy in a clean environment, the wiring, sync-workflow, adopt and
                          package-manager suites (75 passed), and the framework_sync mutation suite
Declared gaps:             (1) neither template has ever run on GitHub; (2) the flip and the
                              anonymous-download verification are the owner's
```
