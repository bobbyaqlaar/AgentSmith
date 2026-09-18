# Enterprise Pack (docs/DESIGN.md › Enterprise Install and Compliance Pack)

Optional governance layer for orgs running AgentSmith across multiple
teams. Does not change core framework behaviour — adds enforcement,
auditability, and isolation controls.

## Org Hook Bundle

```bash
# 1. IT generates an org signing keypair once (gpg --full-generate-key),
#    keeps the private key secret, distributes the public key to MDM.

# 2. On a machine with hooks already installed (install-ai-stack.sh):
./enterprise/package-hook-bundle.sh 1.0.0 \
  --gpg-key it-sec@example.com \
  --org-policy ./our-org-policy.yaml \
  --out ./dist

# Produces in ./dist:
#   agenticframework-hooks-1.0.0.tar.gz
#   agenticframework-hooks-1.0.0.tar.gz.sig
#   agenticframework-org.yaml
#   mdm-deploy-hooks.sh

# 3. MDM pushes ./dist + the org public key to every managed machine, then runs:
./mdm-deploy-hooks.sh 1.0.0 --org-pubkey ./org-public-key.asc
```

`mdm-deploy-hooks.sh` verifies the GPG signature **before** extracting
anything — a corrupted or unsigned bundle is refused, not installed.
Verified live (see commit history / session log): happy-path install,
tarball tampered after signing (refused, `BAD signature`), and deployment
attempted with the wrong org's public key (refused, `No public key`).

## Bypass Policy Enforcement

`agenticframework-org.yaml`'s `hooks.bypass_policy` is enforced wherever a
bypass can be asked for, once the org policy file is installed at
`~/.agent-framework/agenticframework-org.yaml`: by **the git hooks themselves**
when a commit or checkout runs with `DISABLE_AI_STACK=true` or the machine's
mode is `disabled`, and by `agentsmith mode off` before it records that mode.
One decision serves both (`runtime/machine/policy.py`); the hooks reach it
through `agentsmith hooks bypass-check`.

| `bypass_policy` | A requested bypass |
|---|---|
| (no policy file) | Granted — default developer/solo mode |
| `disabled` | Refused; prints the `break_glass_approvers` contact |
| `break-glass` | Granted only with a valid, unexpired `AI_BREAK_GLASS_TOKEN` signed with `BREAK_GLASS_HMAC_KEY` |
| (unset in a policy file) | Granted — the policy restricts nothing |
| anything else (`disable`, `Disabled`, …) | Refused — an unrecognised value is not read as "no restriction" |

Refused — or when the check cannot run at all (the command missing, the policy
file unreadable) — the hook runs as normal and says so: a failed check is
enforcement, never a bypass. A consequence for MDM-managed machines that get
the signed hook bundle but not `install-ai-stack.sh`: without
`~/.agent-framework/.venv/bin/agentsmith` there is nothing to validate a
break-glass token, so every bypass is refused there. Install the framework on
machines where break-glass must work. Before 2026-09-14 only `ai-stack-off` read the
policy, and `DISABLE_AI_STACK=true git commit` skipped every hook whatever it
said.

Every bypass attempt under an enterprise policy — granted or denied, from a
hook or from `agentsmith mode off` — is written to the Ops Portal's immutable
audit log (`hook_bypass` event, see `portal/lib/auditLog.ts`) when
`OPS_PORTAL_URL` and `AUDIT_LOG_WRITE_TOKEN` are configured in the environment,
and to `~/.agent-framework/local-audit-fallback.log` when they are not or the
write fails. Best-effort: never blocks the command if the portal is unreachable.

## SSO / Audit Log / Dedicated Worker Pool

See `portal/README.md` for SSO/OIDC and the audit log (both live in the Ops
Portal). Dedicated worker pool (`tenant.isolation: dedicated`) is documented
in docs/DESIGN.md › Tenancy Model (Independent Repositories), Enterprise Install and Compliance Pack and scaffolded via `agentsmith tenant init` + the example
manifests — see the project root for the current state of that piece.
