"use client";

// Stop this app. Asks for a reason, because the stop is on the record and someone
// will need to know why before resuming it.

import { useRouter } from "next/navigation";
import { useState } from "react";

export function StopControl({ tenantId }: { tenantId: string }) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function send(action: "stop" | "resume") {
    setMessage(null);
    const resp = await fetch("/api/ops/stop", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ tenantId, action, reason }),
    });
    const data = await resp.json().catch(() => ({}));
    setMessage(resp.ok ? (action === "stop" ? "Stopped." : "Resumed.") : (data.error ?? `HTTP ${resp.status}`));
    if (resp.ok) router.refresh();
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <input aria-label="Reason" placeholder="Reason" value={reason} onChange={(e) => setReason(e.target.value)}
        className="rounded-md border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.04] px-2 py-1" />
      <button type="button" disabled={!reason.trim()} onClick={() => send("stop")} className="px-3 py-1 rounded-md border border-red-600 text-red-700 dark:text-red-400 disabled:opacity-50">Stop app</button>
      <button type="button" disabled={!reason.trim()} onClick={() => send("resume")} className="px-3 py-1 rounded-md border border-black/20 dark:border-white/20 disabled:opacity-50">Resume</button>
      {message && <span role="status" className="text-black/60 dark:text-white/60">{message}</span>}
    </div>
  );
}
