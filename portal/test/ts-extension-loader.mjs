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

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith(".") && !path.extname(specifier)) {
    const parentPath = fileURLToPath(context.parentURL);
    const candidate = path.resolve(path.dirname(parentPath), `${specifier}.ts`);
    if (existsSync(candidate)) {
      return nextResolve(pathToFileURL(candidate).href, context);
    }
  }
  return nextResolve(specifier, context);
}
