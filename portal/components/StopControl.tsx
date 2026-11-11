"use client";

// Stop this app, or resume it. Asks for a reason, because the stop is on the record
// and someone will need to know why before resuming it. Shows only the action that
// applies, confirms a stop, sends once, and says when the request did not get
// through (the 4.1.0 release review, R28).

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { submitOnce } from "@/lib/submitOnce";

export function StopControl({ tenantId, stopped }: { tenantId: string; stopped: boolean }) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const inFlight = useRef({ busy: false });
  const action: "stop" | "resume" = stopped ? "resume" : "stop";

  async function send() {
    setMessage(null);
    setBusy(true);
    const result = await submitOnce(
      inFlight.current,
      async () => {
        const resp = await fetch("/api/ops/stop", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ tenantId, action, reason }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`);
      },
      () => action === "resume" || window.confirm(`Stop ${tenantId}? Every model call it makes will be refused until someone resumes it.`),
    );
    setBusy(false);
    if (result.ok) {
      setMessage(action === "stop" ? "Stopped." : "Resumed.");
      router.refresh();
    } else if (result.error) {
      setMessage(`Not ${action === "stop" ? "stopped" : "resumed"}: ${result.error}`);
    }
  }

  const ready = reason.trim().length > 0 && !busy;
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <input aria-label="Reason" placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)}
        className="rounded-md border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.04] px-2 py-1" />
      {action === "stop" ? (
        <button type="button" disabled={!ready} onClick={send} className="px-3 py-1 rounded-md border border-red-600 text-red-700 dark:text-red-400 disabled:opacity-50">{busy ? "Stopping…" : "Stop app"}</button>
      ) : (
        <button type="button" disabled={!ready} onClick={send} className="px-3 py-1 rounded-md border border-black/20 dark:border-white/20 disabled:opacity-50">{busy ? "Resuming…" : "Resume"}</button>
      )}
      {message && <span role="status" className="text-black/60 dark:text-white/60">{message}</span>}
    </div>
  );
}
