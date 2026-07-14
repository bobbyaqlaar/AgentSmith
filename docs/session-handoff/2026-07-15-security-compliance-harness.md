# Session Handoff — Security Compliance Harness

**Date:** 2026-07-15  
**Branch:** `main` (sync with `origin/main` before starting)  
**Phase:** P12 — Security Compliance Harness (docs complete; implementation not started)

---

## Paste this into a fresh session

```
Repo: /Users/mac/Documents/Bobby/Aqlaar/Apps/AgenticFramework
Branch: main

Goal: Implement the Security Compliance Harness (P12) — reusable test coverage
for OWASP LLM, NIST AI RMF, MITRE ATLAS, and ISO/IEC 42001 for ALL AgentSmith
tenant apps.

Docs shipped (DO NOT redo unless wrong):
- docs/security-framework-map.md          ← canonical crosswalk + harness contract
- docs/superpowers/specs/2026-07-15-security-compliance-harness-design.md
- docs/superpowers/plans/2026-07-15-security-compliance-harness.md  ← start Task 1

Prior work still valid:
- Reliability pack v1 (hallucination, TTFT, self-correction) — merged
- UAE sovereign Falcon 3 Ollama — live-verified
- ISO map: docs/iso-42001-control-map.md
- DemoScript.md — LOCAL ONLY, gitignored — do not track or link from README/SPECS

Execute: docs/superpowers/plans/2026-07-15-security-compliance-harness.md
Use subagent-driven-development or executing-plans. TDD per task.
Commit only when I ask.

Strict mode target: SECURITY_STRICT=1 fails on Gap controls after Tasks 6–10 land.
```

---

## What was decided

| Decision | Choice |
|---|---|
| First deliverable | Markdown crosswalk + harness contract (done) |
| Control IDs | `SEC-*` stable across four frameworks |
| Orchestrator | `scripts/run-security-checks.py` |
| Tenant extensions | `.agent-rfc/security/` |
| CI | `workflow-templates/eval-security.yml` |
| Gap modules | prompt_guard, structured_output, tool_registry, adversarial eval, moderation hook |
| Strict default | false until P1 modules ship; then true for new tenants |

---

## Implementation order

1. **Task 1** — `fixtures/security/control_registry.json` + `scripts/security/registry.py`
2. **Task 2** — `run-security-checks.py` + smoke runners (PII pre/post)
3. **Task 3** — CI workflow + `verify_system.py --check-security`
4. **Task 4** — tenant templates (risk register, agency manifest, tool allowlist)
5. **Task 5** — evidence pack per-framework Markdown
6. **Tasks 6–10** — gap modules (parallelizable)
7. **Tasks 11–12** — SSO fail-closed + doc status updates + strict flip

---

## Key files to read first

1. `docs/security-framework-map.md` — unified control table
2. `docs/superpowers/plans/2026-07-15-security-compliance-harness.md` — task steps with code
3. `runtime/input_guardrail.py`, `runtime/trace_redactor.py` — existing SEC-PII runners wrap these
4. `scripts/run-evals.py` — pattern for adversarial suite extension

---

## Do not

- Track or link `DemoScript.md`
- Commit `.agent-history.log`, `.obsidian/`, secrets
- Claim ISO/OWASP/NIST/MITRE certification in docs
- Skip TDD on new runtime modules

---

## Success criteria

- [ ] `python3 scripts/run-security-checks.py --mode ci` exits 0 (non-strict initially)
- [ ] `pytest scripts/test/test_security_*.py runtime/test/test_security_*.py` green
- [ ] Evidence pack exports 5 framework reports
- [ ] All **Gap** rows in security-framework-map → **Met** or **Partial** with harness proof
- [ ] Tenant CI template includes `eval-security.yml`

---

## Env vars (harness)

| Var | Default | Meaning |
|---|---|---|
| `SECURITY_STRICT` | `0` | Fail on warn/skip for gap controls |
| `PROMPT_GUARD` | `default` (after Task 6) | `off\|default\|strict` |
| `MODERATION_HOOK` | unset | `required` in regulated strict CI |
| `ADVERSARIAL_FAIL_ABOVE` | `0.10` | Adversarial suite threshold |
| `SSO_REVOCATION_MODE` | `fail-open` | Portal session revocation behaviour |

---

## Related compliance docs

- ISO themes: `docs/iso-42001-control-map.md`
- UAE: `docs/uae-regulatory.md`
- Gaps tracker: `FIXES_AND_CLEANUP.md` § P12
