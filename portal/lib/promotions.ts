// portal/lib/promotions.ts — reads shadow-eval failures (scripts/shadow-eval.py,
// Product_Archive.md P1c) from a tenant's Phoenix and surfaces them as a
// read-only "suggested promotion" list. Promotion itself stays HITL-gated
// via `ai-stack-promote` — this is a queue for a human to act on, not an
// auto-promotion path (SPECS.md §9).

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
  const resp = await fetch(`${phoenixBaseUrl.replace(/\/$/, "")}${path}${qs ? `?${qs}` : ""}`, {
    signal: AbortSignal.timeout(5000),
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
): Promise<SuggestedPromotion[]> {
  const sinceHours = opts.sinceHours ?? 24;
  const project = opts.project ?? "default";
  try {
    const start = new Date(Date.now() - sinceHours * 60 * 60 * 1000);
    const spanParams = new URLSearchParams({ start_time: start.toISOString(), limit: "1000" });
    const spanData = await phoenixGet(phoenixBaseUrl, `/v1/projects/${project}/spans`, spanParams);
    const spans: PhoenixSpan[] = Array.isArray(spanData) ? spanData : spanData.data ?? [];
    if (spans.length === 0) return [];

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
    return failures;
  } catch {
    return [];
  }
}
