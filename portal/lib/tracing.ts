// portal/lib/tracing.ts — the portal's own spans.
//
// WHAT WAS MISSING. The worker injects a W3C `traceparent` on its way here
// (runtime/tracing.inject_context) and app/api/runs/ingest stores the trace id
// on the row, so a portal page can LINK to the trace. That is correlation, not
// tracing: the trace itself ended at the process boundary, because the portal
// emitted nothing. "Follow this request across services" — the entire point —
// stopped at the ingest handler, and the portal's own work (three Postgres
// round-trips, an outbound Phoenix query that can hang for five seconds) was
// invisible in every trace it appeared in.
//
// This module is the API-only half: it imports `@opentelemetry/api`, which is
// a no-op without a provider, and nothing from the SDK. The SDK lives in
// instrumentation.node.ts alone, so it is loaded once, in the Node runtime,
// and can never be dragged into the Edge bundle by a route that wanted a span.
// (middleware.ts runs on Edge — see test/edgeSafety.test.ts for what that
// costs when it is got wrong.)
//
// WHAT PORTAL SPANS DELIBERATELY DO NOT CARRY: request bodies, query
// parameters, row values, tokens. The Python side can afford payloads because
// every span it exports passes through runtime/trace_redactor.py; nothing here
// does. Parameterised SQL is recorded because it is code — the values travel
// separately as `params` and are never touched. Exception messages are the one
// remaining place data could reach a span, which is why `db.statement` is the
// statement and pg's `detail` field (it quotes the offending row's values) is
// never read.

import {
  SpanKind,
  SpanStatusCode,
  context,
  createContextKey,
  isSpanContextValid,
  trace,
  type Attributes,
  type Context,
  type Span,
} from "@opentelemetry/api";

/** Instrument name on every span this module opens. */
const TRACER_NAME = "agentsmith.portal";

/** The per-request half of pillar 3. Everything else is on the Resource. */
export interface PortalIdentity {
  /** The tenant this request is about — the attribute every query filters on. */
  tenantId?: string | null;
  /** The RBAC role of the human who asked, when a human did. */
  actorRole?: string | null;
}

// An OTel context key rather than a second AsyncLocalStorage: the SDK already
// carries a context across every await for us, `onStart` is handed that exact
// context, and one propagation mechanism is easier to reason about than two.
const IDENTITY_KEY = createContextKey("agentsmith.portal.identity");

/**
 * Bind an identity for the duration of `fn`. Every span started inside —
 * including ones started by code that has never heard of tenants, like the
 * pool in lib/db.ts — is stamped by PortalIdentityProcessor.
 *
 * This is `runtime/tenancy.agent_context()`, and it exists for the same
 * reason: threading tenant_id through every call site by hand is a rule, and
 * the audit found that most call sites forgot it.
 */
export function withIdentity<T>(identity: PortalIdentity, fn: () => T): T {
  return context.with(context.active().setValue(IDENTITY_KEY, identity), fn);
}

export function identityFromContext(ctx: Context = context.active()): PortalIdentity {
  return (ctx.getValue(IDENTITY_KEY) as PortalIdentity | undefined) ?? {};
}

/** Identity as span attributes. Absent facts are ABSENT — never "unknown". */
export function identityAttributes(identity: PortalIdentity): Attributes {
  const attrs: Attributes = {};
  if (identity.tenantId) attrs["tenant.id"] = identity.tenantId;
  if (identity.actorRole) attrs["portal.actor.role"] = identity.actorRole;
  return attrs;
}

/** Statement ceiling. Portal SQL is static, but a future generated query
 *  should not be able to put an unbounded string on a span. */
const STATEMENT_CHARS = 2000;

export function truncate(text: string, limit = STATEMENT_CHARS): string {
  // Marked rather than silently clipped, exactly as runtime/tracing.py does —
  // a reader must not take a truncated statement for the whole one.
  return text.length > limit ? `${text.slice(0, limit)}…[truncated at ${limit} chars]` : text;
}

/**
 * Run `fn` inside a span. Records the failure and RE-THROWS: tracing observes,
 * it never changes what the request does.
 */
export async function portalSpan<T>(
  name: string,
  options: { kind?: SpanKind; attributes?: Attributes },
  fn: (span: Span) => Promise<T>,
): Promise<T> {
  const tracer = trace.getTracer(TRACER_NAME);
  return tracer.startActiveSpan(
    name,
    { kind: options.kind ?? SpanKind.INTERNAL, attributes: options.attributes ?? {} },
    async (span) => {
      try {
        return await fn(span);
      } catch (err) {
        try {
          span.setAttribute("error.type", err instanceof Error ? err.name : typeof err);
          span.recordException(err as Error);
          span.setStatus({
            code: SpanStatusCode.ERROR,
            message: err instanceof Error ? err.message : String(err),
          });
        } catch {
          // fail-open: a failed attribute write must not replace the real error
        }
        throw err;
      } finally {
        try {
          span.end();
        } catch {
          // fail-open: see above
        }
      }
    },
  );
}

/**
 * The active trace as 32 lowercase hex characters, or null.
 *
 * When the worker propagated a `traceparent`, this IS the worker's trace id —
 * Next extracts the incoming context before the handler runs — so the ingest
 * route can fall back to it if the header is ever absent or malformed.
 */
export function currentTraceId(): string | null {
  try {
    const spanContext = trace.getSpan(context.active())?.spanContext();
    if (!spanContext || !isSpanContextValid(spanContext)) return null;
    return spanContext.traceId;
  } catch {
    return null; // fail-open: correlation is never worth failing a request
  }
}

/**
 * The OTLP traces endpoint, or null when tracing is not configured.
 *
 * THE TRAP THIS EXISTS FOR: this repo's own convention (SPECS.md §695,
 * OPERATIONS.md, and `ai-dashboard-start`) sets
 *
 *     OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:6006/v1/traces
 *
 * — a full traces URL in the variable the OTLP spec defines as a BASE url.
 * Python's exporter is handed that string directly and is fine. The JS
 * exporter appends `/v1/traces` to the base, so the same value that works
 * everywhere else in this framework would have made the portal POST to
 * `/v1/traces/v1/traces` and drop every span with a 404 that nothing surfaces.
 *
 * So the suffix is detected rather than assumed, and the result is always
 * returned as an explicit traces endpoint.
 */
export function resolveTracesEndpoint(env: NodeJS.ProcessEnv = process.env): string | null {
  const explicit = env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT?.trim();
  if (explicit) return explicit;

  const base = (env.OTEL_EXPORTER_OTLP_ENDPOINT ?? env.AGENT_PHOENIX_ENDPOINT)?.trim();
  if (!base) return null;

  const trimmed = base.replace(/\/+$/, "");
  return trimmed.endsWith("/v1/traces") ? trimmed : `${trimmed}/v1/traces`;
}

// Re-exported so a caller classifying a span needs one import, not two.
// SpanStatusCode is deliberately not re-exported — it is used only in here.
export { SpanKind };
