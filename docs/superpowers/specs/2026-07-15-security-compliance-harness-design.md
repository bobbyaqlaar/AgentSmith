# Security Compliance Harness — Design Spec

**Date:** 2026-07-15  
**Status:** Approved for planning (docs-first)  
**Approach:** Unified control registry + orchestrator + per-framework reports + gap-closure modules

## Goals

1. **Single reusable test harness** that every AgentSmith tenant app runs in CI and exports for auditors.
2. **Explicit crosswalk** across OWASP LLM Top 10, NIST AI RMF, MITRE ATLAS, and ISO/IEC 42001 (see [`docs/security-framework-map.md`](../security-framework-map.md)).
3. **Close documented security gaps** so strict mode (`SECURITY_STRICT=1`) can pass without waivers.
4. **Zero duplicate compliance docs** — ISO map remains canonical for themes; security map adds multi-framework IDs + harness contract.

## Non-goals

- ISO / SOC2 / FedRAMP **certification** (org-owned).
- Shipping a proprietary content-moderation model (pluggable hook only).
- Replacing tenant legal review or risk acceptance.
- MCP server/client in framework (BYO stays settled; tool security wraps tenant tools).

## Decisions (locked)

| Topic | Choice |
|---|---|
| Control ID scheme | `SEC-<DOMAIN>-<NNN>` (stable across frameworks) |
| Orchestrator | `scripts/run-security-checks.py` (parallel to `run-evals.py`, `verify_system.py`) |
| Registry | `fixtures/security/control_registry.json` — single source of truth |
| Tenant extensions | `.agent-rfc/security/` (risk register, agency manifest, adversarial cases, tool allowlist) |
| CI default | `strict: false` until P0–P1 land; then flip tenant templates to `strict: true` |
| Strict semantics | **Gap** controls fail; **Org-owned** fail only if required artifact missing |
| Prompt injection v1 | Rule + heuristic layer (`prompt_guard.py`), not ML classifier |
| Output validation v1 | Pydantic `model_validate_json` wrapper (`structured_output.py`) |
| Tool security v1 | Decorator registry + YAML allowlist; deny by default in strict mode |
| Moderation v1 | Callable hook on gateway; unset = warn (non-strict) or fail (strict) |
| Adversarial eval v1 | Deterministic cases + optional LLM judge; `--suite adversarial` |
| SSO revocation | Env `SSO_REVOCATION_MODE=fail-open\|fail-closed` (default fail-open for backwards compat) |
| Evidence pack | JSON + per-framework Markdown under `--evidence-pack DIR` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  run-security-checks.py                     │
│  load registry → dispatch runners → aggregate → report      │
└────────────┬────────────────────────────────────────────────┘
             │
    ┌────────┼────────┬──────────────┬──────────────┐
    ▼        ▼        ▼              ▼              ▼
 unit     artifact   eval         static        live
