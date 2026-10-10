# The security contract, version 1

A **security provider** checks a repository's own security: the pack it keeps, the posture it
declares, and what its telemetry carries on the wire. AgentSmith is one provider. This directory is
what another platform implements instead, and the suite that proves it did.

## The protocol

```
<security-command> check
<security-command> redaction
```

- **cwd** is the repository, or the request's `cwd` names it.
- **stdin** is one request; unknown keys are ignored. `check`: `request.schema.json` — optional
  `controls` (the ids to check; all by default) and `evidence_dir` (where to write the provider's
  pack for a person). `redaction`: `redaction-request.schema.json` — `environment` (`staging` or
  `production`) and optionally `emitter`, which beats the declaration's.
- **stdout** is one result and nothing else — `result.schema.json` or `redaction-result.schema.json`.
  The provider's report for a person goes to stderr.
- **exit 0** whenever the provider answers; the verdict is in the result, and the caller decides
  what it means for a build. **Exit 3**: this provider cannot run here. An answer is a result on
  stdout; anything else, whatever the exit code, is no answer.

## `check`

| Field | Means |
|---|---|
| `schema` | `1` |
| `verdict` | `pass` \| `fail` \| `not_gradable` |
| `reason` | why, in a sentence — required for anything but `pass` |
| `provider` | `{name, version}` — whose answer this is |
| `controls` | one row per control: `id`, `title`, `subject`, `result`, `message`, `frameworks` (OWASP, NIST, ATLAS, ISO 42001 tags), `evidence` |
| `counts` | rows per result |

**`subject`** says whose evidence a row is. `repository`: checked against the repository's own
pack, code and declarations. `provider`: about the provider's own code — its library, its
services, its probe sets. **In a repository that is not the provider's own, a provider row is not
run**: it reads `not_applicable`, naming the provider's version, whose own CI is its evidence. A
verdict about a repository never depends on how its provider was installed.

**`result`**: `pass`; `fail`; `gap` — a gap a registry declares, shown in every result and never
a failure; `not_applicable` — nothing for the control to govern here. There is **no non-strict
mode**: a control that only warns is a `fail`.

**`verdict`**: `fail` if any row fails; `not_gradable` when the repository's own declarations
cannot be read — a registry that does not match `registry.schema.json`; otherwise `pass`.

**The posture checked is the declared one** — `.agenticframework/tenant.yaml`, never the
environment of whoever runs the check.

### The controls every provider checks

`controls.json` lists them: what each reads and when it passes. In short —

| Id | Reads |
|---|---|
| SEC-RISK-001 | `.agent-rfc/security/risk_register.yaml` (`risk_register.schema.json`) |
| SEC-AGENCY-001 | `.agent-rfc/security/agency_manifest.yaml` (`agency_manifest.schema.json`) |
| SEC-TOOL-001 | `.agent-rfc/security/tool_allowlist.yaml` (`tool_allowlist.schema.json`) and the tools registered |
| SEC-PROMPT-001, SEC-PII-001 | `tenant.yaml` `security.prompt_guard`, `security.input_guardrail` |
| SEC-MOD-001 | `tenant.yaml` `moderation.mode`, `moderation.hook` |
| SEC-PII-002 | `redaction`, for both profiles, with the declared emitter |
| SEC-CHANGE-001 | `providers.json` `gate` |
| SEC-EVAL-001/002/003 | the golden, fairness and hallucination datasets, gradable under `contract/evals/v1` |
| SEC-ADV-001, SEC-RAG-001 | the adversarial and rag_poison suites, under `contract/evals/v1` |

A word the repository declares is checked as a word: a bare YAML `off` is the boolean false, not a
mode. A provider adds controls of its own, under either subject.

### The repository's own controls

`.agent-rfc/security/control_registry.json` (`registry.schema.json`) **adds** controls: one with
an id the provider already checks is refused, and that control fails — a registry the repository
under review can edit must not lower its floor. A row claiming `met` or `partial` names the
`suite` that evidences it, a test path the provider runs with **the repository's own interpreter**
(`python3 -m pytest <suite>`, `python3` from PATH); `gap` and `org-owned` rows need none — a `gap`
row reads `gap`, and an `org-owned` row with no suite `not_applicable`, its evidence held outside
the repository. A
provider never imports the repository's code into its own process — a declared moderation hook
is called the same way.

## `redaction`

The provider runs the emitter with its OTLP destination pointed at a receiver on 127.0.0.1 (its
own destinations and collector credential removed), `ENVIRONMENT` set to the request's, and the
probes of `probes.json` in `SECURITY_REDACTION_PROBES` as a JSON array. **An emitter promises** to
export one span carrying `security.redaction.probe: true` with the probes in `input.value`, through
whatever redaction it applies in that environment.

| Verdict | When |
|---|---|
| `pass` | the probe span arrived, and no probe's `core` appears in anything exported |
| `fail` | one did — `leaked` names it by kind, never by its text — whatever the emitter did after |
| `not_gradable` | the emitter did not run, nothing arrived, no span carried the marker, or none is declared |
| `not_applicable` | the repository declares `"emitter": "none"` |

The probes are not credentials; each is shaped like what a redactor must scrub.

## The declaration

`.agenticframework/providers.json` names the provider (`providers.schema.json`):

```json
{"providers": {"security": {"command": "agentsmith security", "version": "^2", "contract": 1,
                            "emitter": "python3 scripts/telemetry_smoke.py"}}}
```

The command is split on whitespace, with no quoting, and run with the verb appended. `emitter` is
the command that exports one representative run of the repository's telemetry; `"none"` declares
it emits none. `"security": "none"` — the repository declares no security provider, and a step
says so instead of checking.

## Who asks

**A repository's CI**, through a step that resolves the declared provider — AgentSmith's launcher
answers `bash .githooks/process-gate security check [--evidence-dir DIR]` and `security redaction
--environment staging|production`. Failure is **closed**: only `pass` passes, and a `redaction` the
repository declared `none` for. No verdict can be declared a warning — nothing a check reads runs
out.

## Conformance

```bash
agentsmith conformance --port security --provider "<command>"
```

Builds `fixture.json`'s repository fresh for each case of `cases.json`: a complete pack, a
declared posture, a control of the repository's own, a moderation hook module, and `emit.py` — an
emitter on the standard library alone whose argument says how it treats the probes. Each case
changes files and says what the answer must be. Every `check` answer must list each control of
`controls.json` as a repository row, and report each provider row not applicable — the fixture is
not the provider's repository.

## What is not in version 1

The posture of a deployed process — where the runtime lets an environment variable override
`tenant.yaml` — is the deployment's, not this check's. A repository's own residency declaration,
and a provider's release evidence for its provider rows to cite, are later versions.
