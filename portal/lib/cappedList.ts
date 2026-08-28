// portal/lib/cappedList.ts — a list the database truncated, and how many rows
// there actually are.
//
// Two list queries carry a hardcoded LIMIT — unresolved issues at 200, DLQ
// entries at 100 — and both returned a bare array. A caller cannot tell a
// tenant with 200 issues from a tenant with 3,000, and the tenant detail page
// rendered `issues.length` as the "Unresolved issues" metric while the
// dashboard rendered a real SQL `COUNT(*)` for the same tenant. Above the cap
// they disagreed, and the smaller, wrong number was on the page an operator
// opens to investigate.
//
// The type is shared rather than written twice because the mistake is the same
// mistake: a truncated list presented as the whole one (review-levers: failure-is-not-a-result), and
// one fact with two values (15).

export interface CappedList<T> {
  entries: T[];
  /** Rows matching the query, before the LIMIT. */
  total: number;
  /** The LIMIT that produced `entries`. */
  limit: number;
}

export function capped<T>(entries: T[], total: number, limit: number): CappedList<T> {
  return { entries, total, limit };
}

/** True when the database had more to give. Rendered, never assumed. */
export function isTruncated<T>(list: CappedList<T>): boolean {
  return list.total > list.entries.length;
}
