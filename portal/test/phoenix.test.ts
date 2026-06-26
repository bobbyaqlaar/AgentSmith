// portal/test/phoenix.test.ts — regression test for getRecentTraceStats()'s
// GraphQL query shape (P2c). The shape itself was validated against a live
// Phoenix instance during implementation; this test mocks fetch so a future
// PR can't silently break it without a live Phoenix in CI.

import assert from "node:assert/strict";
import { getRecentTraceStats } from "../lib/phoenix.ts";

let passed = 0;
function test(name: string, fn: () => Promise<void> | void) {
  return (async () => {
    try {
      await fn();
      passed += 1;
      console.log(`ok - ${name}`);
    } catch (err) {
      console.error(`not ok - ${name}`);
      console.error(err);
      process.exitCode = 1;
    }
  })();
}

const originalFetch = globalThis.fetch;

await test("getRecentTraceStats sums ok/error/total across time-series bins", async () => {
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body));
    if (body.query.includes("projects {")) {
      return new Response(JSON.stringify({ data: { projects: { edges: [{ node: { id: "proj1" } }] } } }));
    }
    return new Response(
      JSON.stringify({
        data: {
          node: {
            traceCountByStatusTimeSeries: {
              data: [
                { okCount: 8, errorCount: 2, totalCount: 10 },
                { okCount: 5, errorCount: 0, totalCount: 5 },
              ],
            },
          },
        },
      }),
    );
  }) as typeof fetch;

  const stats = await getRecentTraceStats("http://phoenix:6006", { sinceHours: 24 });
  assert.deepEqual(stats, { traceCount: 15, errorCount: 2, errorRate: 2 / 15 });
  globalThis.fetch = originalFetch;
});

await test("getRecentTraceStats degrades to null on GraphQL error (tenant Phoenix down)", async () => {
  globalThis.fetch = (async () => new Response("", { status: 503 })) as typeof fetch;
  const stats = await getRecentTraceStats("http://unreachable:6006", { sinceHours: 24 });
  assert.equal(stats, null);
  globalThis.fetch = originalFetch;
});

await test("getRecentTraceStats degrades to null when no project exists", async () => {
  globalThis.fetch = (async () =>
    new Response(JSON.stringify({ data: { projects: { edges: [] } } }))) as typeof fetch;
  const stats = await getRecentTraceStats("http://phoenix:6006", { sinceHours: 24 });
  assert.equal(stats, null);
  globalThis.fetch = originalFetch;
});

console.log(`\n${passed} passed`);
if (process.exitCode) process.exit(process.exitCode);
