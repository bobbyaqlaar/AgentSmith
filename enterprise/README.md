# Enterprise Pack (SPECS.md §30)

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

`agenticframework-org.yaml`'s `hooks.bypass_policy` is enforced by
`ai-stack-off` (in `install-ai-stack.sh`), once the org policy file is
installed at `~/.agent-framework/agenticframework-org.yaml`:

| `bypass_policy` | `ai-stack-off` behaviour |
|---|---|
| (no policy file) | Unrestricted — default developer/solo mode |
| `disabled` | Always refuses; prints `break_glass_approvers` contact |
| `break-glass` | Refuses unless `AI_BREAK_GLASS_TOKEN` is set |

Every `ai-stack-off` attempt under an enterprise policy — granted or denied
— is written to the Ops Portal's immutable audit log (`hook_bypass` event,
see `portal/lib/auditLog.ts`) when `OPS_PORTAL_URL` and
`AUDIT_LOG_WRITE_TOKEN` are configured in the environment. Best-effort: never
blocks the command if the portal is unreachable.

## SSO / Audit Log / Dedicated Worker Pool

See `portal/README.md` for SSO/OIDC and the audit log (both live in the Ops
Portal). Dedicated worker pool (`tenant.isolation: dedicated`) is documented
in SPECS.md §23/§30 and scaffolded via `ai-tenant-init` + the example
manifests — see the project root for the current state of that piece.
