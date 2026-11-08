"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const FIELD = "rounded-md border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.04] px-2 py-1 text-sm";

export function IncidentForm({ apps }: { apps: string[] }) {
  const router = useRouter();
  const [form, setForm] = useState({ tenantId: apps[0] ?? "", title: "", severity: "medium", details: "" });
  const [error, setError] = useState<string | null>(null);
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const resp = await fetch("/api/incidents", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(form) });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) return setError(data.error ?? `HTTP ${resp.status}`);
    setForm((f) => ({ ...f, title: "", details: "" }));
    router.refresh();
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <select aria-label="App" className={FIELD} value={form.tenantId} onChange={set("tenantId")}>{apps.map((a) => <option key={a}>{a}</option>)}</select>
      <input aria-label="Title" required placeholder="What happened" className={FIELD} value={form.title} onChange={set("title")} />
      <select aria-label="Severity" className={FIELD} value={form.severity} onChange={set("severity")}>{["low", "medium", "high", "critical"].map((s) => <option key={s}>{s}</option>)}</select>
      <input aria-label="Details" placeholder="Details" className={FIELD} value={form.details} onChange={set("details")} />
      <button type="submit" className="px-3 py-1 text-sm rounded-md bg-blue-600 text-white">Open incident</button>
      {error && <span role="alert" className="text-sm text-red-700 dark:text-red-400">{error}</span>}
    </form>
  );
}
