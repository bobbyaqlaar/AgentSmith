"use client";

// An app's machine credentials: issue, rotate, revoke (Administration › Apps).
// Three kinds, one panel: the CI's ingest token (portal phase 1), the workers'
// Ops token and the replay signing key (contract/ops/v1). Each appears once, in
// this panel, right after it is issued. Rotating and revoking break whatever
// holds the old one until it is updated, so both ask first and say so.

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

export type CredentialKind = "ingest" | "ops" | "replay";

const KINDS: Record<
  CredentialKind,
  { path: string; noun: string; holder: string; revocable: boolean; where: (origin: string, secretsUrl: ReactNode) => ReactNode }
> = {
  ingest: {
    path: "ingest-token",
    noun: "token",
    holder: "This app's CI",
    revocable: true,
    where: (origin, secretsUrl) => (
      <>
        Set two secrets in the app&apos;s repository{secretsUrl}: <code>AGENTSMITH_PORTAL_INGEST_TOKEN</code> to this token,
        and <code>AGENTSMITH_PORTAL_URL</code> to <code>{origin || "this portal's address"}</code>.
      </>
    ),
  },
  ops: {
    path: "ops-token",
    noun: "token",
    holder: "This app's workers",
    revocable: true,
    where: (origin) => (
      <>
        Set two variables on the app&apos;s worker deployment: <code>OPS_PORTAL_TOKEN</code> to this token, and{" "}
        <code>OPS_PORTAL_URL</code> to <code>{origin || "this portal's address"}</code>.
      </>
    ),
  },
  replay: {
    path: "replay-key",
    noun: "key",
    holder: "This app's replay webhook",
    revocable: false,
    where: () => (
      <>
        Set <code>REPLAY_WEBHOOK_SECRET</code> on the app&apos;s worker to this key. The portal signs every replay with it.
      </>
    ),
  },
};

const PRIMARY = "px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50";
const SECONDARY =
  "px-3 py-1.5 text-sm rounded-md border border-black/10 dark:border-white/10 hover:bg-black/5 dark:hover:bg-white/5 disabled:opacity-50";
const DANGER = "px-3 py-1.5 text-sm rounded-md bg-red-600 text-white hover:bg-red-700 disabled:opacity-50";

export function IngestTokenPanel({
  appId,
  active,
  repoSecretsUrl,
  kind = "ingest",
}: {
  appId: string;
  active: boolean;
  repoSecretsUrl: string | null;
  kind?: CredentialKind;
}) {
  const spec = KINDS[kind];
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
      const resp = await fetch(`/api/admin/apps/${appId}/${spec.path}`, { method });
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
          <p className="font-medium">Copy this {spec.noun} now — it is not shown again.</p>
          <div className="flex items-center gap-2">
            <code className="font-mono text-xs break-all flex-1">{token}</code>
            <button type="button" className={SECONDARY} onClick={copy} aria-label={`Copy the ${spec.noun}`}>
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <p>
            {spec.where(
              origin,
              repoSecretsUrl ? (
                <>
                  {" "}(<a className="text-blue-700 dark:text-blue-400 hover:underline" href={repoSecretsUrl} rel="noreferrer" target="_blank">Settings › Secrets › Actions</a>)
                </>
              ) : null,
            )}
          </p>
        </div>
      )}

      {!confirming && (
        <div className="flex gap-2">
          <button type="button" className={PRIMARY} disabled={busy} onClick={() => (active ? setConfirming("rotate") : call("POST"))}>
            {busy ? "Working…" : active ? `Rotate ${spec.noun}` : `Issue ${spec.noun}`}
          </button>
          {active && spec.revocable && (
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
              ? `The current ${spec.noun} stops working at once. ${spec.holder} is refused until it holds the new one.`
              : `Every ${spec.noun} of this kind for this app stops working, and none replaces it. ${spec.holder} is refused until a new one is issued.`}
          </p>
          <div className="flex gap-2">
            <button type="button" className={DANGER} disabled={busy} onClick={() => call(confirming === "rotate" ? "POST" : "DELETE")}>
              {busy ? "Working…" : confirming === "rotate" ? `Rotate — the old ${spec.noun} stops working` : "Revoke — it is refused"}
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
