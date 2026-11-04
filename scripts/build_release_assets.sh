#!/usr/bin/env bash
# scripts/build_release_assets.sh <out-dir> — what a release publishes, built one
# way for .github/workflows/release.yml and for scripts/check_release_install.sh,
# so what the check exercises is what ships
# (.agent-rfc/designs/release-install-path.md).
#
#   agentsmith-source.tar.gz   the commit's tracked tree, unprefixed. The installer
#                              unpacks it and installs from it as from a checkout.
#   install-ai-stack.sh        the bootstrap script itself
#   *.sha256                   "<hash>  <bare name>": `shasum -a 256 --check` resolves
#                              the name against the current directory
#   widget.js                  the in-app widget a tenant embeds
set -euo pipefail

out="${1:?usage: build_release_assets.sh <out-dir>}"
root="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
mkdir -p "$out"

# `git archive`, not `tar` of the working tree: tracked files only, so no .env,
# node_modules or .hitl_blobs can reach a release.
git -C "$root" archive --format=tar.gz -o "$out/agentsmith-source.tar.gz" HEAD
cp "$root/install-ai-stack.sh" "$out/install-ai-stack.sh"
cp "$root/templates/in-app-widget/widget.js" "$out/widget.js"
(cd "$out" && for f in agentsmith-source.tar.gz install-ai-stack.sh; do shasum -a 256 "$f" > "$f.sha256"; done)

# What the gate and the ports read at run time, named: an archive missing one is
# a release that installs and then fails its first commit.
listing="$(tar -tzf "$out/agentsmith-source.tar.gz")"
for needed in install-ai-stack.sh .githooks/process-gate docs/review-levers.md \
              docs/design-review-checklist.md runtime/cli.py requirements.lock \
              fixtures/security/control_registry.json templates/governance.json; do
  # A here-string, not a pipe: `grep -q` leaves at its first match, and under
  # pipefail a writer left behind reads as "missing", as it did tagging v3.0.1.
  if ! grep -qxF "$needed" <<<"$listing"; then
    echo "❌ agentsmith-source.tar.gz is missing $needed" >&2
    exit 1
  fi
done
ls -la "$out"
