// portal/test/edgeSafety.test.ts — middleware.ts runs on the EDGE runtime, so
// nothing it imports may reach a Node-only builtin.
//
// This exists because `tsc --noEmit` and `npm test` BOTH pass on a file that
// imports node:crypto, and only `next build` fails — with an
// UnhandledSchemeError pointing at webpack internals rather than at the import.
// lib/authz.ts gained its first crypto import when the user-password compare
// was made constant-time; the Edge constraint arrived in the same commit and
// went unnoticed, and main could not build for two commits.
//
// Cheaper than a build in the loop that matters: a build takes ~30s and only
// runs in one CI job, while this runs with the unit tests.

import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { constantTimeEquals } from "../lib/constantTime.ts";

const HERE = dirname(fileURLToPath(import.meta.url));
const PORTAL = resolve(HERE, "..");

let passed = 0;
function test(name: string, fn: () => void) {
  try {
    fn();
    passed += 1;
    console.log(`ok - ${name}`);
  } catch (err) {
    console.error(`not ok - ${name}`);
    console.error(err);
    process.exitCode = 1;
  }
}

/**
 * Comments removed before scanning.
 *
 * Not cosmetic: lib/constantTime.ts's header QUOTES the build error it exists
 * to prevent ("Reading from \"node:crypto\""), and the first version of this
 * test failed on that sentence. A guard that fires on a file explaining why it
 * is safe is worse than no guard — it gets deleted.
 *
 * Block comments and line comments only. It does not track string literals, so
 * a `//` inside a string would over-strip; nothing in the Edge graph does that,
 * and the failure mode is a false PASS on one line rather than a false alarm.
 */
function stripComments(source: string): string {
  // LINE comments first. middleware.ts contains `// /api/sync/* is
  // machine-to-machine`, and stripping blocks first let that `/*` open a
  // "block comment" that ran to the next `*/` further down the file —
  // swallowing every import on the way. The walker then returned one file and
  // the scan below passed having examined nothing but middleware.ts itself.
  return source
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");
}

/** Relative specifiers only — a bare package import is not ours to walk. */
function localImports(source: string): string[] {
  const out: string[] = [];
  const pattern = /(?:from|import)\s+["'](\.[^"']+)["']/g;
  for (const match of source.matchAll(pattern)) out.push(match[1]);
  return out;
}

function resolveLocal(fromFile: string, specifier: string): string | null {
  const base = join(dirname(fromFile), specifier);
  for (const candidate of [base, `${base}.ts`, `${base}.tsx`, join(base, "index.ts")]) {
    if (existsSync(candidate) && !candidate.endsWith("/")) return candidate;
  }
  return null;
}

/** Every local module middleware.ts reaches, transitively. */
function edgeGraph(): string[] {
  const entry = join(PORTAL, "middleware.ts");
  const seen = new Set<string>();
  const queue = [entry];
  while (queue.length) {
    const file = queue.pop()!;
    if (seen.has(file)) continue;
    seen.add(file);
    for (const specifier of localImports(stripComments(readFileSync(file, "utf8")))) {
      const resolved = resolveLocal(file, specifier);
      if (resolved) queue.push(resolved);
    }
  }
  return [...seen];
}

// Node builtins the Edge runtime does not provide. `node:crypto` is the one
// that actually broke the build; the rest are the same trap wearing a
// different name.
//
// `Buffer` is deliberately NOT here. Next polyfills it in the Edge runtime and
// middleware.ts decodes basic-auth credentials with it — this test flagged that
// on its first run, and `next build` compiling is the authoritative answer, not
// the rule. A guard that fails on working code trains people to delete it.
const FORBIDDEN = [
  /from\s+["']node:/,
  /require\(\s*["']node:/,
  /from\s+["'](?:crypto|fs|path|os|child_process)["']/,
];

test("middleware's import graph is non-trivial (the walker actually walks)", () => {
  const graph = edgeGraph();
  // If resolution silently returned nothing, every assertion below would pass
  // over an empty set — the check would be green having examined no files.
  assert.ok(
    graph.length >= 3,
    `expected middleware to reach several lib/ modules, got ${graph.length}`,
  );
  assert.ok(
    graph.some((f) => f.endsWith("lib/authz.ts")),
    "expected lib/authz.ts in the graph — resolution is broken if it is absent",
  );
  assert.ok(
    graph.some((f) => f.endsWith("lib/constantTime.ts")),
    "expected lib/constantTime.ts in the graph — it is the module this guards",
  );
});

test("no module reachable from middleware.ts uses a Node-only builtin", () => {
  for (const file of edgeGraph()) {
    const source = stripComments(readFileSync(file, "utf8"));
    for (const pattern of FORBIDDEN) {
      assert.ok(
        !pattern.test(source),
        `${file.replace(`${PORTAL}/`, "")} matches ${pattern} — middleware runs ` +
          `on the Edge runtime, so this breaks \`next build\` and nothing else ` +
          `catches it`,
      );
    }
  }
});

// The SDK arrives as a BARE specifier, which the walker above deliberately
// does not follow — so the `node:` patterns never see the `node:async_hooks`
// inside it. instrumentation.ts already guards this by importing the SDK
// dynamically behind NEXT_RUNTIME; this is the check that notices if someone
// reaches for a span in middleware.ts and pulls the whole SDK onto the Edge.
//
// lib/tracing.ts is NOT forbidden: it imports @opentelemetry/api only, which
// is a no-op without a provider and runs on the Edge quite happily. Banning it
// would be a rule against working code, which is how guards get deleted.
const FORBIDDEN_ON_EDGE_PACKAGES = [
  /from\s+["']@opentelemetry\/sdk-/,
  /from\s+["']@opentelemetry\/exporter-/,
  /from\s+["'].*instrumentation\.node["']/,
];

test("no module reachable from middleware.ts pulls in the OTel SDK", () => {
  for (const file of edgeGraph()) {
    const source = stripComments(readFileSync(file, "utf8"));
    for (const pattern of FORBIDDEN_ON_EDGE_PACKAGES) {
      assert.ok(
        !pattern.test(source),
        `${file.replace(`${PORTAL}/`, "")} matches ${pattern} — the OTel Node SDK ` +
          `cannot load on the Edge runtime. Use lib/tracing.ts (API only) instead.`,
      );
    }
  }
});

test("constantTimeEquals matches identical strings", () => {
  assert.equal(constantTimeEquals("hunter2", "hunter2"), true);
  assert.equal(constantTimeEquals("", ""), true);
});

test("constantTimeEquals rejects differing content and differing lengths", () => {
  assert.equal(constantTimeEquals("hunter2", "hunter3"), false);
  assert.equal(constantTimeEquals("hunter2", "hunter22"), false);
  assert.equal(constantTimeEquals("", "x"), false);
});

test("constantTimeEquals compares BYTES, not code units", () => {
  // Two strings of equal .length but different UTF-8 byte length. Comparing by
  // code unit would index past one array and read undefined.
  assert.equal(constantTimeEquals("é", "e"), false);
  assert.equal(constantTimeEquals("café", "café"), true);
});

console.log(`\n${passed} passed`);
