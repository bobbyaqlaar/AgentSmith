---
status: active
scope:
  - scripts/security/runners/agent_workflow.py
  - scripts/security/runners/__init__.py
  - fixtures/security/control_registry.json
  - contract/security/v1/cases.json
  - scripts/test/test_agent_workflow_injection.py
  - scripts/test/test_security_contract.py
---
# A workflow may not hand untrusted event text to a coding agent

Gap 10 of `docs/PRODUCT_BACKLOG.md`.

## Problem

In April 2026 researchers hijacked Claude Code, Gemini CLI and Copilot through malicious pull-request titles. A workflow that puts `${{ github.event.pull_request.title }}` in an agent's prompt hands an outsider the agent's instructions, and its token. Nothing checks for this.

## Approach

A new control, `SEC-CIAGENT-001`, static, subject `repository`, so every tenant's Security job runs it. A control and not a commit check, because a tenant's pillars are off by default.

It reads `.github/workflows/*.yml` and fails a step that:

1. **is a coding agent:** a known action (`anthropics/claude-code-action`, `openai/codex-action`, `google-github-actions/run-gemini-cli`, `actions/ai-inference`), or a `run:` calling `claude`, `codex`, `gemini`, `copilot`, `cursor-agent`, `aider`, `opencode` or `goose`; and
2. **receives untrusted text:** GitHub's documented attacker-controlled fields, in a `${{ }}` expression in its `with:` or `run:`; through an `env:` value it uses, at workflow, job or step level; or by reading `$GITHUB_EVENT_PATH`.

**One allowance.** A job or step `if:` restricting that field's own author to `OWNER`, `MEMBER` or `COLLABORATOR` passes, because that author is trusted: `comment.author_association` for `comment.body`, and likewise for issues, pull requests and reviews. Without it a tenant using the usual `@claude` mention pattern would have no way to go green. A condition using `!=` does not count, and the allowance never applies to branch names or commit messages, which have no such author field.

A workflow that does not parse fails the control. An unread workflow is not a clean one.

**What this cannot see.** Text laundered through `steps.*.outputs` or a file, an agent action not on the list, or an agent launched from a script the workflow calls. The control's message says what it read, and it is a floor.

## Pillars

- P1 applies — `docs/PRODUCT_BACKLOG.md` gap 10 is the requirement; `.agent-rfc/designs/agent-workflow-injection.md` is the plan.
- P2 applies — `scripts/security/runners/delegating.py` is the shape a runner takes; `pyyaml` is already required and no package is added.
- P3 n/a — a static check of files; no model call or tool call to trace.
- P4 applies — `scripts/test/test_agent_workflow_injection.py` covers each route in and each allowance; mutation-checked by hand.
- P7 applies — `scripts/security/runners/agent_workflow.py` returns the `ControlResult` every runner returns.
- P8 n/a — the telemetry wire is untouched.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 applies — `scripts/security/runners/agent_workflow.py` is the check for this pillar; the workflow text it reads is parsed and matched, never evaluated.
- P12 n/a — no secrets involved.
- P13 applies — `fixtures/security/control_registry.json` adds a repository control, so it cannot be skipped by a tenant's pillar settings.
- P14 applies — `contract/security/v1/cases.json` and `docs/security-framework-map.md` are updated with the registry; `scripts/test/test_security_registry.py` holds them together.
- P15 applies — `scripts/test/test_agent_workflow_injection.py` holds that a workflow that does not parse fails rather than passes.
- P16 applies — `CHANGELOG.md` names the new control and how to go green; reverting is one commit.

## Deviations

none

## Dependencies

none

## Levers

- `failure-is-not-a-result` — an unparseable workflow fails.
- `test-that-cannot-fail` — each route is mutation-checked by hand.
- `declared-vs-enforced` — the design says what the control cannot see.
