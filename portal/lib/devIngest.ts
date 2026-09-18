// portal/lib/devIngest.ts — what the Dev ingest accepts (portal phase 1, S3,
// .agent-rfc/designs/portal-phase1.md).
//
// The body is the file `process_gate.py ci --json` writes, sent by an app's CI.
// It is data from outside the portal, validated here before anything is stored:
// types, catalogue values and lengths. Keys the gate does not write are dropped,
// never stored. A body that fails anywhere is refused whole.
//
// Pure — no database, no Next — so the tests run the same validator the route
// does.

import { isSafeHttpUrl } from "./safeUrl";

/** The record's shape version. Kept equal to DEV_RECORD_SCHEMA in scripts/process_gate.py. */
export const DEV_RECORD_SCHEMA = 1;

/** What the gate decided about a commit. Kept equal to the CHECK on dev_commits.verdict and to
 *  what scripts/process_gate.py emits (both pinned by tests). */
export const DEV_VERDICTS = ["passed", "failed", "passed_with_notes", "not_gated", "before_adoption"] as const;
export type DevVerdict = (typeof DEV_VERDICTS)[number];

export const PILLAR_KINDS = ["applies", "n/a", "gap", "deviation", "unrecognised"] as const;
export type PillarKind = (typeof PILLAR_KINDS)[number];

export const DEV_LIMITS = {
  /** Commits in one request. A longer range is sent in several. */
  commits: 500,
  /** Characters in a commit subject. */
  subject: 1000,
  /** Characters in one error, note, path, title or reason. */
  text: 4000,
  /** Entries in one list: errors, notes, repairs, scope, deviations, passes. */
  list: 200,
  /** Bytes in one request body. */
  bodyBytes: 2_000_000,
} as const;

export interface DevDeviation {
  id: string;
  textSha256: string;
  approvalId: string | null;
}

export interface DevDesign {
  ref: string;
  path: string | null;
  resolved: boolean;
  reason: string | null;
  title: string | null;
  status: string | null;
  scope: string[];
  pillars: Record<string, PillarKind>;
  deviations: DevDeviation[];
}

export interface DevReview {
  ref: string;
  path: string | null;
  resolved: boolean;
  reason: string | null;
  passes: { n: number; findings: number }[];
  signedOff: boolean | null;
  kgQuery: string | null;
}

export interface DevCommit {
  sha: string;
  parentSha: string | null;
  subject: string;
  authorName: string | null;
  authorEmail: string | null;
  committedAt: string | null;
  adopted: boolean;
  gated: boolean;
  verdict: DevVerdict;
  errors: string[];
  notes: string[];
  repairs: string[];
  design: DevDesign | null;
  review: DevReview | null;
}

export interface DevIngest {
  schema: number;
  head: string;
  ciRunUrl: string | null;
  commits: DevCommit[];
}

export type Parsed<T> = { ok: true; value: T } | { ok: false; error: string };

// ── the checks ───────────────────────────────────────────────────────────────

class Refused extends Error {}

const SHA = /^[0-9a-f]{40}(?:[0-9a-f]{24})?$/; // SHA-1, or SHA-256 repositories
const HEX64 = /^[0-9a-f]{64}$/;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function str(value: unknown, where: string, max: number = DEV_LIMITS.text): string {
  if (typeof value !== "string") throw new Refused(`${where} must be a string`);
  if (value.length > max) throw new Refused(`${where} is longer than ${max} characters`);
  return value;
}

function optStr(value: unknown, where: string, max: number = DEV_LIMITS.text): string | null {
  return value === null || value === undefined ? null : str(value, where, max);
}

function bool(value: unknown, where: string): boolean {
  if (typeof value !== "boolean") throw new Refused(`${where} must be true or false`);
  return value;
}

function sha(value: unknown, where: string): string {
  if (typeof value !== "string" || !SHA.test(value)) throw new Refused(`${where} must be a commit hash`);
  return value;
}

function list<T>(value: unknown, where: string, item: (v: unknown, w: string) => T): T[] {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) throw new Refused(`${where} must be a list`);
  if (value.length > DEV_LIMITS.list) throw new Refused(`${where} has more than ${DEV_LIMITS.list} entries`);
  return value.map((v, i) => item(v, `${where}[${i}]`));
}

function oneOf<T extends string>(value: unknown, allowed: readonly T[], where: string): T {
  if (typeof value !== "string" || !(allowed as readonly string[]).includes(value)) {
    throw new Refused(`${where} must be one of ${allowed.join(", ")}`);
  }
  return value as T;
}

function time(value: unknown, where: string): string | null {
  if (value === null || value === undefined || value === "") return null;
  const text = str(value, where, 64);
  if (Number.isNaN(Date.parse(text))) throw new Refused(`${where} is not a time`);
  return text;
}

function nonNegativeInt(value: unknown, where: string): number {
  if (!Number.isInteger(value) || (value as number) < 0) throw new Refused(`${where} must be a whole number`);
  return value as number;
}

