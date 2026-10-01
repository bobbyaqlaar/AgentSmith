// portal/test/brand.test.ts — the AgentSmith and Aqlaar marks reach the page in
// production, not only in `next dev` (.agent-rfc/designs/portal-brand.md).
//
// portal/Dockerfile copies .next/standalone and .next/static into the image and
// NOT public/, so a file served from public/ works locally and 404s in the
// image. The marks are imported as modules instead, which lands them in
// .next/static. These tests keep it that way.

import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PORTAL = resolve(dirname(fileURLToPath(import.meta.url)), "..");

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

/** Width, height and colour type from a PNG's IHDR chunk; colour type 6 is RGBA. */
function png(path: string): { width: number; height: number; rgba: boolean } {
  const bytes = readFileSync(path);
  assert.equal(bytes.subarray(1, 4).toString("ascii"), "PNG", `${path} is not a PNG`);
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20), rgba: bytes[25] === 6 };
}

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? sources(join(dir, e.name)) : /\.tsx?$/.test(e.name) ? [join(dir, e.name)] : [],
  );
}

test("the portal has no public/ folder — the Docker image would not serve it", () => {
  const dockerfile = readFileSync(join(PORTAL, "Dockerfile"), "utf8");
  if (!/COPY[^\n]*\bpublic\b/.test(dockerfile)) {
    assert.ok(!existsSync(join(PORTAL, "public")), "portal/public exists, and portal/Dockerfile does not copy it");
  }
});

test("no page or component points at a root-relative file, which would mean public/", () => {
  const offenders = [...sources(join(PORTAL, "app")), ...sources(join(PORTAL, "components"))].filter((f) =>
    /\bsrc=["'{]\s*["']?\/(?!\/)/.test(readFileSync(f, "utf8")),
  );
  assert.deepEqual(offenders, []);
});

test("the layout imports both marks as modules, unoptimized", () => {
  const layout = readFileSync(join(PORTAL, "app", "layout.tsx"), "utf8");
  assert.match(layout, /import \w+ from "@\/assets\/brand\/agentsmith-mark\.png"/);
  assert.match(layout, /import \w+ from "@\/assets\/brand\/aqlaar\.png"/);
  // The optimizer needs sharp in standalone mode; the portal does not install it.
  const images = layout.match(/<Image\b[^>]*>/g) ?? [];
  assert.ok(images.length >= 2, "expected both marks to be rendered with next/image");
  for (const tag of images) assert.match(tag, /\bunoptimized\b/, tag);
});

test("the image module type is declared in a tracked file, not only in the generated next-env.d.ts", () => {
  // next-env.d.ts is written by \`next build\` and gitignored; CI type-checks before
  // it builds. Without a tracked declaration, tsc passes on any machine that has
  // built once and fails in CI — which is how the first push of these marks failed.
  const declared = join(PORTAL, "assets", "brand", "images.d.ts");
  assert.ok(existsSync(declared), "assets/brand/images.d.ts is missing");
  assert.match(readFileSync(declared, "utf8"), /^\/\/\/ <reference types="next\/image-types\/global" \/>$/m);
});

test("each mark is a transparent PNG sized for where it is shown", () => {
  const mark = png(join(PORTAL, "assets", "brand", "agentsmith-mark.png"));
  assert.deepEqual(mark, { width: 128, height: 128, rgba: true });
  const aqlaar = png(join(PORTAL, "assets", "brand", "aqlaar.png"));
  assert.equal(aqlaar.width, 96);
  assert.ok(aqlaar.rgba);
  const icon = png(join(PORTAL, "app", "icon.png"));
  assert.deepEqual(icon, { width: 64, height: 64, rgba: true });
});

console.log(`\n${passed} passed`);
