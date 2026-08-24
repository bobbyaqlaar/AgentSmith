// portal/test/tracing.test.ts — the portal's spans, asserted over EMITTED
// spans rather than over the helpers that emit them.
//
// That distinction is the whole point, and it is borrowed from the finding
// that produced runtime/test/test_pillar3_conformance.py: the old assertion
// there checked `tenant.id == "acme"` on a call that had passed
// `tenant_id="acme"`, so it could not fail. Everything below runs through a
// real NodeTracerProvider into a real InMemorySpanExporter, and reads the
// exported span.
//
// One provider, registered once, at module load. OTel's global tracer provider
// is one-shot in JS exactly as it is in Python — a second `register()` is
// ignored with a warning — so a test that installed its own would silently
// assert on spans belonging to someone else's exporter. Each portal test file
// is its own `node` process, so registering here costs nothing elsewhere.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { SpanStatusCode, context, propagation, trace } from "@opentelemetry/api";
import { InMemorySpanExporter, NodeTracerProvider, SimpleSpanProcessor } from "@opentelemetry/sdk-trace-node";

import { isPassthroughQuery, operationOf } from "../lib/db.ts";
import { ENVIRONMENT_ALIASES, getEnvironment } from "../lib/environment.ts";
import { PORTAL_ROLE, PortalIdentityProcessor, resourceAttributes } from "../lib/spanIdentity.ts";
import {
  currentTraceId,
  portalSpan,
  resolveTracesEndpoint,
  withIdentity,
} from "../lib/tracing.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(HERE, "..", "..");

const exporter = new InMemorySpanExporter();
const provider = new NodeTracerProvider({
  spanProcessors: [new PortalIdentityProcessor(), new SimpleSpanProcessor(exporter)],
});
provider.register();

let passed = 0;
async function test(name: string, fn: () => void | Promise<void>) {
  exporter.reset();
  try {
    await fn();
    passed += 1;
    console.log(`ok - ${name}`);
  } catch (err) {
    console.error(`not ok - ${name}`);
    console.error(err);
    process.exitCode = 1;
  }
}

/** Exported spans, asserting there ARE some — without this every assertion
 *  below would pass over an empty array if registration had quietly lost. */
function spans() {
  const finished = exporter.getFinishedSpans();
  assert.ok(finished.length > 0, "no spans were exported — the assertions would check nothing");
  return finished;
}

const only = () => {
  const finished = spans();
  assert.equal(finished.length, 1, `expected one span, got ${finished.map((s) => s.name).join(", ")}`);
  return finished[0];
};

// ── the harness itself ───────────────────────────────────────────────────────

await test("the registered provider is the one this file exported into", async () => {
  await portalSpan("portal.test.smoke", {}, async () => {});
  assert.equal(only().name, "portal.test.smoke");
});

// ── identity (pillar 3, per-request half) ────────────────────────────────────

await test("a span started inside withIdentity carries the tenant", async () => {
  await withIdentity({ tenantId: "acme", actorRole: "operator" }, () =>
    portalSpan("portal.test.work", {}, async () => {}),
  );
  const span = only();
  assert.equal(span.attributes["tenant.id"], "acme");
  assert.equal(span.attributes["portal.actor.role"], "operator");
});

await test("nested spans inherit identity without being told", async () => {
  // This is the pool's case: lib/db.ts has never heard of a tenant and its
  // query spans must be attributed anyway.
  await withIdentity({ tenantId: "globex" }, () =>
    portalSpan("portal.test.outer", {}, async () => {
      await portalSpan("portal.test.inner", {}, async () => {});
    }),
  );
  const names = spans().map((s) => s.name);
  assert.deepEqual(new Set(names), new Set(["portal.test.inner", "portal.test.outer"]));
  for (const span of spans()) assert.equal(span.attributes["tenant.id"], "globex");
});

await test("an unbound span is unattributed, not mislabelled", async () => {
  // Absent, not "unknown": a gap is visible in a query, a plausible
  // placeholder gets aggregated with real data and is not.
  await portalSpan("portal.test.orphan", {}, async () => {});
  const span = only();
  assert.ok(!("tenant.id" in span.attributes));
  assert.ok(!("portal.actor.role" in span.attributes));
});

