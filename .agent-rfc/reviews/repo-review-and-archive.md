# Review: repo-review-and-archive

The owner's request, 7 Nov: up to four passes over the repository against `docs/design-review-checklist.md` and
`docs/validation-checklist.md`, the documents checked against the code, then an archive of what nothing uses.

**Method, run on every pass:** each backticked path and relative link in the live documents against `git ls-files`;
each documented `agentsmith` command against the CLI's own subcommands; each file ever deleted against live
mentions of it; each tracked file against what refers to it, split into code, workflow, installer, template and
config references versus documents, tests and records. Records (`CHANGELOG.md` entries, `docs/PRODUCT_ARCHIVE.md`,
`docs/REVIEW_LOG.md`, `.agent-rfc/`, the backlog's Lessons appendix) say what was true then and were not edited.

## Pass 1 — findings: 3

1. `docs-match-behaviour` — **`docs/DESIGN.md` Pillar 1 described specs as `NNN-<slug>.md`, and the enterprise rule as
   an RFC *or* an `RFC-NNN` reference.** The process gate requires `.agent-rfc/designs/<slug>.md` and the trailers, and
   `scripts/gate_guardrails.py` requires both enterprise conditions. **Fix:** the bullets say what the gates check.
2. `docs-match-behaviour` — **The manual's "Wire tenant history sync" told every tenant to post to `/api/sync/history`
   from CD or `agentsmith check`,** and the route's header said `cd-staging.yml` and `cd-production.yml` call it.
   Nothing does since `scripts/sync-portal-history.py` was retired; the route is deprecated. **Fix:** the section is
   headed deprecated and says what replaced it; the route's header says nothing ships a sender.
3. `docs-match-behaviour` — **Two manual passages named `/api/runs/ingest` as the worker's run-status path.** With an Ops
   token the gateway sends to `/api/ops/ingest`; the old route is its fallback without one. **Fix:** both name the Ops
   contract and the fallback.

## Pass 2 — findings: 5

`grep-for-siblings` on the shared token and the deprecated routes across every live document and template.

4. **The `.env` templates still set the shared token as needed:** the portal's server block, two tenant examples and
   `portal/.env.example`. **Fix:** the server and portal entries are commented out and marked deprecated; the tenant
   examples set `OPS_PORTAL_TOKEN`, the app's own Ops token.
5. **The tenant GitHub-secrets table listed a "CD → portal history sync" no workflow has,** and left out the pair
   `agentsmith-gates.yml` reads. **Fix:** one row for `AGENTSMITH_PORTAL_URL` and `AGENTSMITH_PORTAL_INGEST_TOKEN`.
6. **`templates/in-app-widget/README.md` said run status goes to `/api/runs/ingest`.** **Fix:** `/api/ops/ingest`, with the app's token.
7. **`docs/DESIGN.md`'s list of portal data sources implied a shipped history sender.** **Fix:** it says the route is
   deprecated and nothing shipped sends to it; the missing sender is a declared gap below.
8. **The widget's Working-state demo imported `llm_gateway` from `.` and used the shared token.** **Fix:** the
   package import and `OPS_PORTAL_TOKEN`; `_report_run_status` sends by the Ops contract when that token is set.

## Pass 3 — findings: 3

`grep-for-siblings` on the two patterns pass 2 found in snippets, and on retired command names.

9. **Two more manual snippets imported runtime modules a tenant no longer holds** (`from dead_letter import`, after
   `sys.path.insert(0, '.')`, and `from llm_gateway import`). **Fix:** `from agentsmith.dead_letter import …` and
   `from agentsmith.llm_gateway import LLMGateway`; both imports run.
10. **`docker-compose.yml` described the token as "used by CD's history-sync step".** **Fix:** the comment says it is
    deprecated; the variable still passes through, since the portal still accepts it.
11. **Live text named retired commands:** `CHANGELOG.md`'s preamble told tenants to upgrade with `ai-stack-upgrade`
    and pin `framework.version` in `tenant.yaml`, and a backlog item named `ai-tenant-init`. **Fix:** the preamble says
    the pin is the setup step `providers.json` declares, moved by `agentsmith sync` and its weekly pull request.

## Pass 4 — findings: 0

- Every check above re-run on the final tree. The only change in the path check is the removed `001-auth-fix.md`
  example; what it still lists is generated rule files, tenant-side files, and paths relative to the on-prem bundle
  or the portal, each read in context.
- No live document names the shared token as needed, `/api/runs/ingest` as the worker's path, or an `ai-*` command.
- The archive (`implemented-not-invoked`, `no-redundant-artifacts`): of 968 tracked files, only two have no reference
  from code, workflows, the installer, templates or config, no directory read whole by a tool, and no live document
  telling a reader to use them. `examples/oil-price-agent/check_model_ids.py` is a one-off model-ID probe for the
  archived demo repository; `assets/LogoAqlaar-Transparent.png` is the source of `portal/assets/brand/aqlaar.png`. Both
  moved with `git mv`. Everything else was checked to have a real caller, including `scripts/verify_judge_route.py`
  (an operator's judge check, its imports resolve), the Helm chart (`--check-onprem-deploy` reads the directory), and
  every portal component and library (each imported by non-test code).

**Declared gaps, on the backlog:** the portal's unresolved-issues view has no shipped sender; the reference example
imports the runtime from a checkout.

## Sign-off

Group 1 · DRY & shared code — [x] checked — two unused files archived; no duplicate found by the reference scan.
Group 2 · Quality / safety — [x] checked — the documents stop sending tenants to a shared token every tenant holds.
Group 3 · Architecture / hygiene — [x] checked — documents match the code across eleven findings; two gaps declared with triggers.
Group 4 · Process — [x] checked — design first; four passes, the last clean; CHANGELOG and backlog.
Group 5 · Intuitive UI — [x] n/a — no screen changes.
Group 6 · Signal integrity — [x] checked — the setup docs no longer present a deprecated path as the working one.
Group 7 · Auth & session integrity — [x] checked — documents only: the shared bearer token is described as deprecated everywhere it is configured.

Tests added: none — the changes are documents, comments and two moves; `scripts/test/test_design_tree_drift.py` holds the tree with `archive/` in it.
Mutation-checked: n/a — no code changes.
Fixtures re-pinned: `.agent-rfc/fixtures/knowledge_graph.json`.
Gates run: the 16 test files that read the edited documents and env examples (193 passed, 2 skipped); `test_ops_contract.py` (21 passed); `docker compose config`; ruff; mypy; py_compile; check-kg; check-hooks; artifacts; the process gate. Not run here: the portal's `npm test`, unaffected by a comment.

Levers reviewed: `docs-match-behaviour`, `no-redundant-artifacts`, `grep-for-siblings`, `implemented-not-invoked`.

KG query: kg:44c857099aa4
