// portal/instrumentation.node.ts — the SDK, assembled once, in one place.
//
// This is `runtime/tracing.configure_tracing()` for the portal, and it exists
// for the same reason that function does: assembling a provider by hand is
// several steps that must all be remembered, and the evidence across this
// repo is that they are not.
//
// WHAT REGISTERING THIS BUYS, beyond the spans below. Next.js instruments its
// own request handling when — and only when — a tracer provider is registered
// (see next/dist/server/lib/trace/tracer.js), and it calls `propagation.extract`
// on the incoming headers before the handler runs. So the worker's
// `traceparent` becomes the PARENT of the portal's request span, and every
// span this process starts is a descendant of the worker's LLM call. That is
// the difference between a trace that stops at the process boundary and one
// that crosses it.
//
// DEGRADATION: with no endpoint configured, nothing is registered at all — not
// a provider with no exporter, which would record spans, pay for them, and
// drop them. No endpoint means the portal behaves exactly as it did before
// this file existed.

import { diag, DiagConsoleLogger, DiagLogLevel } from "@opentelemetry/api";
import { resourceFromAttributes } from "@opentelemetry/resources";
import { BatchSpanProcessor, NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";

import { PortalIdentityProcessor, resourceAttributes } from "./lib/spanIdentity";
import { resolveTracesEndpoint } from "./lib/tracing";

const endpoint = resolveTracesEndpoint();

if (!endpoint) {
  console.info(
    "[tracing] no OTEL_EXPORTER_OTLP_ENDPOINT / OTEL_EXPORTER_OTLP_TRACES_ENDPOINT — " +
      "portal spans are disabled (set it to your Phoenix instance, e.g. http://localhost:6006).",
  );
} else {
  // The SDK swallows export failures by default: a wrong endpoint or a
  // Phoenix that is down looks identical to a portal that was never
  // instrumented. ERROR-level diagnostics make that one visible line instead
  // of silence, without the per-span noise of DEBUG.
  diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.ERROR);

  const provider = new NodeTracerProvider({
    resource: resourceFromAttributes(resourceAttributes()),
    // Order matters and is the same as the Python side's: identity stamps at
    // start, export reads what is there at the end. Processors can only be
    // supplied here — `addSpanProcessor` was removed in SDK 2.x, so a
    // provider is complete when it is constructed or not at all.
    spanProcessors: [new PortalIdentityProcessor(), new BatchSpanProcessor(new OTLPTraceExporter({ url: endpoint }))],
  });

  // register() — not `trace.setGlobalTracerProvider` — because it also
  // installs the W3C propagator and the async-hooks context manager. Without
  // the propagator the incoming `traceparent` is never read and the portal
  // starts a fresh, unconnected trace; without the context manager the active
  // span is lost at the first `await`.
  provider.register();

  // Cloud Run (see .github/workflows/cd-portal.yml) stops a revision with
  // SIGTERM. A batch processor holds up to 5s of spans, so without this the
  // last spans before a deploy — often the interesting ones — are lost.
  // `once`, and no process.exit: Next installs its own handler and this must
  // not replace it.
  process.once("SIGTERM", () => {
    void provider.shutdown().catch(() => {
      // fail-open: a flush failure during shutdown is not worth a crash loop
    });
  });
}
