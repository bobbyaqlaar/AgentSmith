"use client";

import { useState } from "react";
import { Badge, toneForDlqReason } from "./ui/Badge";
import type { DLQEntry } from "@/lib/dlq";

// CRM example (Product_Archive.md HITL/DLQ redesign): the agent
// hallucinated {"account_status": "active"} where the schema expects
// "status" — an operator edits the JSON below to {"status": "active"}
// and clicks Replay. If the entry has a workflowId/gateId (came from
// run_with_recoverable_step, not a terminal dead-letter), Replay resumes
// the SAME live, still-parked workflow instead of restarting anything.
export function DlqEntryCard({ entry }: { entry: DLQEntry }) {
  const [text, setText] = useState(() => JSON.stringify(entry.payload, null, 2));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [resolved, setResolved] = useState(false);

  const parseError = (() => {
    try {
      JSON.parse(text);
      return null;
    } catch (e) {
      return e instanceof Error ? e.message : "Invalid JSON";
    }
  })();

  async function replay() {
    setBusy(true);
    setMessage(null);
    try {
      const payload = JSON.parse(text);
      const resp = await fetch(`/api/dlq/${entry.taskId}/replay`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ payload }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`);
      setMessage({
        kind: "ok",
        text: data.resumable
          ? "Replayed — live workflow resumed with this payload."
          : "Sent to the tenant's webhook, but this entry has no live workflow to resume (it's from a terminal dead-letter, not a parked one) — what happens next is up to the tenant's own receiver.",
      });
      setResolved(true);
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof Error ? e.message : "Replay failed" });
    } finally {
      setBusy(false);
    }
  }

  async function discard() {
    setBusy(true);
    setMessage(null);
    try {
      const resp = await fetch(`/api/dlq/${entry.taskId}/discard`, { method: "POST" });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`);
      setResolved(true);
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof Error ? e.message : "Discard failed" });
    } finally {
      setBusy(false);
    }
  }

  if (resolved) {
    return (
      <div className="border border-black/10 dark:border-white/10 rounded-lg p-4 text-sm text-black/50 dark:text-white/50">
        {entry.taskId} — resolved.
      </div>
    );
  }

  return (
    <div className="border border-black/10 dark:border-white/10 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs font-mono text-black/50 dark:text-white/50">
          <span>{entry.taskId}</span>
          {entry.reason && <Badge tone={toneForDlqReason(entry.reason)}>{entry.reason}</Badge>}
          {entry.workflowId && (
            <span title="Resumable — this entry came from a live, still-parked workflow">▶ {entry.workflowId}</span>
          )}
        </div>
        <span className="text-xs text-black/40 dark:text-white/40">{new Date(entry.createdAt).toLocaleString()}</span>
      </div>

      <p className="text-sm text-red-700 dark:text-red-400">{entry.error}</p>

      <textarea
        className="w-full font-mono text-xs rounded-md border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] p-2"
        rows={6}
        value={text}
        onChange={(e) => setText(e.target.value)}
        spellCheck={false}
      />
      {parseError && <p className="text-xs text-red-700 dark:text-red-400">{parseError}</p>}

      <div className="flex items-center gap-2">
        <button
          className="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          disabled={busy || !!parseError}
          onClick={replay}
        >
          Replay{entry.workflowId ? " (resume workflow)" : ""}
        </button>
        <button
          className="px-3 py-1.5 text-sm rounded-md border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-50"
          disabled={busy}
          onClick={discard}
        >
          Discard
        </button>
        {message && (
          <span className={message.kind === "error" ? "text-sm text-red-700 dark:text-red-400" : "text-sm text-green-700 dark:text-green-400"}>
            {message.text}
          </span>
        )}
      </div>
    </div>
  );
}
