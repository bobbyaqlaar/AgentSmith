"use client";

// Approve or reject one gate. The reason is required: it is what makes a decision
// a decision someone can later answer for.

import { useRouter } from "next/navigation";
import { useState } from "react";

export function HitlDecision({ tenantId, recordId }: { tenantId: string; recordId: number }) {
  const router = useRouter();
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(approved: boolean) {
    setBusy(true);
    setError(null);
    try {
      const resp = await fetch("/api/hitl/decide", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ tenantId, recordId, approved, rationale }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const ready = rationale.trim().length > 0 && !busy;
  return (
    <div className="space-y-2">
      <label className="block text-xs text-black/60 dark:text-white/60">
        Your reason (recorded with your name)
        <textarea className="w-full text-sm rounded-md border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.04] px-2 py-1"
          rows={2} value={rationale} onChange={(e) => setRationale(e.target.value)} />
      </label>
      {error && <p className="text-xs text-red-700 dark:text-red-400" role="alert">{error}</p>}
      <div className="flex gap-2">
        <button type="button" disabled={!ready} onClick={() => decide(true)} className="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white disabled:opacity-50">Approve</button>
        <button type="button" disabled={!ready} onClick={() => decide(false)} className="px-3 py-1.5 text-sm rounded-md border border-red-600 text-red-700 dark:text-red-400 disabled:opacity-50">Reject</button>
      </div>
    </div>
  );
}
