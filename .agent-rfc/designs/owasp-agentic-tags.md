---
status: active
scope:
  - fixtures/security/control_registry.json
  - scripts/security/registry.py
  - scripts/security/report.py
  - scripts/run-security-checks.py
  - scripts/gate_models.py
  - contract/security/v1/registry.schema.json
  - contract/security/v1/result.schema.json
  - scripts/test/test_security_registry.py
  - scripts/test/test_security_evidence_pack.py
---
# Evidence packs grade the OWASP Agentic Top 10

Gap 1 of `docs/PRODUCT_BACKLOG.md`.

## Problem

`docs/security-framework-map.md` maps the OWASP Top 10 for Agentic Applications by reading, and says so: "the harness does not grade them". An evidence pack carries the LLM Top 10 and not this list, so an auditor asking about agentic risk gets prose and no result.

## Approach

A fifth tag, `owasp_agentic`, on each control, with `ASI01` to `ASI10`, optional and additive in the registry and its published schema.

**The map is the source, and a test holds the two together.** A control is tagged with an entry only where the map's row is `Partial` or better. Where the map says **Not covered** (ASI03, ASI04, ASI05, ASI07), no control is tagged. The controls it names there protect people or the build, not agents at run time, and a tag would read as coverage. The test fails in both directions, as the LLM Top 10's does since Phase 0.

**The pack lists all ten.** `owasp_agentic_top10.md` has one row per entry: the controls tagged with it and their results, or "not covered by any control". An absent entry must not read as an absent risk, so the page lists all ten whatever the filter. `--framework owasp_agentic` narrows the main report as the others do.

## Pillars

- P1 applies — `docs/PRODUCT_BACKLOG.md` gap 1 is the requirement; `.agent-rfc/designs/owasp-agentic-tags.md` is the plan.
- P2 applies — `scripts/security/report.py` adds one page beside the four it writes; no new dependency.
- P3 n/a — no runtime path changes.
- P4 applies — `scripts/test/test_security_registry.py` holds the tags to the map; `scripts/test/test_security_evidence_pack.py` reads the new page; mutation-checked by hand.
- P7 applies — `scripts/gate_models.py` `ControlFrameworks` gains the field, and `contract/security/v1/registry.schema.json` is generated from it.
- P8 n/a — the telemetry wire is untouched.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 n/a — nothing new reads untrusted content.
- P12 n/a — no secrets involved.
- P13 n/a — no gate changes.
- P14 applies — `scripts/test/test_security_registry.py` fails when `docs/security-framework-map.md` and `fixtures/security/control_registry.json` disagree.
- P15 applies — `scripts/test/test_security_evidence_pack.py` holds that an entry no control covers is printed as not covered, not left out.
- P16 applies — `CHANGELOG.md` names the field; a registry without it still loads.

## Deviations

none

## Dependencies

none

## Levers

- `single-source-of-truth` — the map decides, the registry follows, a test holds them.
- `declared-vs-enforced` — no tag where the map says not covered.
- `failure-is-not-a-result` — an uncovered entry is printed, not omitted.
