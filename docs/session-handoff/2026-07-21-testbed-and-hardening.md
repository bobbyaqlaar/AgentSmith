# Session Handoff — Testbed Tenant + Framework Hardening

**Date:** 2026-07-21
**Branch:** `main` (sync with `origin/main` before starting)
**State:** framework suite **287 passed / 3 skipped**; KYC Sentinel tenant
**39 passed**, strict security harness exits 0. Both repos committed, clean.

---

## Paste this into a fresh session

```
Repos:
  /Users/mac/Documents/Bobby/Aqlaar/Apps/AgenticFramework   (the framework)
  /Users/mac/Documents/Bobby/Aqlaar/Apps/KYC_Sentinel       (testbed tenant)
Branch: main (both)

What happened this arc (DO NOT redo — all committed):
- Built KYC Sentinel, the E2E testbed tenant from docs/testbed-tenant-spec.md:
  5 agents, 4 model routes, F1–F8 engineered-failure demos. Runs fully offline
  (KYC_FAKE_LLM=1) and against the installed package with no AGENTSMITH_DIR.
- Building it surfaced framework gaps G1–G10; ALL are fixed. Full analysis with
  reproduction + fix notes: AgenticFramework/TestbedFeedback-2026-07-21.md.
- Two earlier framework reviews are also done: ReviewFindings-2026-07-18.md
  (docs↔code sync + perf, P1–P3) and TestCoverageReview-2026-07-21.md
  (test coverage gaps 1–7, all closed).

Framework changes worth knowing (all in CHANGELOG [Unreleased]):
- pyproject.toml → `agentsmith-runtime` is pip-installable; `import runtime`
  is unconditional (no more try/except ImportError fallbacks). scripts/ that
  import runtime add the REPO ROOT to sys.path, not runtime/.
- runtime/testing.py  — FakeGateway/RecordingGateway test doubles.
- runtime/judging.py  — citations_grounded, pair_parity, judge_independence_warning
  (run-evals imports pair_parity; CI gate == per-request check).
- runtime/tracing.py  — agent_span() + per-tool-call spans from ToolRegistry.invoke.
- gateway: complete_stream streams Anthropic + falls back for cloud providers;
  degrade ladder walks to the first FREE tier; CompletionResult.guardrail_counts.
- prompt_guard: PROMPT_GUARD=off|warn|default|strict (blocking default);
  SEC-PROMPT-001 now asserts enforcement, not just detection.
- moderation: declared hook (moderation.hook in tenant.yaml) makes
  MODERATION_HOOK=required satisfiable.
- post-checkout seeds .agent-rfc/security/ from vendored templates (never
  overwrites).

WHAT'S NEXT (the only open work): DEPLOYMENT. See
KYC_Sentinel/DEVLOG.md — the "CI/CD (GitHub) — pending" and
"Deployment — pending" sections are stubs waiting to be filled. Needs GitHub +
GCP credentials (not available in the sandbox this arc was built in).

Also open but optional: docs polish D1/D4 in TestbedFeedback §B; a possible
SEC-MOD-002 split (option c in the G10 write-up).

Verify before deploying:
  # framework
  cd AgenticFramework && PYTHONPATH=scripts:. python3 -m pytest scripts/test runtime/test -q
  # tenant (offline)
  cd ../KYC_Sentinel && AGENTSMITH_DIR=$PWD/../AgenticFramework python3 -m pytest test -q && python3 demo.py all
  # tenant strict security gate
  PROMPT_GUARD=default MODERATION_HOOK=required python3 ../AgenticFramework/scripts/run-security-checks.py --mode ci --strict
```

---

## Deployment starting points (the pending DEVLOG sections)

The framework's own deploy story is the template to follow — it is already
live-verified once (Product_Archive.md §P11): GitHub Actions → GCP Cloud Run
via Workload Identity Federation (keyless).

1. **Push both repos to GitHub.** KYC Sentinel's CI is
   `.github/workflows/ci.yml`; it checks out the framework and
   `pip install -e`'s it. For a published framework, replace that with the
   pinned `agentsmith-runtime @ git+…@v1.0.0` line already commented in
   `KYC_Sentinel/requirements.txt`.
2. **Wire GitHub Actions secrets** per OPERATIONS.md "GitHub Actions secrets"
   (WIF provider, Cloud SQL, provider API keys, `OPS_PORTAL_SYNC_TOKEN`).
3. **Reusable eval workflows** — point the tenant at `eval-scorecard.yml`,
   `eval-fairness.yml`, `eval-hallucination.yml` with `strict: true`.
4. **Deploy** the worker image (`KYC_Sentinel/Dockerfile`, builds from the
   tenant repo alone now) to Cloud Run; stand up Postgres + Temporal + Phoenix
   per OPERATIONS.md §0.
5. **Prove the round-trip** the testbed was built for: trigger `malf-009` →
   parks in DLQ → portal "Replay with edits" → `replay_webhook_server` →
   `temporal_replay` resumes it (F1); trigger `sanc-005` → HITL gate → approve
   in the portal. Then turn on `shadow-eval.py` sampling and watch the first
   production failure become a golden case.

Append results to `KYC_Sentinel/DEVLOG.md` under the pending sections as you go.

## Lessons this arc (don't relearn)

- A test double MORE capable than the real thing hides the bugs a testbed
  exists to find (the fake gateway aliased `complete_stream`→`complete` and
  masked G1 for the whole build). `runtime/testing.py` is deliberately no more
  capable than the real gateway.
- Four gaps were found only by fixing an earlier one (G9←G3, G10←G5, G6's
  scripts breakage, G8's span clobber). Keep the testbed permanently; each
  framework change should be re-run through it before release.
- `regex to restructure source` mangled multi-line imports; use a line-scanner.
