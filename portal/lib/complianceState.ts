// portal/lib/complianceState.ts — what the checklist shows for one app. Pure, so
// the tests run the same logic the page does.

export interface ObligationRow {
  id: string;
  title: string;
  refs: Record<string, Array<string | number>>;
  layer: "provider" | "app" | "org";
  class: "enforced" | "verified" | "attested";
  phases: Array<"design" | "build" | "deploy" | "operate">;
  mechanism: string | null;
  owner_role: string;
  recurrence_days: number | null;
  instructions: string;
  evidence: string;
  blocks: Array<"ci" | "production">;
  profiles: string[];
}

export interface AttestationRecord {
  id: string;
  obligation: string;
  actor: string;
  role: string;
  evidence: string;
  attested_at: string;
  expires_at: string | null;
  note: string;
  channel: "tty" | "portal";
}

export type RowState = "signed" | "expiring" | "expired" | "missing" | "automatic";

export interface ChecklistRow {
  obligation: ObligationRow;
  state: RowState;
  latest: AttestationRecord | null;
}

const EXPIRING_DAYS = 30;
const DAY = 86_400_000;

/** One row per obligation. A mechanism-backed row reads `automatic`: CI is what checks it. */
export function checklist(rows: ObligationRow[], records: AttestationRecord[], now: Date): ChecklistRow[] {
  return rows.map((obligation) => {
    if (obligation.class !== "attested") return { obligation, state: "automatic", latest: null };
    const mine = records
      .filter((r) => r.obligation === obligation.id)
      .sort((a, b) => Date.parse(b.attested_at) - Date.parse(a.attested_at));
    const latest = mine[0] ?? null;
    if (!latest) return { obligation, state: "missing", latest };
    if (latest.expires_at === null) return { obligation, state: "signed", latest };
    const left = Date.parse(latest.expires_at) - now.getTime();
    if (left <= 0) return { obligation, state: "expired", latest };
    return { obligation, state: left <= EXPIRING_DAYS * DAY ? "expiring" : "signed", latest };
  });
}

export const LIMITS = { evidence: 2000, note: 2000, id: 64, actor: 320, role: 64, batch: 500 } as const;

function text(value: unknown, max: number): string | null {
  return typeof value === "string" && value.length > 0 && value.length <= max ? value : null;
}

/** A batch of signatures from a repository. One bad record refuses the batch. */
export function parseAttestations(raw: unknown, known: Set<string>): { ok: true; value: AttestationRecord[] } | { ok: false; error: string } {
  const list = (raw as { attestations?: unknown })?.attestations;
  if (!Array.isArray(list)) return { ok: false, error: "attestations must be a list" };
  if (list.length > LIMITS.batch) return { ok: false, error: `more than ${LIMITS.batch} attestations` };
  const value: AttestationRecord[] = [];
  for (const [index, item] of list.entries()) {
    const r = item as Record<string, unknown>;
    const id = text(r?.id, LIMITS.id);
    const obligation = text(r?.obligation, LIMITS.id);
    const actor = text(r?.actor, LIMITS.actor);
    const role = text(r?.role, LIMITS.role);
    const evidence = text(r?.evidence, LIMITS.evidence);
    const attestedAt = text(r?.attested_at, 64);
    const expiresAt = r?.expires_at === null || r?.expires_at === undefined ? null : text(r.expires_at, 64);
    const note = r?.note === undefined || r?.note === "" ? "" : text(r.note, LIMITS.note);
    if (!id || !obligation || !actor || !role || !evidence || !attestedAt || note === null) {
      return { ok: false, error: `attestation ${index} is incomplete` };
    }
    if (!known.has(obligation)) return { ok: false, error: `attestation ${index}: unknown obligation ${obligation}` };
    if (r.channel !== "tty") return { ok: false, error: `attestation ${index}: a repository's record has channel "tty"` };
    if (Number.isNaN(Date.parse(attestedAt)) || (expiresAt !== null && Number.isNaN(Date.parse(expiresAt)))) {
      return { ok: false, error: `attestation ${index}: a date does not parse` };
    }
    if (r.expires_at !== null && r.expires_at !== undefined && expiresAt === null) {
      return { ok: false, error: `attestation ${index}: expires_at is not a date` };
    }
    value.push({ id, obligation, actor, role, evidence, attested_at: attestedAt, expires_at: expiresAt, note, channel: "tty" });
  }
  return { ok: true, value };
}

/** The rule that a person does not approve their own request. */
export function mayDecide(actor: string, requestedBy: string | null): boolean {
  return !requestedBy || requestedBy.toLowerCase() !== actor.toLowerCase();
}
