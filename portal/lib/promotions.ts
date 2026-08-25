// portal/lib/promotions.ts — reads shadow-eval failures (scripts/shadow-eval.py,
// Product_Archive.md P1c) from a tenant's Phoenix and surfaces them as a
// read-only "suggested promotion" list. Promotion itself stays HITL-gated
// via `ai-stack-promote` — this is a queue for a human to act on, not an
// auto-promotion path (SPECS.md §9).

import { phoenixFetch } from "./phoenix";

/**
 * One scan of a tenant's shadow-eval annotations.
 *
 * `spansScanned` and `truncated` exist because the spans endpoint is
 * cursor-paginated (`next_cursor`) and this reads ONE page. The page below
 * renders "No shadow-eval failures in the last 24h" — a claim about a window —
 * and a one-page scan of a busy tenant does not support it. Following the
 * cursor to exhaustion is not the fix either: that is unbounded work on a page
 * render. Reporting the scope of what was actually looked at is.
 */
export interface PromotionScan {
  failures: SuggestedPromotion[];
  spansScanned: number;
  /** Phoenix said there was another page and this did not read it. */
  truncated: boolean;
}

export interface SuggestedPromotion {
  spanId: string;
  traceId: string | null;
  score: number;
  explanation: string;
  inputValue: string | null;
  outputValue: string | null;
}

interface PhoenixSpan {
  context: { span_id: string; trace_id: string };
  attributes?: Record<string, unknown>;
}

async function phoenixGet(phoenixBaseUrl: string, path: string, params: URLSearchParams): Promise<any> {
  const qs = params.toString();
  // Through lib/phoenix's shared client, so this hop is traced like the other
  // two. It had its own fetch — same trailing-slash strip, same 5s timeout,
  // no span — and stayed invisible when the portal was instrumented, on the
  // same page render as the calls that were not.
  const resp = await phoenixFetch(phoenixBaseUrl, `${path}${qs ? `?${qs}` : ""}`, {
    spanName: "portal.phoenix.rest",
    timeoutMs: 5000,
    attributes: { "http.route": path },
  });
  if (!resp.ok) throw new Error(`Phoenix REST HTTP ${resp.status}`);
  return resp.json();
}

/**
 * Returns shadow_eval annotations scored below the passing threshold over
 * the last `sinceHours`, for a human to review in the suggested-promotion
 * queue. Degrades to an empty list (not an error) if Phoenix is
 * unreachable or has no spans/annotations yet — same posture as
 * checkPhoenixHealth/getRecentTraceStats.
 */
export async function getSuggestedPromotions(
  phoenixBaseUrl: string,
  opts: { sinceHours?: number; project?: string } = {},
): Promise<PromotionScan | null> {
  // Returns null when the query FAILED, [] when it genuinely found nothing.
  // These are opposite facts and the page renders them differently: an empty
  // list says "no shadow-eval failures in the last 24h", which is a health
  // claim, and producing that from a Phoenix outage tells an operator the
  // tenant is fine when nobody actually looked. `getRecentTraceStats` in
  // lib/phoenix.ts already draws this distinction — same treatment here.
  const sinceHours = opts.sinceHours ?? 24;
  const project = opts.project ?? "default";
  try {
    const start = new Date(Date.now() - sinceHours * 60 * 60 * 1000);
    const spanParams = new URLSearchParams({ start_time: start.toISOString(), limit: "1000" });
    const spanData = await phoenixGet(phoenixBaseUrl, `/v1/projects/${project}/spans`, spanParams);
    const spans: PhoenixSpan[] = Array.isArray(spanData) ? spanData : spanData.data ?? [];
    // Non-null next_cursor means Phoenix has more for this window than one page.
    const truncated = !Array.isArray(spanData) && Boolean(spanData?.next_cursor);
    if (spans.length === 0) return { failures: [], spansScanned: 0, truncated };

    const spanById = new Map(spans.map((s) => [s.context.span_id, s]));
    const annotationParams = new URLSearchParams();
    for (const s of spans) annotationParams.append("span_ids", s.context.span_id);
    annotationParams.append("include_annotation_names", "shadow_eval");

    const annotationData = await phoenixGet(phoenixBaseUrl, `/v1/projects/${project}/span_annotations`, annotationParams);
    const annotations: any[] = Array.isArray(annotationData) ? annotationData : annotationData.data ?? [];

    const failures: SuggestedPromotion[] = [];
    for (const ann of annotations) {
      const result = ann.result ?? {};
      if (result.label !== "fail") continue;
      const span = spanById.get(ann.span_id);
      const attrs = span?.attributes ?? {};
      failures.push({
        spanId: ann.span_id,
        traceId: span?.context.trace_id ?? null,
        score: typeof result.score === "number" ? result.score : 0,
        explanation: result.explanation ?? "",
        inputValue: typeof attrs["input.value"] === "string" ? (attrs["input.value"] as string) : null,
        outputValue: typeof attrs["output.value"] === "string" ? (attrs["output.value"] as string) : null,
      });
    }
    return { failures, spansScanned: spans.length, truncated };
  } catch {
    return null;
  }
}