await test("identity does not leak past the block that bound it", async () => {
  // A Node process serves every tenant in turn. One request's tenant surviving
  // into the next would mislabel every span after the first.
  await withIdentity({ tenantId: "acme" }, () => portalSpan("portal.test.first", {}, async () => {}));
  await portalSpan("portal.test.after", {}, async () => {});
  const after = spans().find((s) => s.name === "portal.test.after");
  assert.ok(after);
  assert.ok(!("tenant.id" in after.attributes), "tenant leaked out of withIdentity");
});

// ── the process hop ──────────────────────────────────────────────────────────

await test("an incoming traceparent becomes the PARENT of the portal's span", async () => {
  // What Next does before a route handler runs (withPropagatedContext in
  // next/dist/server/lib/trace/tracer.js). Asserting it here rather than
  // trusting it: this single behaviour is the difference between a trace that
  // crosses the process boundary and two traces that merely mention the same
  // id.
  const traceId = "4bf92f3577b34da6a3ce929d0e0e4736";
  const parentSpanId = "00f067aa0ba902b7";
  const remote = propagation.extract(context.active(), {
    traceparent: `00-${traceId}-${parentSpanId}-01`,
  });

  await context.with(remote, () => portalSpan("portal.test.hop", {}, async () => {}));

  const span = only();
  assert.equal(span.spanContext().traceId, traceId, "portal span started a NEW trace");
  assert.equal(span.parentSpanContext?.spanId ?? span.parentSpanId, parentSpanId);
});

await test("currentTraceId reports the propagated trace, and null outside one", async () => {
  const traceId = "0af7651916cd43dd8448eb211c80319c";
  const remote = propagation.extract(context.active(), {
    traceparent: `00-${traceId}-b7ad6b7169203331-01`,
  });
  let seen: string | null = null;
  await context.with(remote, () => portalSpan("portal.test.id", {}, async () => {
    seen = currentTraceId();
  }));
  assert.equal(seen, traceId);
  assert.equal(currentTraceId(), null, "a trace id outside any span is a fabricated correlation");
});

// ── failures ─────────────────────────────────────────────────────────────────

await test("portalSpan records the failure and re-throws it", async () => {
  await assert.rejects(
    () => portalSpan("portal.test.boom", {}, async () => {
      throw new TypeError("kaboom");
    }),
    /kaboom/,
  );
  const span = only();
  assert.equal(span.status.code, SpanStatusCode.ERROR);
  assert.equal(span.attributes["error.type"], "TypeError");
  assert.equal(span.events[0]?.name, "exception");
});

// ── the Resource half ────────────────────────────────────────────────────────

await test("the Resource carries the per-process half and NOT the per-request half", () => {
  const attrs = resourceAttributes({ ENVIRONMENT: "staging" } as NodeJS.ProcessEnv);
  assert.equal(attrs["service.name"], "agentsmith-ops-portal");
  assert.equal(attrs["agent.role"], PORTAL_ROLE);
  assert.equal(attrs.environment, "staging");
  // These two vary between requests in one process — on the Resource they
  // would be a confident lie on most spans rather than an honest gap on some.
  assert.ok(!("tenant.id" in attrs));
  assert.ok(!("portal.actor.role" in attrs));
});

await test("the owner is omitted rather than guessed", () => {
  assert.ok(!("agent.owner_id" in resourceAttributes({} as NodeJS.ProcessEnv)));
  assert.equal(
    resourceAttributes({ AGENT_OWNER_ID: "bobby@example.com" } as NodeJS.ProcessEnv)["agent.owner_id"],
    "bobby@example.com",
  );
});

// ── the endpoint trap ────────────────────────────────────────────────────────

await test("an endpoint that already names /v1/traces is not suffixed twice", () => {
  // This repo's own convention puts a full traces URL in the variable the OTLP
  // spec calls a base — see resolveTracesEndpoint. Left unhandled, every span
  // would POST to /v1/traces/v1/traces and vanish with a 404.
  const env = { OTEL_EXPORTER_OTLP_ENDPOINT: "http://localhost:6006/v1/traces" } as NodeJS.ProcessEnv;
  assert.equal(resolveTracesEndpoint(env), "http://localhost:6006/v1/traces");
});

