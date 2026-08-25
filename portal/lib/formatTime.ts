// portal/lib/formatTime.ts — how this portal prints an instant.
//
// Split from components/ui/Timestamp.tsx for the reason lib/authz.ts is split
// from lib/currentAccess.ts and lib/auditSignature.ts from lib/auditLog.ts:
// `npm test` runs bare `node --experimental-strip-types`, which cannot load a
// .tsx at all ("Unknown file extension"). Pure logic that lives beside JSX is
// pure logic nothing can test.
//
// WHY UTC, STATED. `new Date(x).toLocaleString()` appeared three times — twice
// in SERVER components, so it formatted in the container's timezone (UTC on
// Cloud Run), and once in a client component, so it formatted in the browser's.
// The same product printed the same kind of fact in two zones depending on
// which page you were on, and labelled neither. On an audit log that is not
// cosmetic.
//
// It was also a hydration bug: client components are server-rendered for the
// initial HTML, so the browser recomputed a different string and React patched
// the mismatch. `toISOString` is deterministic — same input, same output, in
// Node and in a browser — which is what makes the markup stable.

export function formatUtc(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  // Absent, not "Invalid Date": a timestamp the database did not give us must
  // not render as a plausible-looking string.
  if (Number.isNaN(date.getTime())) return "\u2014";
  // 2026-08-25T14:03:12.482Z -> 2026-08-25 14:03:12 UTC
  return `${date.toISOString().slice(0, 19).replace("T", " ")} UTC`;
}

/** The machine-readable form for <time dateTime>, or undefined when unparseable. */
export function isoOrUndefined(value: string | Date): string | undefined {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}
