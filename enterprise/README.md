# Enterprise Pack (docs/DESIGN.md › Enterprise Install and Compliance Pack)

Optional governance layer for orgs running AgentSmith across multiple
teams. Does not change core framework behaviour — adds enforcement,
auditability, and isolation controls.

## The org policy, and no hook bundle

The org policy (`agenticframework-org.yaml`, an example beside this file) is installed on each
managed machine at `~/.agent-framework/agenticframework-org.yaml`, beside the provider
`install-ai-stack.sh` installs. IT distributes the installer and the policy through its own
MDM. The signed **hook bundle** (`package-hook-bundle.sh`, `mdm-deploy-hooks.sh`) is gone in
3.0.0, together with the machine-wide git hooks it shipped
(`.agent-rfc/designs/vendoring-retired.md`). A repository is governed by the gate it declares,
through its own `.githooks`, and the commit checks the bundle's hooks made under the policy
(an `RFC-NNN` per commit, an RFC under `.agent-rfc/`, no direct `cost_router` import) are
made by that gate. A signed bundle of the provider install and the policy is on the backlog.

## Bypass Policy Enforcement

`agenticframework-org.yaml`'s `hooks.bypass_policy` decides whether `agentsmith mode off` may
record the machine as disabled (`runtime/machine/policy.py`; `agentsmith hooks bypass-check`
asks the same question). A repository's own gate has no bypass switch to ask about: the
`DISABLE_AI_STACK=true` the machine-wide hooks honoured left with them in 3.0.0, and a commit
that skips the gate (`--no-verify`) is caught by the sweep and by CI whatever the policy says.

| `bypass_policy` | A requested bypass |
|---|---|
| (no policy file) | Granted — default developer/solo mode |
| `disabled` | Refused; prints the `break_glass_approvers` contact |
| `break-glass` | Granted only with a valid, unexpired `AI_BREAK_GLASS_TOKEN` signed with `BREAK_GLASS_HMAC_KEY` |
| (unset in a policy file) | Granted — the policy restricts nothing |
| anything else (`disable`, `Disabled`, …) | Refused — an unrecognised value is not read as "no restriction" |

Refused — or when the check cannot run at all (the command missing, the policy file
unreadable) — the mode is not changed, and the command says so: a failed check is enforcement,
never a bypass.

Every bypass attempt under an enterprise policy — granted or denied, from
`agentsmith mode off` — is written to the Ops Portal's immutable
audit log (`hook_bypass` event, see `portal/lib/auditLog.ts`) when
`OPS_PORTAL_URL` and `AUDIT_LOG_WRITE_TOKEN` are configured in the environment,
and to `~/.agent-framework/local-audit-fallback.log` when they are not or the
write fails. Best-effort: never blocks the command if the portal is unreachable.

## SSO / Audit Log / Dedicated Worker Pool

See `portal/README.md` for SSO/OIDC and the audit log (both live in the Ops
Portal). Dedicated worker pool (`tenant.isolation: dedicated`) is documented
in docs/DESIGN.md › Tenancy Model (Independent Repositories), Enterprise Install and Compliance Pack and scaffolded via `agentsmith tenant init` + the example
manifests — see the project root for the current state of that piece.
