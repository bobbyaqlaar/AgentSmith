import { headers } from "next/headers";
import { listAuditEvents } from "@/lib/auditLog";
import { ROLE_HEADER, TENANT_SCOPE_HEADER, canAdmin, getAccessFromHeaderValues } from "@/lib/authz";
import { Badge } from "@/components/ui/Badge";

export const dynamic = "force-dynamic";

export default async function AuditLogPage() {
  const h = headers();
  const access = getAccessFromHeaderValues(h.get(ROLE_HEADER), h.get(TENANT_SCOPE_HEADER));

  if (!canAdmin(access)) {
    return (
      <div className="space-y-2">
        <h2 className="text-xl font-medium">Audit log</h2>
        <p className="text-black/60 dark:text-white/60">
          The admin role is required to view the audit log.
        </p>
      </div>
    );
  }

  const events = await listAuditEvents({ limit: 200 });

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-medium">Audit log</h2>
        <p className="text-sm text-black/60 dark:text-white/60 mt-1">
          Immutable, HMAC-signed. <code className="text-black/80 dark:text-white/80">verified: false</code> below
          means a row's signature no longer matches its content — tampering, or a key rotation without re-signing.
        </p>
      </div>

      {events.length === 0 ? (
        <p className="text-black/60 dark:text-white/60">No events recorded yet.</p>
      ) : (
        <div className="border border-black/10 dark:border-white/10 rounded-lg overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-black/[0.03] dark:bg-white/[0.05] text-black/60 dark:text-white/60">
              <tr>
                <th className="py-2.5 px-4 font-medium">Time</th>
                <th className="py-2.5 px-4 font-medium">Event type</th>
                <th className="py-2.5 px-4 font-medium">Actor</th>
                <th className="py-2.5 px-4 font-medium">Tenant</th>
                <th className="py-2.5 px-4 font-medium">Verified</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.eventId} className="border-t border-black/10 dark:border-white/10">
                  <td className="py-2.5 px-4 text-black/70 dark:text-white/70">
                    {new Date(e.timestamp).toLocaleString()}
                  </td>
                  <td className="py-2.5 px-4 font-mono text-xs">{e.eventType}</td>
                  <td className="py-2.5 px-4">{e.actorId}</td>
                  <td className="py-2.5 px-4 text-black/70 dark:text-white/70">{e.tenantId ?? "—"}</td>
                  <td className="py-2.5 px-4">
                    {e.verified ? <Badge tone="success">verified</Badge> : <Badge tone="danger">tampered</Badge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
