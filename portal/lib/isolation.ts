// portal/lib/isolation.ts — the `isolation` enum shared by the tenants API
// route and the DB CHECK constraint (SPECS.md §23). Mirrors the
// `--isolation shared|dedicated` validation already in install-ai-stack.sh's
// ai-tenant-init.

export const ISOLATION_VALUES = ["shared", "dedicated"] as const;
export type Isolation = (typeof ISOLATION_VALUES)[number];

export function isValidIsolation(value: unknown): value is Isolation {
  return typeof value === "string" && (ISOLATION_VALUES as readonly string[]).includes(value);
}
