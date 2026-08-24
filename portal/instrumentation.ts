// portal/instrumentation.ts — Next's one startup hook, and the only reason the
// portal appears in a trace at all.
//
// Runs once per runtime before any request is served (requires
// `experimental.instrumentationHook` in next.config.mjs on Next 14). Next
// calls it for BOTH runtimes, and the Edge one cannot load the OTel Node SDK —
// so the SDK is behind a dynamic import guarded on NEXT_RUNTIME rather than a
// top-level one. A static import here would put `node:async_hooks` in the Edge
// bundle and break `next build`, which is the failure test/edgeSafety.test.ts
// was written after.

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./instrumentation.node");
  }
}
