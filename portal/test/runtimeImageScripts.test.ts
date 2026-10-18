// portal/test/runtimeImageScripts.test.ts — the npm scripts the built image is
// expected to run only reference paths the image actually carries.
//
// Dockerfile's final stage copies scripts/ and db/ with this comment:
//
//   "copied explicitly so `docker compose run portal npm run db:migrate` works
//    against the running image without a separate build step"
//
// That is a claim about a command, and nothing read it. `db:migrate` passed
// --experimental-loader=./test/ts-extension-loader.mjs, and the final stage does
// not copy test/, so the documented command died with ERR_MODULE_NOT_FOUND —
// found on 2026-10-18 while bringing the portal up for the demo, probably never
// having worked against a built image.
//
// The loader itself is right for the tests beside it: run under plain Node they
// need `.ts` and `@/…` resolved, which Next's bundler does at build time.
// scripts/migrate.ts imports only node builtins and pg, so it needs none of it.
//
// The checks are a function over (package.json, Dockerfile), so the tests at the
// bottom can feed it synthetic inputs and prove the guard's own rails still
// bite. Without those, a mutant that made this check vacuous survived — the
// first version of this file passed while db:migrate was still broken.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const PORTAL = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

/** Scripts the built image is expected to run, and why each one is on the list. */
const RUNTIME_SCRIPTS: Record<string, string> = {
  "db:migrate":
    "Dockerfile's final stage copies scripts/ and db/ expressly so this runs against the image",
};

/** Paths the final stage copies in, as top-level entries under /app. */
export function carriedByFinalStage(dockerfile: string): Set<string> {
  const stages = dockerfile.split(/^FROM .*$/m);
  const final = stages[stages.length - 1];
  assert.ok(
    final && final.trim().length > 0,
    "could not find the Dockerfile's final stage — this test cannot check anything",
  );

  const carried = new Set<string>();
  for (const line of final.split("\n")) {
    const m = line.match(/^\s*COPY\s+.*?\s+(\S+)\s*$/);
    if (!m) continue;
    const destination = m[1].replace(/^\.\//, "").replace(/\/$/, "");
    if (destination === "" || destination === ".") {
      // `COPY .next/standalone ./` unpacks Next's standalone bundle at /app.
      // Enumerated rather than treated as "everything": as a wildcard it made
      // this whole check vacuous.
      for (const fromStandalone of ["server.js", "node_modules", ".next", "package.json"]) {
        carried.add(fromStandalone);
      }
      continue;
    }
    carried.add(destination.split("/")[0]);
  }
  assert.ok(carried.size > 0, "no COPY destinations found in the final stage");
  return carried;
}

/** Relative file paths a command line names (flags included). */
export function referencedPaths(command: string): string[] {
  const found = new Set<string>();
  for (const token of command.split(/\s+/)) {
    const candidate = token.includes("=") ? token.slice(token.indexOf("=") + 1) : token;
    if (/^[.]{0,2}\/?[\w./-]+\.(ts|mjs|cjs|js|sql|json)$/.test(candidate) && !candidate.startsWith("-")) {
      found.add(candidate.replace(/^\.\//, ""));
    }
  }
  return [...found];
}

/** Throws unless every path each runtime script names is carried by the image. */
export function checkRuntimeScripts(
  pkg: { scripts?: Record<string, string> },
  dockerfile: string,
  runtimeScripts: Record<string, string> = RUNTIME_SCRIPTS,
): void {
  const carried = carriedByFinalStage(dockerfile);

  for (const [name, why] of Object.entries(runtimeScripts)) {
    const command = pkg.scripts?.[name];
    assert.ok(command, `package.json has no "${name}" script — ${why}`);

    const paths = referencedPaths(command);
    assert.ok(
      paths.length > 0,
      `no file paths found in "${name}" — the check would pass by matching nothing`,
    );

    for (const referenced of paths) {
      const top = referenced.split("/")[0];
      assert.ok(
        carried.has(top),
        `"${name}" references ${referenced}, but the image's final stage does not copy ${top}/ ` +
          `(it carries: ${[...carried].sort().join(", ")}). ${why}`,
      );
    }
  }
}

function realFiles() {
  return {
    pkg: JSON.parse(readFileSync(path.join(PORTAL, "package.json"), "utf-8")),
    dockerfile: readFileSync(path.join(PORTAL, "Dockerfile"), "utf-8"),
  };
}

test("every script the image must run references only paths the image carries", () => {
  const { pkg, dockerfile } = realFiles();
  checkRuntimeScripts(pkg, dockerfile);
});

test("the loader the tests need is not required by a script the image runs", () => {
  const { pkg } = realFiles();
  for (const name of Object.keys(RUNTIME_SCRIPTS)) {
    const command: string = pkg.scripts?.[name] ?? "";
    assert.ok(
      !command.includes("test/"),
      `"${name}" reaches into test/, which the runtime image does not carry: ${command}`,
    );
  }
});

// ── guard the guard: each rail, proven to bite ──────────────────────────────

const DOCKERFILE_SHAPE = [
  "FROM node:22-alpine AS build",
  "COPY . .",
  "FROM node:22-alpine AS runner",
  "COPY --from=build /app/.next/standalone ./",
  "COPY --from=build /app/scripts ./scripts",
].join("\n");

test("the standalone bundle is enumerated, never a wildcard", () => {
  const carried = carriedByFinalStage(DOCKERFILE_SHAPE);
  assert.ok(!carried.has("."), "a '.' entry would let any path pass and make this file pointless");
  assert.deepEqual(
    [...carried].sort(),
    [".next", "node_modules", "package.json", "scripts", "server.js"],
  );
  // and the consequence: a script reaching outside those is refused
  assert.throws(
    () => checkRuntimeScripts(
      { scripts: { "db:migrate": "node --experimental-loader=./test/x.mjs scripts/migrate.ts" } },
      DOCKERFILE_SHAPE,
    ),
    /does not copy test\//,
  );
});

test("a script naming no paths is refused rather than passing", () => {
  assert.throws(
    () => checkRuntimeScripts({ scripts: { "db:migrate": "echo nothing to see" } }, DOCKERFILE_SHAPE),
    /would pass by matching nothing/,
  );
});

test("a Dockerfile this cannot parse is refused rather than passing", () => {
  assert.throws(() => carriedByFinalStage(""), /could not find the Dockerfile's final stage/);
  assert.throws(
    () => carriedByFinalStage("FROM node:22-alpine AS runner\nRUN echo no copies here\n"),
    /no COPY destinations found/,
  );
});

test("a missing runtime script is refused rather than skipped", () => {
  assert.throws(
    () => checkRuntimeScripts({ scripts: {} }, DOCKERFILE_SHAPE),
    /has no "db:migrate" script/,
  );
});
