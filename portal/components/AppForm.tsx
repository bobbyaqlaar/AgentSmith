"use client";

// Register an app, or edit one (Administration › Apps; portal phase 1). The
// server validates (lib/apps.parseAppInput); this form only collects and says
// what the server said.

import { useRouter } from "next/navigation";
import { useState } from "react";

const FIELD =
  "w-full text-sm rounded-md border border-black/10 dark:border-white/10 bg-black/[0.02] dark:bg-white/[0.03] px-2 py-1.5";
const PRIMARY = "px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50";

export interface AppFormValues {
  id: string;
  name: string;
  repoUrl: string;
  repoProvider: "" | "github" | "gitlab";
  defaultBranch: string;
}

export function AppForm({ mode, initial }: { mode: "create" | "update"; initial?: AppFormValues }) {
  const router = useRouter();
  const [values, setValues] = useState<AppFormValues>(
    initial ?? { id: "", name: "", repoUrl: "", repoProvider: "github", defaultBranch: "main" },
  );
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const set = (key: keyof AppFormValues) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setValues((v) => ({ ...v, [key]: e.target.value }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    const body = {
      ...(mode === "create" ? { id: values.id } : {}),
      name: values.name,
      repoUrl: values.repoUrl || null,
      repoProvider: values.repoUrl ? values.repoProvider || null : null,
      defaultBranch: values.defaultBranch || null,
    };
    try {
      const resp = await fetch(mode === "create" ? "/api/admin/apps" : `/api/admin/apps/${initial?.id}`, {
        method: mode === "create" ? "POST" : "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`);
      if (mode === "create") {
        router.push(`/admin/apps/${data.app}`);
      } else {
        setMessage({ kind: "ok", text: "Saved." });
        router.refresh();
      }
    } catch (err) {
      setMessage({ kind: "error", text: err instanceof Error ? err.message : String(err) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 max-w-xl" aria-busy={busy}>
      {mode === "create" && (
        <label className="block text-sm space-y-1">
          <span>App id — lower-case letters, digits and dashes; used in URLs</span>
          <input className={FIELD} value={values.id} onChange={set("id")} required pattern="[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?" />
        </label>
      )}
      <label className="block text-sm space-y-1">
        <span>Name</span>
        <input className={FIELD} value={values.name} onChange={set("name")} required maxLength={200} />
      </label>
      <label className="block text-sm space-y-1">
        <span>Repository URL — optional, but without it commits cannot be linked</span>
        <input className={FIELD} value={values.repoUrl} onChange={set("repoUrl")} type="url" placeholder="https://github.com/org/repo" />
      </label>
      <div className="flex gap-3">
        <label className="block text-sm space-y-1 flex-1">
          <span>Provider</span>
          <select className={FIELD} value={values.repoProvider} onChange={set("repoProvider")} disabled={!values.repoUrl}>
            <option value="github">GitHub</option>
            <option value="gitlab">GitLab (links only — no gate data yet)</option>
          </select>
        </label>
        <label className="block text-sm space-y-1 flex-1">
          <span>Default branch</span>
          <input className={FIELD} value={values.defaultBranch} onChange={set("defaultBranch")} />
        </label>
      </div>
      <div className="flex items-center gap-3">
        <button type="submit" className={PRIMARY} disabled={busy}>
          {busy ? (mode === "create" ? "Registering…" : "Saving…") : mode === "create" ? "Register app" : "Save"}
        </button>
        {message && (
          <p role="status" className={`text-sm ${message.kind === "ok" ? "text-green-700 dark:text-green-400" : "text-red-700 dark:text-red-400"}`}>
            {message.text}
          </p>
        )}
      </div>
    </form>
  );
}