(pytest)  (schema)  (run-evals)  (import AST)  (optional)
    │        │        │              │              │
    └────────┴────────┴──────────────┴──────────────┘
                         │
              fixtures/security/control_registry.json
              .agent-rfc/security/* (tenant)
                         │
              evidence-pack/ + CI exit code
```

### Runner interface

Each control maps to a **runner** in `scripts/security/runners/`:

```python
@dataclass(frozen=True)
class ControlResult:
    control_id: str
    status: Literal["pass", "fail", "skip", "warn"]
    message: str
    evidence: dict[str, str]  # paths, metrics

def run(control: ControlSpec, ctx: HarnessContext) -> ControlResult: ...
```

`HarnessContext` carries: repo root, tenant `.agent-rfc/security/` path, env flags (`SECURITY_STRICT`, `INPUT_GUARDRAIL`), optional portal URL for live checks.

### Framework rollup

`scripts/security/report.py` joins `control_registry.json` framework tags → generates:
- `security_report.md` (all controls)
- `owasp_llm_top10.md`, `nist_ai_rmf.md`, `mitre_atlas.md`, `iso_42001.md`

Pass rule for `--mode ci`:
- **pass** → green
- **warn** → green if not strict; fail if strict
- **skip** on **Gap** → warn (non-strict) or fail (strict)
- **fail** → always red

---

## Component designs

### 1. Control registry (`fixtures/security/control_registry.json`)

JSON array of objects:

```json
{
  "id": "SEC-PII-001",
  "title": "Pre-call PII scrub",
  "status": "partial",
  "owner": "shared",
  "frameworks": {
    "owasp": ["LLM06"],
    "nist": ["MAP-2.6", "MANAGE-2.4"],
    "atlas": ["AML.T0043"],
    "iso42001": [9]
  },
  "runner": "pii_precall",
  "check_type": "unit",
  "mechanism": "runtime/input_guardrail.py"
}
```

### 2. PII runners (existing code)

Reuse `runtime/test/test_input_guardrail.py` and `verify_system.py --check-redaction`.
Harness invokes pytest subset or imports test helpers directly.

### 3. Prompt guard (`runtime/prompt_guard.py`) — NEW

**Behaviour:**
- `scan_prompt(text: str) -> PromptGuardResult` with `blocked: bool`, `reasons: list[str]`
- v1 heuristics: instruction override patterns (`ignore previous`, `system:`, role markers), delimiter injection, excessive control chars
- Optional tenant patterns via `.agent-rfc/security/prompt_denylist.txt`
- Wired in `llm_gateway.complete()` / `complete_stream()` **before** `input_guardrail` when `PROMPT_GUARD=default|strict|off` (default `default` after ship)

**Harness:** `fixtures/security/prompt_injection_cases_base.json` — each case `{input, expect_blocked}`.

### 4. Structured output (`runtime/structured_output.py`) — NEW

```python
def parse_llm_json[T: BaseModel](raw: str, model: type[T]) -> T:
    """Extract JSON (fenced or bare) and model_validate_json; raise StructuredOutputError."""
```

Reference apps migrate one pipeline as proof. Harness static check: no bare `json.loads()` on LLM output in `runtime/` without `# security-ok:` comment (optional lint rule in P2).

### 5. Tool registry (`runtime/tool_registry.py`) — NEW

- `@tool(name=..., description=...)` decorator → JSON schema from type hints
- `ToolRegistry` with `register`, `get_schema`, `invoke(name, args)` 
- Allowlist: `.agent-rfc/security/tool_allowlist.yaml` — only listed tools callable in strict mode
- Harness: attempt disallowed tool → expect `ToolNotAllowedError`

### 6. Moderation hook — NEW

- `register_output_moderator(fn: Callable[[str], ModerationResult])` on gateway module
- `MODERATION_HOOK=required` in strict CI for regulated tenants
- Default: no hook → skip with warn

### 7. Adversarial eval suite — NEW

Extend `run-evals.py`:

- `--suite adversarial` loads `adversarial_evals_base.json` + tenant overrides
- Cases tag expected behaviour: `block`, `flag`, `safe`
- Scorer: prompt guard result + optional judge dimension `adversarial_resilience`
- Threshold: `ADVERSARIAL_FAIL_ABOVE=0.10` (configurable)

### 8. Risk register template — NEW

- `fixtures/security/templates/risk_register.yaml` — schema with entries `{id, description, severity, mitigations[], control_ids[]}`
- Harness validates YAML against JSON Schema in `scripts/security/schemas/risk_register.schema.json`
- Does **not** judge risk content truth

### 9. Agency manifest — NEW

- `.agent-rfc/security/agency_manifest.yaml` lists `{workflow, action, needs_hitl: true}`
- Harness static: grep workflow files for declared actions; warn if manifest missing entries (soft) or fail in strict after generator ships

### 10. CI workflow (`workflow-templates/eval-security.yml`)

Inputs: `strict: boolean`. Steps:
1. Install deps (pytest, pyyaml, pydantic)
2. `pytest scripts/test/test_security_*.py runtime/test/test_security_*.py -q`
3. `python3 scripts/run-security-checks.py --mode ci [--strict]`
4. Upload evidence pack artifact on main/staging CD

### 11. verify_system integration

Add `--check-security` flag → runs smoke subset (PII unit import, registry parse, redaction check) for install health.

---

## Migration / rollout

| Phase | Deliverable | Strict CI |
|---|---|---|
| **Docs (this session)** | security-framework-map, spec, plan, handoff | N/A |
| **P0 Harness core** | registry, orchestrator, report, eval-security.yml | optional warn-only |
| **P1 Gap modules** | prompt_guard, structured_output, tool_registry | tenant opt-in strict |
| **P2 Eval + hooks** | adversarial suite, moderation hook, risk template | framework default strict in templates |
| **P3 Hardening** | SSO fail-closed option, RAG poison fixture, agency lint | all new tenants strict |

---

## Testing strategy

- **TDD** per module: failing pytest → implement → pass
- **Integration:** harness end-to-end on AgentSmith self-test workflow
- **Regression:** existing eval/hallucination/fairness suites unchanged
- **Evidence:** golden `security_report.json` snapshot in CI (optional P2)

---

## Documentation updates (this session)

| File | Change |
|---|---|
| `docs/security-framework-map.md` | Canonical crosswalk + harness contract |
| `docs/iso-42001-control-map.md` | Link to security map |
| `README.md` | Compliance bullet → security harness |
| `SPECS.md` §30 | Security framework table + link |
| `FIXES_AND_CLEANUP.md` | New P12 security harness phase |
| `docs/session-handoff/2026-07-15-security-compliance-harness.md` | New context bootstrap |

---

## Open questions (deferred to implementation)

1. **Agency manifest static analysis depth** — v1 manifest presence + sample workflow; v2 full coverage lint.
2. **Prompt guard false positive budget** — tune with tenant feedback; start conservative with warn-only mode.
3. **Live adversarial judge cost** — default deterministic; LLM judge behind `ADVERSARIAL_LIVE=1`.

---

## Approval

Design approved implicitly by user request: *"All of these are required to be implemented"* + *"Make the markdown file for security first"* + *"Post planning, update documentation and memory"*.

Next step: [`docs/superpowers/plans/2026-07-15-security-compliance-harness.md`](../plans/2026-07-15-security-compliance-harness.md).
