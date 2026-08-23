import Link from "next/link";
import { notFound } from "next/navigation";
import { listDLQEntries } from "@/lib/dlq";
import { canAccessTenant } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { DlqEntryCard } from "@/components/DlqEntryCard";

export const dynamic = "force-dynamic";

export default async function TenantDlqPage({ params }: { params: { tenantId: string } }) {
  const access = currentAccess();
  if (!canAccessTenant(access, params.tenantId)) notFound();

  const entries = await listDLQEntries(params.tenantId, "pending");

  return (
    <div className="space-y-6">
      <nav className="text-sm text-black/50 dark:text-white/50">
        <Link href="/dlq" className="hover:text-black dark:hover:text-white">Dead-letter queue</Link>
        <span className="mx-1.5">/</span>
        <span className="text-black/80 dark:text-white/80">{params.tenantId}</span>
      </nav>

      <h2 className="text-xl font-medium">
        Pending entries <span className="text-black/40 dark:text-white/40">({params.tenantId})</span>
      </h2>

      {entries.length === 0 ? (
        <p className="text-black/60 dark:text-white/60">No pending DLQ entries for this tenant.</p>
      ) : (
        <div className="space-y-3">
          {entries.map((entry) => (
            <DlqEntryCard key={entry.taskId} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}
