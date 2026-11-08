"use client";

// Sign one obligation. The server decides who may; this collects where the
// evidence is and says what the server said.

import { useRouter } from "next/navigation";
import { useState } from "react";

const FIELD =
  "w-full text-sm rounded-md border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.04] px-2 py-1";

export function AttestForm({ app, obligation }: { app: string; obligation: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [evidence, setEvidence] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <button type="button" className="text-sm text-blue-700 dark:text-blue-400 hover:underline" onClick={() => setOpen(true)}>
        Sign
      </button>
    );
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const resp = await fetch(`/api/compliance/${encodeURIComponent(app)}/attest`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ obligation, evidence, note }),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`);
      setOpen(false);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2 min-w-56">
      <label className="block text-xs text-black/60 dark:text-white/60">
        Where the evidence is
        <input className={FIELD} required value={evidence} onChange={(e) => setEvidence(e.target.value)} />
      </label>
      <label className="block text-xs text-black/60 dark:text-white/60">
        Note (optional)
        <input className={FIELD} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      {error && <p className="text-xs text-red-700 dark:text-red-400" role="alert">{error}</p>}
      <div className="flex gap-3 text-sm">
        <button type="submit" disabled={busy} className="px-2 py-1 rounded-md bg-blue-600 text-white disabled:opacity-50">
          {busy ? "Signing…" : "Sign as true"}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-black/60 dark:text-white/60">Cancel</button>
      </div>
    </form>
  );
}
