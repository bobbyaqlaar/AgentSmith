"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { submitOnce } from "@/lib/submitOnce";

const FIELD = "rounded-md border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.04] px-2 py-1 text-sm";

export function IncidentForm({ apps }: { apps: string[] }) {
  const router = useRouter();
  const [form, setForm] = useState({ tenantId: apps[0] ?? "", title: "", severity: "medium", details: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef({ busy: false });
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setForm((f) => ({ ...f, [key]: e.target.value }));

  // One click, one incident, and an answer either way (the 4.1.0 review's second pass, P2-R21).
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const result = await submitOnce(inFlight.current, async () => {
      const resp = await fetch("/api/incidents", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(form) });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`);
    });
    setBusy(false);
    if (result.ok) {
      setForm((f) => ({ ...f, title: "", details: "" }));
      router.refresh();
    } else if (result.error) {
      setError(`Not opened: ${result.error}`);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <select aria-label="App" className={FIELD} value={form.tenantId} onChange={set("tenantId")}>{apps.map((a) => <option key={a}>{a}</option>)}</select>
      <input aria-label="Title" required placeholder="What happened" className={FIELD} value={form.title} onChange={set("title")} />
      <select aria-label="Severity" className={FIELD} value={form.severity} onChange={set("severity")}>{["low", "medium", "high", "critical"].map((s) => <option key={s}>{s}</option>)}</select>
      <input aria-label="Details" placeholder="Details" className={FIELD} value={form.details} onChange={set("details")} />
      <button type="submit" disabled={busy} className="px-3 py-1 text-sm rounded-md bg-blue-600 text-white disabled:opacity-50">{busy ? "Opening…" : "Open incident"}</button>
      {error && <span role="alert" className="text-sm text-red-700 dark:text-red-400">{error}</span>}
    </form>
  );
}
