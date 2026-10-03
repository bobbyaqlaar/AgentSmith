// portal/test/recordCases.ts — a record contract case's body: fixture.json's
// record with the one thing the case changes (contract/record/v1/cases.json says
// how). The same rules as runtime/conformance.py's record_body, which runs the
// cases against any receiver over HTTP.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export interface RecordCase {
  name: string;
  token: "valid" | "unknown" | "none";
  expect: number;
  why?: string;
  set?: Record<string, unknown>;
  repeat_commits?: number;
  pad?: number;
}

const CONTRACT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "contract", "record", "v1");

export function recordBody(c: RecordCase): string {
  const body = structuredClone(JSON.parse(readFileSync(join(CONTRACT, "fixture.json"), "utf8")).record);
  for (const [path, value] of Object.entries(c.set ?? {})) {
    const keys = path.split(".");
    const last = keys.pop()!;
    let node = body;
    for (const key of keys) node = Array.isArray(node) ? node[Number(key)] : node[key];
    if (Array.isArray(node)) node[Number(last)] = value;
    else node[last] = value;
  }
  if (c.repeat_commits) body.commits = Array(c.repeat_commits).fill(body.commits[0]);
  if (c.pad) body._pad = "x".repeat(c.pad);
  return JSON.stringify(body);
}
