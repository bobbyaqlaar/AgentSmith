import Link from "next/link";
import { notFound } from "next/navigation";
import { listDLQEntries } from "@/lib/dlq";
import { canAccessTenant } from "@/lib/authz";
import { currentAccess } from "@/lib/currentAccess";
import { DlqEntryCard } from "@/components/DlqEntryCard";
import { isTruncated } from "@/lib/cappedList";

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
        {entries && isTruncated(entries) && (
          <span className="ml-2 text-sm font-normal text-black/50 dark:text-white/50">
            showing the {entries.limit} most recent of {entries.total}
          </span>
        )}
      </h2>

      {entries === null ? (
        // Not the same sentence as "none pending". This page used to render the
        // reassuring one from a database no worker has ever connected to, while
        // the index page one click earlier said "Not wired" correctly.
        <p className="text-amber-700 dark:text-amber-400">
          Not wired — no worker has constructed a <code>DeadLetterQueue</code> against this
          database yet, so this list is unavailable rather than empty.
        </p>
      ) : entries.total === 0 ? (
        <p className="text-black/60 dark:text-white/60">No pending DLQ entries for this tenant.</p>
      ) : (
        <div className="space-y-3">
          {entries.entries.map((entry) => (
            <DlqEntryCard key={entry.taskId} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}
