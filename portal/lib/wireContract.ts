// portal/lib/wireContract.ts — what a given AgentSmith version can emit.
//
// WHY THE PORTAL NEEDS THIS. AgentSmith and the tenants that use it have
// different owners and different cadences: IT operations runs the framework and
// this portal, the business runs the tenant apps and pins a framework version
// so IT's releases cannot move underneath them. That is the design, and the pin
// is what makes it work.
//
// What follows from it is that this portal is ALWAYS reading a fleet spanning
// several framework versions, and a version decides which fields a tenant is
// capable of populating at all. A tenant on v1.2.0 reports no tokens, no cost
// and no trace id — none of those existed. In `agent_runs` that is a NULL, and
// it is the same NULL a current tenant writes when its provider reported no
// usage or its exporter is misconfigured.
//
// One value, two meanings, on the product whose users are IT ops. This module
// splits them.
//
// THE PRIMARY SIGNAL IS THE COLUMN'S OWN PRESENCE. `framework_version` began
// being reported in the same release that added the fields below, so a row with
// no version is, by construction, from a framework that predates all of them —
// no version table required, and no guess about which release a row came from.
// The table matters for what comes NEXT: when 1.4 adds a field, 1.3 tenants
// will legitimately lack it and this is where that gets written down.

/** Fields whose absence is ambiguous without knowing the emitting version. */
export type WireField = "inputTokens" | "outputTokens" | "costUsd" | "traceId";

/**
 * The pending release — the one that first reports `framework_version` and the
 * fields above. Declared once because it is a guess until the release is cut;
 * `test/wireContract.test.ts` fails if the CHANGELOG's compatibility matrix
 * gains a row that disagrees, so the guess cannot quietly become wrong.
 */
export const FIRST_VERSIONED_RELEASE = "1.3.0";

const EMITS_SINCE: Record<WireField, string> = {
  inputTokens: FIRST_VERSIONED_RELEASE,
  outputTokens: FIRST_VERSIONED_RELEASE,
  costUsd: FIRST_VERSIONED_RELEASE,
  traceId: FIRST_VERSIONED_RELEASE,
};

export interface ParsedVersion {
  major: number;
  minor: number;
  patch: number;
  /** `+src` — a working copy, not a release artifact. See runtime/version.py. */
  fromSource: boolean;
}

export function parseVersion(value: string | null | undefined): ParsedVersion | null {
  if (!value) return null;
  const m = /^(\d+)\.(\d+)\.(\d+)(\+src)?$/.exec(value.trim());
  if (!m) return null;
  return {
    major: Number(m[1]),
    minor: Number(m[2]),
    patch: Number(m[3]),
    fromSource: Boolean(m[4]),
  };
}

function atLeast(v: ParsedVersion, target: string): boolean {
  const t = parseVersion(target);
  if (!t) return false;
  if (v.major !== t.major) return v.major > t.major;
  if (v.minor !== t.minor) return v.minor > t.minor;
  return v.patch >= t.patch;
}

/**
 * Whether `version` emits `field`.
 *
 * THREE STATES, not two, and that is the whole point of the module.
 *
 *  - `"yes"`     — this version emits it, so a NULL is a real gap worth chasing.
 *  - `"no"`      — this version cannot emit it; a NULL is expected and means nothing.
 *  - `"unknown"` — we cannot say. Either no version was reported by something
 *                  that also did not report the field (so the row predates
 *                  versioning), or the version is unparseable, or it is a `+src`
 *                  build whose number does not bound what it contains. Rendering
 *                  "unknown" as either of the other two is how a fleet view
 *                  starts lying.
 */
export function emits(
  version: string | null | undefined,
  field: WireField,
): "yes" | "no" | "unknown" {
  const parsed = parseVersion(version);
  if (!parsed) {
    // No version at all: the row was written by a framework that predates
    // version reporting, which is also the framework that predates every field
    // in EMITS_SINCE. An unparseable string lands here too — same answer for a
    // different reason, and neither is worth guessing about.
    return version ? "unknown" : "no";
  }
  if (parsed.fromSource) {
    // A working copy sitting between two releases. Its number says which
    // release it descends from and nothing about what it actually contains.
    return "unknown";
  }
  return atLeast(parsed, EMITS_SINCE[field]) ? "yes" : "no";
}

/**
 * A sentence for a cell that has no value, or null when the value is simply
 * missing and the caller should say so in its own words.
 *
 * The UI rule this exists to enforce: an empty cell must never be rendered the
 * same way for "this version never reported it" and "this version should have
 * and did not". The first is a fact about the fleet; the second is a fault.
 */
export function explainAbsent(
  version: string | null | undefined,
  field: WireField,
): string | null {
  switch (emits(version, field)) {
    case "no":
      return version
        ? `not reported by AgentSmith ${version}`
        : `not reported by this tenant's AgentSmith version (pre-${FIRST_VERSIONED_RELEASE})`;
    case "unknown":
      return `AgentSmith ${version} — cannot tell whether this is reported`;
    case "yes":
      return null; // a genuine gap; the caller decides what to say about it
  }
}

/** How many tenants/runs are on each version — the fleet view IT actually wants. */
export function versionBreakdown(
  versions: (string | null | undefined)[],
): { version: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const v of versions) {
    const key = v?.trim() || `pre-${FIRST_VERSIONED_RELEASE}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([version, count]) => ({ version, count }))
    .sort((a, b) => b.count - a.count || a.version.localeCompare(b.version));
}
