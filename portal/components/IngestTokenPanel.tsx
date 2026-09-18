"use client";

// An app's ingest token: issue, rotate, revoke (Administration › Apps; portal
// phase 1). The token appears once, in this panel, right after it is issued;
// the portal keeps only its hash. Rotating and revoking break the app's CI
// until its secret is updated, so both ask first and say so.

import { useRouter } from "next/navigation";
import { useState } from "react";

const PRIMARY = "px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50";
const SECONDARY =
  "px-3 py-1.5 text-sm rounded-md border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-50";
const DANGER = "px-3 py-1.5 text-sm rounded-md bg-red-600 text-white hover:bg-red-700 disabled:opacity-50";

export function IngestTokenPanel({ appId, active, repoSecretsUrl }: { appId: string; active: boolean; repoSecretsUrl: string | null }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState<"rotate" | "revoke" | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function call(method: "POST" | "DELETE") {
    setBusy(true);
    setError(null);
    try {
      const resp = await fetch(`/api/admin/apps/${appId}/ingest-token`, { method });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`);
      setToken(method === "POST" ? data.token : null);
      setConfirming(null);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function copy() {
    if (!token) return;
    await navigator.clipboard.writeText(token);
    setCopied(true);
  }

  const origin = typeof window === "undefined" ? "" : window.location.origin;

  return (
    <div className="space-y-3 text-sm">
      {token && (
        <div className="border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-950/30 rounded-lg p-3 space-y-2" role="status">
          <p className="font-medium">Copy this token now — it is not shown again.</p>
          <div className="flex items-center gap-2">
            <code className="font-mono text-xs break-all flex-1">{token}</code>
            <button type="button" className={SECONDARY} onClick={copy} aria-label="Copy the ingest token">
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <p>
            Set two secrets in the app&apos;s repository
            {repoSecretsUrl && (
              <>
                {" "}(<a className="text-blue-700 dark:text-blue-400 hover:underline" href={repoSecretsUrl} rel="noreferrer" target="_blank">Settings › Secrets › Actions</a>)
              </>
            )}
            : <code>AGENTSMITH_PORTAL_INGEST_TOKEN</code> to this token, and <code>AGENTSMITH_PORTAL_URL</code> to{" "}
            <code>{origin || "this portal's address"}</code>.
          </p>
        </div>
      )}

      {!confirming && (
        <div className="flex gap-2">
          <button type="button" className={PRIMARY} disabled={busy} onClick={() => (active ? setConfirming("rotate") : call("POST"))}>
            {busy ? "Working…" : active ? "Rotate token" : "Issue token"}
          </button>
          {active && (
            <button type="button" className={SECONDARY} disabled={busy} onClick={() => setConfirming("revoke")}>
              Revoke
            </button>
          )}
        </div>
      )}

      {confirming && (
        <div className="border border-black/10 dark:border-white/10 rounded-lg p-3 space-y-2">
          <p>
            {confirming === "rotate"
              ? "The current token stops working at once. This app's CI is refused until its secret holds the new one."
              : "Every token for this app stops working, and none replaces it. This app's CI is refused until a new token is issued."}
          </p>
          <div className="flex gap-2">
            <button type="button" className={DANGER} disabled={busy} onClick={() => call(confirming === "rotate" ? "POST" : "DELETE")}>
              {busy ? "Working…" : confirming === "rotate" ? "Rotate — the old token stops working" : "Revoke — CI is refused"}
            </button>
            <button type="button" className={SECONDARY} disabled={busy} onClick={() => setConfirming(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {error && <p role="alert" className="text-red-700 dark:text-red-400">{error}</p>}
    </div>
  );
}
