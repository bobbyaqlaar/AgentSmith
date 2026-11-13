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

/** When a signature stops counting. A recurring obligation's period comes from the
 *  catalogue; a later or missing `expires_at` does not stretch it (the 4.1.0 release
 *  review, R15). Mirrors `expires` in scripts/compliance_port.py. */
export function expiresAt(record: AttestationRecord, recurrenceDays: number | null): number | null {
  const given = record.expires_at === null ? null : Date.parse(record.expires_at);
  if (!recurrenceDays) return given;
  const due = Date.parse(record.attested_at) + recurrenceDays * DAY;
  return given === null ? due : Math.min(due, given);
}

/** One row per obligation. A mechanism-backed row reads `automatic`: CI is what checks it. */
export function checklist(rows: ObligationRow[], records: AttestationRecord[], now: Date): ChecklistRow[] {
  return rows.map((obligation) => {
    if (obligation.class !== "attested") return { obligation, state: "automatic", latest: null };
    const mine = records
      .filter((r) => r.obligation === obligation.id && Date.parse(r.attested_at) <= now.getTime() + 5 * 60_000)
      .sort((a, b) => Date.parse(b.attested_at) - Date.parse(a.attested_at));
    if (mine.length === 0) return { obligation, state: "missing", latest: null };
    // The newest signature still live counts, as in the port's `latest_valid`: judging only
    // the newest made a short-lived later signature hide a live earlier one (the 4.1.0
    // review's second pass, P2-R20). Both are held to fixtures/compliance/signature_cases.json.
    const live = mine.find((r) => { const until = expiresAt(r, obligation.recurrence_days); return until === null || until > now.getTime(); });
    if (!live) return { obligation, state: "expired", latest: mine[0] };
    const until = expiresAt(live, obligation.recurrence_days);
    if (until === null) return { obligation, state: "signed", latest: live };
    return { obligation, state: until - now.getTime() <= EXPIRING_DAYS * DAY ? "expiring" : "signed", latest: live };
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

const normalised = (value: string) => value.trim().toLowerCase();

/** The rule that a person does not approve their own request. The requester must be
 *  the sign-in email the app sent; one that is not an email cannot be told apart from
 *  the reviewer, so nobody may decide it (the 4.1.0 release review, R29). */
export function mayDecide(actor: string, requestedBy: string | null): boolean {
  if (!requestedBy) return true;
  const who = normalised(requestedBy);
  return /^[^@\s]+@[^@\s]+$/.test(who) && who !== normalised(actor);
}