await test("a base endpoint gains the traces path exactly once", () => {
  for (const base of ["http://localhost:6006", "http://localhost:6006/", "http://localhost:6006//"]) {
    assert.equal(
      resolveTracesEndpoint({ OTEL_EXPORTER_OTLP_ENDPOINT: base } as NodeJS.ProcessEnv),
      "http://localhost:6006/v1/traces",
      base,
    );
  }
});

await test("the traces-specific variable wins, and nothing set means disabled", () => {
  assert.equal(
    resolveTracesEndpoint({
      OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: "http://collector:4318/v1/traces",
      OTEL_EXPORTER_OTLP_ENDPOINT: "http://localhost:6006",
    } as NodeJS.ProcessEnv),
    "http://collector:4318/v1/traces",
  );
  assert.equal(resolveTracesEndpoint({} as NodeJS.ProcessEnv), null);
  assert.equal(
    resolveTracesEndpoint({ AGENT_PHOENIX_ENDPOINT: "http://phoenix:6006" } as NodeJS.ProcessEnv),
    "http://phoenix:6006/v1/traces",
  );
});

// ── the pool wrapper's decisions ─────────────────────────────────────────────

await test("the pool traces the promise forms and passes the others through", () => {
  assert.equal(isPassthroughQuery(["SELECT 1", []]), false);
  assert.equal(isPassthroughQuery([{ text: "SELECT 1", values: [] }]), false);
  // A trailing callback and a Submittable both return something other than a
  // promise; wrapping either would change what the caller gets back.
  assert.equal(isPassthroughQuery(["SELECT 1", [], () => {}]), true);
  assert.equal(isPassthroughQuery([{ submit: () => {} }]), true);
});

await test("the span name comes from a closed set of operations", () => {
  assert.equal(operationOf("SELECT * FROM tenants"), "SELECT");
  assert.equal(operationOf("  insert into agent_runs values ($1)"), "INSERT");
  // Anything unrecognised collapses to one name rather than minting a new
  // time series per statement.
  assert.equal(operationOf("WITH x AS (SELECT 1) SELECT * FROM x"), "QUERY");
  assert.equal(operationOf(undefined), "QUERY");
});

// ── the mirror ───────────────────────────────────────────────────────────────

await test("lib/environment.ts has not drifted from runtime/environment.py", () => {
  // A deliberate mirror needs a pin, or it is just a second opinion. Same
  // treatment scripts/_shared.py's _dotenv_value mirror gets on the Python
  // side. Reading the file rather than skipping when it is absent: a check
  // that quietly measures nothing is the failure mode this repo keeps finding.
  const source = readFileSync(resolve(REPO_ROOT, "runtime", "environment.py"), "utf8");
  const block = source.match(/_ALIASES\s*=\s*\{([\s\S]*?)\}/);
  assert.ok(block, "could not find _ALIASES in runtime/environment.py");
  const python: Record<string, string> = {};
  for (const [, key, value] of block[1].matchAll(/"([^"]+)"\s*:\s*"([^"]+)"/g)) python[key] = value;

  assert.ok(Object.keys(python).length >= 8, "parsed too few aliases — the regex, not the code, is wrong");
  assert.deepEqual(ENVIRONMENT_ALIASES, python);
  // And the fail-closed default the header promises, which the table alone
  // does not express.
  assert.ok(!source.includes('_ALIASES.get(raw, "development")'), "the Python default is no longer production");
});

await test("an unset or misspelled ENVIRONMENT fails closed to production", () => {
  const original = process.env.ENVIRONMENT;
  try {
    delete process.env.ENVIRONMENT;
    assert.equal(getEnvironment(), "production");
    process.env.ENVIRONMENT = "produciton";
    assert.equal(getEnvironment(), "production");
    process.env.ENVIRONMENT = "dev";
    assert.equal(getEnvironment(), "development");
  } finally {
    if (original === undefined) delete process.env.ENVIRONMENT;
    else process.env.ENVIRONMENT = original;
  }
});

await provider.shutdown();
console.log(`\n${passed} passed`);
