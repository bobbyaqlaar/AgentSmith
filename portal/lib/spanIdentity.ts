// portal/lib/spanIdentity.ts — pillar 3 for the portal, split the same way
// runtime/tracing.py splits it.
//
// PER-PROCESS facts (service, project, environment, owner, the portal's own
// component role) go on the Resource, where every span inherits them and no
// call site can forget one. PER-REQUEST facts (which tenant, which human) go
// on a span processor reading the active context, because they change between
// two spans of the same process and a Resource attribute would make them a
// confident lie on most spans rather than an honest gap on some.
//
// Type-only imports from the SDK, so this module carries no SDK code: the
// bootstrap in instrumentation.node.ts is the one place that loads it.

import type { Context } from "@opentelemetry/api";
import type { ReadableSpan, Span, SpanProcessor } from "@opentelemetry/sdk-trace-node";

import { getEnvironment } from "./environment";
import { identityAttributes, identityFromContext } from "./tracing";

/** The portal's component role. Deliberately a name no tenant agent uses:
 *  pillar 3 wants an `agent.role` on every span, and "ops-portal" says which
 *  component emitted it without ever being mistaken for `intake`/`research`/
 *  `analyst` work in an aggregation by role. */
export const PORTAL_ROLE = "ops-portal";

const SERVICE_NAME = "agentsmith-ops-portal";

export function resourceAttributes(env: NodeJS.ProcessEnv = process.env): Record<string, string> {
  const attrs: Record<string, string> = {
    "service.name": SERVICE_NAME,
    // Groups portal traces with the worker's when both name the same project.
    // A repo-derived default is not available in a container, and being wrong
    // here is cosmetic — nothing partitions on project.name.
    "project.name": env.AGENT_PROJECT_NAME?.trim() || SERVICE_NAME,
    environment: getEnvironment(env),
    "agent.role": PORTAL_ROLE,
  };
  const owner = env.AGENT_OWNER_ID?.trim();
  // Omitted when unset rather than "unknown" — a gap is visible in a query,
  // a plausible placeholder gets aggregated with real data and is not.
  if (owner) attrs["agent.owner_id"] = owner;
  return attrs;
}

/**
 * Stamps the per-request half onto every span at START.
 *
 * At start, not at end, for the reason runtime/tracing.py gives: an exporter
 * may sample or route on the attributes, and a span that learns its tenant
 * only when it closes has already been routed without one.
 *
 * `onEnding` is optional in the JS SpanProcessor interface, so unlike the
 * Python side this can be implemented rather than subclassed — but the same
 * rule applies: implement the interface the SDK actually calls, not the one
 * the docs summarise.
 */
export class PortalIdentityProcessor implements SpanProcessor {
  onStart(span: Span, parentContext: Context): void {
    try {
      const attrs = identityAttributes(identityFromContext(parentContext));
      for (const [key, value] of Object.entries(attrs)) {
        if (value !== undefined) span.setAttribute(key, value);
      }
    } catch {
      // fail-open: identity must never break a span, and a span must never
      // break the request it measures
    }
  }

  onEnd(_span: ReadableSpan): void {
    // Nothing. This processor only ever writes at start.
  }

  async forceFlush(): Promise<void> {}

  async shutdown(): Promise<void> {}
}
