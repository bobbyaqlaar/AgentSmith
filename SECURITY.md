# Security Policy

AgentSmith governs how software is built and run, so a flaw in it can quietly weaken every repository it
governs. Reports are welcome and taken seriously.

## Reporting a vulnerability

**Do not open a public issue.** Report it privately through GitHub: the repository's **Security** tab →
**Report a vulnerability**. Please include the version (`agentsmith version`), what you did, what happened,
and how to reproduce it.

We aim to acknowledge a report within three working days, and will tell you what we find and when a fix
ships. We credit reporters who want credit.

## Supported versions

Security fixes go into the latest release. A tenant pins its release, so the release notes and the
compatibility matrix in `CHANGELOG.md` say what moving to it involves.

## In scope, especially

- **Bypassing a gate:** a change reaching `main` without the design, review or CI check that should catch it,
  or an AI coding agent getting past an edit or shell check.
- **The Ops Portal:** authentication, role and tenant isolation, the audit log's tamper evidence, replay
  signing.
- **The runtime:** the gateway's budget, prompt and tool controls; PII and trace redaction.
- **The release path:** the installer, its checksums, the composite actions tenants reference.

## Out of scope

A model's own output, and vulnerabilities in third-party services and dependencies, unless AgentSmith's use
of them is the cause. Please report those upstream, and tell us if we should respond.

The controls in `docs/security-framework-map.md` are a mapping aid, not a certification.
