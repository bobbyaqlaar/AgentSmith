"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { submitOnce } from "@/lib/submitOnce";

// An incident cannot be reopened, so closing asks first; it sends once and says when it
// did not work (the 4.1.0 review's second pass, P2-R21).
export function IncidentClose({ tenantId, incidentId }: { tenantId: string; incidentId: number }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef({ busy: false });

  async function close() {
    setError(null);
    setBusy(true);
    const result = await submitOnce(
      inFlight.current,
      async () => {
        const resp = await fetch("/api/incidents", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ tenantId, closeId: incidentId }),
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`);
      },
      () => window.confirm(`Close incident ${incidentId}? A closed incident cannot be reopened.`),
    );
    setBusy(false);
    if (result.ok) router.refresh();
    else if (result.error) setError(`Not closed: ${result.error}`);
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button type="button" onClick={close} disabled={busy} className="text-sm text-blue-700 dark:text-blue-400 hover:underline disabled:opacity-50">
        {busy ? "Closing…" : "Close"}
      </button>
      {error && <span role="alert" className="text-sm text-red-700 dark:text-red-400">{error}</span>}
    </span>
  );
}
