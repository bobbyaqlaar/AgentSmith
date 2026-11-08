"use client";

import { useRouter } from "next/navigation";

export function IncidentClose({ tenantId, incidentId }: { tenantId: string; incidentId: number }) {
  const router = useRouter();
  async function close() {
    const resp = await fetch("/api/incidents", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ tenantId, closeId: incidentId }),
    });
    if (resp.ok) router.refresh();
  }
  return (
    <button type="button" onClick={close} className="text-sm text-blue-700 dark:text-blue-400 hover:underline">
      Close
    </button>
  );
}