function design(value: unknown, where: string): DevDesign | null {
  if (value === null || value === undefined) return null;
  if (!isObject(value)) throw new Refused(`${where} must be an object or null`);
  const pillars: Record<string, PillarKind> = {};
  if (value.pillars !== undefined && value.pillars !== null) {
    if (!isObject(value.pillars)) throw new Refused(`${where}.pillars must be an object`);
    const entries = Object.entries(value.pillars);
    if (entries.length > DEV_LIMITS.list) throw new Refused(`${where}.pillars has too many entries`);
    for (const [pillar, kind] of entries) {
      if (!/^P\d{1,3}$/.test(pillar)) throw new Refused(`${where}.pillars has a key that is not a pillar: ${pillar}`);
      pillars[pillar] = oneOf(kind, PILLAR_KINDS, `${where}.pillars.${pillar}`);
    }
  }
  return {
    ref: str(value.ref, `${where}.ref`),
    path: optStr(value.path, `${where}.path`),
    resolved: bool(value.resolved, `${where}.resolved`),
    reason: optStr(value.reason, `${where}.reason`),
    title: optStr(value.title, `${where}.title`),
    status: optStr(value.status, `${where}.status`, 32),
    scope: list(value.scope, `${where}.scope`, (v, w) => str(v, w)),
    pillars,
    deviations: list(value.deviations, `${where}.deviations`, (v, w) => {
      if (!isObject(v)) throw new Refused(`${w} must be an object`);
      if (typeof v.text_sha256 !== "string" || !HEX64.test(v.text_sha256)) {
        throw new Refused(`${w}.text_sha256 must be a SHA-256`);
      }
      return {
        id: str(v.id, `${w}.id`, 32),
        textSha256: v.text_sha256,
        approvalId: optStr(v.approval_id, `${w}.approval_id`, 32),
      };
    }),
  };
}

function review(value: unknown, where: string): DevReview | null {
  if (value === null || value === undefined) return null;
  if (!isObject(value)) throw new Refused(`${where} must be an object or null`);
  const signed = value.signed_off;
  if (signed !== undefined && signed !== null && typeof signed !== "boolean") {
    throw new Refused(`${where}.signed_off must be true, false or null`);
  }
  return {
    ref: str(value.ref, `${where}.ref`),
    path: optStr(value.path, `${where}.path`),
    resolved: bool(value.resolved, `${where}.resolved`),
    reason: optStr(value.reason, `${where}.reason`),
    passes: list(value.passes, `${where}.passes`, (v, w) => {
      if (!isObject(v)) throw new Refused(`${w} must be an object`);
      return { n: nonNegativeInt(v.n, `${w}.n`), findings: nonNegativeInt(v.findings, `${w}.findings`) };
    }),
    signedOff: typeof signed === "boolean" ? signed : null,
    kgQuery: optStr(value.kg_query, `${where}.kg_query`, 64),
  };
}

function commit(value: unknown, where: string): DevCommit {
  if (!isObject(value)) throw new Refused(`${where} must be an object`);
  return {
    sha: sha(value.commit, `${where}.commit`),
    parentSha: value.parent === null || value.parent === undefined ? null : sha(value.parent, `${where}.parent`),
    subject: str(value.subject, `${where}.subject`, DEV_LIMITS.subject),
    authorName: optStr(value.author_name, `${where}.author_name`, 320),
    authorEmail: optStr(value.author_email, `${where}.author_email`, 320),
    committedAt: time(value.committed_at, `${where}.committed_at`),
    adopted: bool(value.adopted, `${where}.adopted`),
    gated: bool(value.gated, `${where}.gated`),
    verdict: oneOf(value.verdict, DEV_VERDICTS, `${where}.verdict`),
    errors: list(value.errors, `${where}.errors`, (v, w) => str(v, w)),
    notes: list(value.notes, `${where}.notes`, (v, w) => str(v, w)),
    repairs: list(value.repairs, `${where}.repairs`, (v, w) => sha(v, w)),
    design: design(value.design, `${where}.design`),
    review: review(value.review, `${where}.review`),
  };
}

/** The body, validated whole, or the first reason it is refused. */
export function parseDevIngest(body: unknown): Parsed<DevIngest> {
  try {
    if (!isObject(body)) throw new Refused("the body must be a JSON object");
    if (body.schema !== DEV_RECORD_SCHEMA) {
      throw new Refused(
        `this portal reads record schema ${DEV_RECORD_SCHEMA}; this body declares schema ${String(body.schema)}`,
      );
    }
    if (!Array.isArray(body.commits)) throw new Refused("commits must be a list");
    if (body.commits.length > DEV_LIMITS.commits) {
      throw new Refused(`commits holds ${body.commits.length}; send at most ${DEV_LIMITS.commits} per request`);
    }
    const url = body.ci_run_url;
    if (url !== undefined && url !== null && !isSafeHttpUrl(url)) throw new Refused("ci_run_url must be an http(s) URL");
    return {
      ok: true,
      value: {
        schema: DEV_RECORD_SCHEMA,
        head: sha(body.head, "head"),
        ciRunUrl: typeof url === "string" ? url : null,
        commits: body.commits.map((c, i) => commit(c, `commits[${i}]`)),
      },
    };
  } catch (err) {
    if (err instanceof Refused) return { ok: false, error: err.message };
    throw err;
  }
}
