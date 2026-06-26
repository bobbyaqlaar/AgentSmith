// Semantic status pill, reused everywhere a status appears: tenant
// healthy/degraded/failed, MAJOR/CRITICAL issues, DLQ entry status
// (pending/replayed/discarded), agent_runs status.
export type BadgeTone = "success" | "warning" | "danger" | "neutral";

const TONE_CLASSES: Record<BadgeTone, string> = {
  success: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  warning: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  danger: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  neutral: "bg-black/10 text-black/70 dark:bg-white/10 dark:text-white/70",
};

export function Badge({ tone, children }: { tone: BadgeTone; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center text-xs font-mono px-2 py-0.5 rounded-md ${TONE_CLASSES[tone]}`}>
      {children}
    </span>
  );
}

export function toneForLevel(level: string): BadgeTone {
  if (level === "CRITICAL") return "danger";
  if (level === "MAJOR") return "warning";
  return "neutral";
}

export function toneForRunStatus(status: string): BadgeTone {
  if (status === "success") return "success";
  if (status === "degraded") return "warning";
  if (status === "failed") return "danger";
  return "neutral"; // "running" / "unknown"
}

// DLQ entry reason (runtime/dead_letter.py's REASON_* constants) —
// "needs a human decision" (warning) vs. "needs an engineer" (danger),
// the distinction FIXES_AND_CLEANUP.md's HITL/DLQ redesign added a
// structured `reason` column specifically to let this view render.
export function toneForDlqReason(reason: string | null): BadgeTone {
  if (reason === "infra_error") return "danger";
  if (reason === "validation_error" || reason === "tool_call_error" || reason === "hitl_timeout" || reason === "hitl_rejected") {
    return "warning";
  }
  return "neutral";
}
