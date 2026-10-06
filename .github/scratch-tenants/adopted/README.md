# agentsmith-scratch-adopted

A scratch tenant: an existing repository with its own code and CI, brought under AgentSmith's
gates by `agentsmith tenant adopt`. Rebuilt from an orphan commit by AgentSmith's scratch-tenants
workflow on every change to what a tenant receives, so that its CI — the gate's `ci` event through
the provider's setup action, and the rules check — proves the governance contracts at that commit.

Pure workflow output: its source is `.github/scratch-tenants/adopted/` in AgentSmith. Do not edit.
