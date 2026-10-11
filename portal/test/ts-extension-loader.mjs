// portal/test/ts-extension-loader.mjs — Node ESM loader hook that appends
// `.ts` to extensionless relative imports (e.g. `from "./db"`) before
// resolution. The portal's own source uses Next.js's bundler-mode module
// resolution (tsconfig.json moduleResolution: "bundler"), which allows
// extensionless imports — correct for how Next.js actually builds this
// code, not a bug to "fix" in the source. Plain `node --experimental-strip-types`
// has no bundler and needs the real extension, so this loader bridges the
// gap for tests run directly under Node instead of Next's build pipeline.
import { existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

// `@/x` is tsconfig.json's path alias for the portal root; routes import their
// libraries through it, so a test that drives a route needs it resolved too.
const PORTAL_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) {
    const target = path.join(PORTAL_ROOT, specifier.slice(2));
    const candidate = path.extname(target) ? target : `${target}.ts`;
    if (existsSync(candidate)) return nextResolve(pathToFileURL(candidate).href, context);
  }
  // Next's subpath entry points (`next/server`) are files Node's ESM resolver
  // only finds with their extension; the bundler adds it, this does here.
  if (specifier.startsWith("next/") && !path.extname(specifier)) {
    return nextResolve(`${specifier}.js`, context);
  }
  if (specifier.startsWith(".") && !path.extname(specifier)) {
    const parentPath = fileURLToPath(context.parentURL);
    const candidate = path.resolve(path.dirname(parentPath), `${specifier}.ts`);
    if (existsSync(candidate)) {
      return nextResolve(pathToFileURL(candidate).href, context);
    }
  }
  return nextResolve(specifier, context);
}
