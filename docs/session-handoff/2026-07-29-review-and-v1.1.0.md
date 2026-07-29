# Session handoff — cross-repo review → v1.1.0 (2026-07-29)

A review of AgenticFramework + KYC Sentinel (docs↔docs, docs↔code, redundancy,
code quality), then four phases of fixes ending in the framework's first
published release. Findings are closed; this note records what changed and
what a next session should know.

## Where things stand

- **v1.1.0 released** — [the first actually-published version](https://github.com/bobbyaqlaar/AgentSmith/releases/tag/v1.1.0).
  1.0.0 was documented and dated but never tagged, so
  `install-ai-stack.sh`'s `releases/latest/download/*.tar.gz` path 404'd and no
  tenant could pin a version. All five artifacts verified fetchable; the KYC
  Sentinel pin resolves (`pip install --dry-run` → `agentsmith-runtime-1.1.0`).
- **Framework suite 331 passing** (was 289, and a bare `pytest` only ran 171 of
  them). **KYC Sentinel 50 passing**, CI green, adversarial eval gate live.
- **Only open build item:** KYC Sentinel "Running live" — real backends and
  credentials. See `FIXES_AND_CLEANUP.md`.

## The defects worth remembering

Not the full list (that's CHANGELOG 1.1.0) — the ones whose *shape* will recur.

1. **A mandatory-HITL gate a coin flip could skip.** `run_with_hitl_gate`
   re-executed the activity it was gating and read `needs_hitl` off that second
   run. A temperature-0.1 Analyst returning MEDIUM the second time approved the
   applicant with no human signal. Callers now pass `gate_result=`.
2. **The security harness graded the wrong repo.** It resolved the
   `.agent-rfc/security/` pack from its *install* location, so every tenant's
   `--strict` run graded the framework's pack. The pack `ai-tenant-init` seeds
   was read by nothing. Compounding it, the framework's own pack was a
   byte-copy of the placeholder template — `RISK-EXAMPLE-001` was passing as
   compliance evidence.
3. **Two demo drivers reported success while proving nothing.** `raise
   AssertionError(...)` sat inside a `try` caught by `except Exception`. They
   were CI steps and the release-qualification check.
4. **Four disagreeing copies of "which model is the architect tier."** Plus a
   judge id in a constant *and* in models.yaml, and CI templates pinning
   `AGENT_JUDGE_MODEL` over whatever a tenant declared.
5. **"Graceful skip" that failed CI.** `run-evals.py` returned exit 2 for "too
   few cases to gate" — the state every new tenant starts in. The rule was
   written down in `FIXES_AND_CLEANUP.md`'s own lessons and applied to one of
   two call sites.

## Guards added

Each of the above now has a test that fails if it comes back:
`runtime/test/test_hitl_gate.py` (runs without Temporal or Postgres, so it
isn't skipped locally), `scripts/test/test_security_harness_roots.py`,
`scripts/test/test_no_hardcoded_model_ids.py` (with `# model-literal-ok:` as
the documented escape hatch), `scripts/test/test_release_artifact_contract.py`,
`scripts/test/test_workflow_template_wiring.py`,
`scripts/test/test_judge_model_resolution.py`.

## Traps found the hard way

- `python3 scripts/foo.py` puts `scripts/` on `sys.path[0]`, **not** the repo
  root — so `import runtime` fails in the normal invocation path while passing
  under pytest, which does have the root on the path. A feature can look fully
  tested and do nothing in every real run. `_shared.load_registry()` handles it
  now; the regression test invokes a script as a subprocess.
- **GitHub Actions rejects YAML anchors.** They parse fine locally.
- The `secrets` context is unavailable in a step's `if:`, which is what pushes
  people toward hardcoding a provider name. Put the decision in code that can
  read `models.yaml` and pass the candidate keys through `env:`.
- `map_codebase.py` ignored `dist`/`build` but not `.next` — 297 of the
  Knowledge Graph's 449 nodes were minified bundles feeding the agent context
  window.

## A caution about the review itself

Four of the smaller findings in the original report were **false positives**,
all from a line-based scanner that wasn't fence-aware and wasn't verified
hit-by-hit before reporting:

- `UserManual.md`'s `## Objective` / `## Files to Modify` headings are inside a
  ` ```markdown ` fence — an RFC template, not real headings.
- `SPECS.md` §22 is a deliberate tombstone with a pointer, not an empty stub.
- The P12 design doc's `owasp_llm_top10.md` / `nist_ai_rmf.md` /
  `mitre_atlas.md` / `iso_42001.md` are **generated** by
  `run-security-checks.py --evidence-pack`.
- `Product_Archive.md`'s "dead links" are prose recording deletions, or files
  in the oil-price-demo repo.

Only `templates/onprem-deploy/README.md`'s pointer at a non-existent
`kubernetes/templates/secret.yaml` was real (the chart deliberately references
a pre-existing Secret by name). Verify each hit before acting on a scan.

## If you are picking this up

Read `FIXES_AND_CLEANUP.md` first — it was rewritten and is now accurate. The
next concrete step is infrastructure, not code: Cloud SQL + Temporal + Ollama +
Phoenix for KYC Sentinel, and `ANTHROPIC_API_KEY_JUDGE` (which also switches on
the three judge-backed eval gates). There is also ~$7–10/month of GCP still
billing from oil-price-demo that should be reused or torn down.

---

## Addendum — the eval gates, after v1.1.0

Four fixes landed after the tag (see CHANGELOG `[Unreleased]`), all from one
thread: making KYC Sentinel's three judge-backed gates actually run.

**Fixtures now pin this tenant's own output.** Each golden/fairness case is
mapped to an applicant and run through the real `process_application` in fake
mode, recording `actual_output` + `actual_output_source`. Before this, the
suites graded the framework's *generic* pipeline output — the gates were
nominally about KYC and were judging something else.
`test/test_eval_fixtures_pinned.py` fails on an unpinned, unmapped, or drifted
case; `make pin-evals` regenerates. Two real defects surfaced during pinning:
`kyc_012` is a *pair* case (pinning one side scored 0.20), and the gender
fairness pair had no applicant behind it at all — it existed only as prompt
text and could never have run.

**The remaining blocker is not code.** The judge account is out of credits
(`"Your credit balance is too low"`). Fund `ANTHROPIC_API_KEY_JUDGE` or repoint
the `judge` role, and the gates start grading. Full diagnosis in KYC Sentinel's
`DEVLOG.md` 2026-07-29.

**A gate-semantics change to be aware of.** All-cases-errored now exits 0 with
the provider's message; partial errors still fail. Reversible, and pinned by
tests on both sides of the boundary. It exists because `main` was red over a
billing state rather than a regression — but if you'd rather a provider outage
block merges, that is a one-line change in `run_scorecard`.

**Lesson worth carrying:** three root-cause hypotheses were wrong in a row
because `raise_for_status()` hides the response body. When a diagnosis stalls,
fix the diagnosability before guessing again.

### Still open (flagged in review, never actioned — not re-requested)

1. Golden `--fail-below 0.80` is **uncalibrated** against the real judge. Local
   Ollama judges proved actively unreliable here: qwen2.5 marked `kyc_012` down
   for "identical outputs despite differing nationalities" — the exact
   behaviour policy-007 requires.
2. KYC has **no hallucination/adversarial fixtures of its own**; those gates
   grade framework base fixtures while their CI step names claim F7/F3
   specificity.
3. `SEC-TOOL-001` verifies the mechanism, not the tenant allowlist.
4. **12 of 23 `SEC-*` controls have no runner.**
