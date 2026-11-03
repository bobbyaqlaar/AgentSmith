# Contributing to AgentSmith

Thank you for considering it. AgentSmith holds its own changes to the rules it enforces on others, so a
contribution here goes through the same gates.

## Before you start

- **A bug:** open an issue with a reproduction. A security problem goes through `SECURITY.md`, not an issue.
- **A larger change:** open an issue first, so we can agree the shape before you build it.

## Setting up

```bash
git clone https://github.com/bobbyaqlaar/AgentSmith && cd AgentSmith
./install-ai-stack.sh                # installs from this checkout
git config core.hooksPath .githooks  # the gates, on your own commits
agentsmith gates list                # what CI runs; `agentsmith gates run` runs it here
```

## What a change needs

The full rules are in `docs/process-gates.md`, and the hooks will tell you what is missing:

1. **A design** at `.agent-rfc/designs/<slug>.md` before any gated file changes: `agentsmith design new <slug>
   --scope <glob>` writes the skeleton. Every pillar gets an answer.
2. **Review passes** at `.agent-rfc/reviews/<slug>.md`, against `docs/review-levers.md`, until a pass finds
   nothing, then a sign-off.
3. **`Design:` and `Review:` trailers** on the commit, and a `CHANGELOG.md` entry where the gate asks for one.
4. **Tests**, and every "yes" gate in `agentsmith gates list` passing on what you staged.

Pull requests are merged by rebase, so each commit must stand on its own. Using an AI coding agent is
welcome; you remain responsible for what it wrote, and the gates apply to it too.

## Licence and sign-off

AgentSmith is licensed under AGPL-3.0-only, and contributions are accepted under that same licence. By
contributing you certify the [Developer Certificate of Origin](https://developercertificate.org/): you wrote
the change, or have the right to submit it under this licence. Sign each commit with `git commit -s`.

## Conduct

`CODE_OF_CONDUCT.md` applies to everyone here.
