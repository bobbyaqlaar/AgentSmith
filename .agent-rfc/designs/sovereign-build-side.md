---
status: active
scope:
  - workflow-templates/**
  - scripts/test/test_runner_setting.py
  - scripts/test/test_documented_env_vars_exist.py
---
# The build side can run on owned machines

The owner's principle of 2026-11-10: AgentSmith is about sovereign AI, its own servers with local open-weight models. The running app already needs no cloud. The build side still leans on one in two places, and the paper says so.

## Problem

Every workflow AgentSmith gives a tenant says `runs-on: ubuntu-latest`, which is GitHub's hosted runner in GitHub's cloud. A team that must keep its code on its own machines has to edit twelve files by hand, and `agentsmith sync` would then put them back. The documentation does not say which coding agents AgentSmith enforces at edit time and which only through CI, or how a team keeps the build side in its own boundary.

## Approach

**The runner is a setting.** Each template job says `runs-on: ${{ vars.AGENTSMITH_RUNNER || 'ubuntu-latest' }}`. A repository or organisation variable names the self-hosted runner's label, for example `self-hosted`. Unset, nothing changes. GitHub Enterprise Server and self-hosted runners both read it. A test holds every template job to it, so a new template cannot reintroduce the hard-wired runner.

**The documentation says what holds where.** A manual section, "Keeping the build side on your own machines", covers:

- **Edit-time enforcement:** Claude Code and Cursor. Rule files and CI: Codex, Gemini CLI, Copilot and Antigravity (gap 11, owner's decision: wait, and say so).
- **Self-hosted runners:** the runner variable. A job with services (the Python stack's Postgres) needs Docker on the runner. GitLab CI is not supported.
- **Coding agents:** they use their vendors' cloud models unless configured with a local one, so code sent to them leaves the boundary. AgentSmith's own gates call no model.
- **Release fetch:** the sync workflow and setup action fetch AgentSmith's releases from GitHub, so an air-gapped site mirrors the release.

## After the 4.1.0 review (2026-11-11)

**R8 — the guidance left the build side dependent on services it did not name.** The section said "four outside services" and that mirroring the installer covers releases; in fact every job fetches GitHub-hosted actions, the setup and deploy steps and the sync workflow name `bobbyaqlaar/AgentSmith`, packages come from PyPI, npm and the Go proxy, two templates upload to Codecov, and no workflow reads a mirror. The section now says plainly that an air-gapped runner is not supported in 4.1.0, lists each dependency with what replaces it, and warns that a self-hosted runner on a public repository runs fork pull requests. A test holds the section to the templates: every outside `uses:` must be named in it. A setting that points the templates at a mirror is open work, not done here.

## Pillars

- P1 applies — `docs/PRODUCT_BACKLOG.md` "CI runner as a setting" and the owner's sovereign principle are the requirement; `.agent-rfc/designs/sovereign-build-side.md` is the plan.
- P2 applies — `workflow-templates/agentsmith-gates.yml` and its eleven siblings change one line each; no new file in a tenant.
- P3 n/a — no runtime path changes.
- P4 applies — `scripts/test/test_runner_setting.py` reads every template; mutation-checked by hand.
- P7 applies — `workflow-templates/ci-python-fastapi.yml` keeps its services; the manual names the Docker requirement on a self-hosted runner.
- P8 n/a — the telemetry wire is untouched.
- P9 n/a — no orchestration.
- P10 n/a — no model call.
- P11 n/a — a repository variable is set by the repository's own administrators, not by event text.
- P12 n/a — no secrets involved.
- P13 applies — `workflow-templates/agentsmith-gates.yml` runs the same gate on either runner.
- P14 n/a — no fixtures.
- P15 n/a — no new signal.
- P16 applies — `CHANGELOG.md` names the variable; unset is today's behaviour, so reverting is unsetting it.

## Deviations

none

## Dependencies

none

## Levers

- `declared-vs-enforced` — the documentation says which agents are enforced where.
- `test-that-cannot-fail` — the test is shown to fail on a hard-wired runner.
