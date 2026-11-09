import Link from "next/link";
import { notFound } from "next/navigation";
import { getTenant } from "@/lib/tenants";
import { getTenantCost } from "@/lib/cost";
import { getUnresolvedIssues } from "@/lib/issues";
import { tenantTraceUrl, checkPhoenixHealth, getRecentTraceStats } from "@/lib/phoenix";
import { getSuggestedPromotions } from "@/lib/promotions";
import { CostChart } from "@/components/CostChart";
import { StopControl } from "@/components/StopControl";
import { can } from "@/lib/authz";
import { lastStopAction } from "@/lib/hitl";
import { listRecentRuns } from "@/lib/runStatus";
import { isSafeHttpUrl } from "@/lib/safeUrl";
import { isTruncated } from "@/lib/cappedList";
import { currentAccess } from "@/lib/currentAccess";
import { Badge, toneForLevel, toneForRunStatus } from "@/components/ui/Badge";
import { MetricCard } from "@/components/ui/Card";
import { Timestamp } from "@/components/ui/Timestamp";

export const dynamic = "force-dynamic";

export default async function TenantDetailPage(props: { params: Promise<{ id: string }> }) {
  const params = await props.params;
  const access = await currentAccess();
  // Treat out-of-scope tenants identically to nonexistent ones — a 403 page
  // would itself leak "this tenant id exists" to a viewer who shouldn't see it.
  if (!can(access, "ops.read", params.id)) notFound();

  const tenant = await getTenant(params.id);
  if (!tenant) notFound();
  const lastStop = await lastStopAction(tenant.tenantId);
  const recentRuns = await listRecentRuns(tenant.tenantId);

  const [cost, issues, phoenixUp, traceStats, suggestedPromotions] = await Promise.all([
    getTenantCost(tenant.tenantId),
    getUnresolvedIssues(tenant.tenantId),
    tenant.phoenixBaseUrl ? checkPhoenixHealth(tenant.phoenixBaseUrl) : Promise.resolve(null),
    tenant.phoenixBaseUrl ? getRecentTraceStats(tenant.phoenixBaseUrl, { sinceHours: 24 }) : Promise.resolve(null),
    // null, like the two Phoenix reads above it — NOT []. An empty list renders
    // "No shadow-eval failures in the last 24h", which is a health claim, and
    // a tenant with no Phoenix endpoint registered has had nothing looked at.
    tenant.phoenixBaseUrl ? getSuggestedPromotions(tenant.phoenixBaseUrl, { sinceHours: 24 }) : Promise.resolve(null),
  ]);

  return (
    <div className="space-y-8">
      <nav className="text-sm text-black/50 dark:text-white/50">
        <Link href="/ops" className="hover:text-black dark:hover:text-white">Apps</Link>
        <span className="mx-1.5">/</span>
        <span className="text-black/80 dark:text-white/80">{tenant.name}</span>
        {can(access, "compliance.read", tenant.tenantId) && (
          <Link href={`/ops/apps/${encodeURIComponent(tenant.tenantId)}/compliance`} className="ml-4 text-blue-700 dark:text-blue-400 hover:underline">Compliance checklist</Link>
        )}
        {can(access, "compliance.read", tenant.tenantId) && (
          <Link href={`/ops/apps/${encodeURIComponent(tenant.tenantId)}/decisions`} className="ml-4 text-blue-700 dark:text-blue-400 hover:underline">Decision trail</Link>
        )}
      </nav>

      {lastStop?.action === "stop" && (
        <p role="status" className="text-sm"><Badge tone="danger">Stopped</Badge> by {lastStop.actor}: {lastStop.reason}</p>
      )}
      {can(access, "ops.stop", tenant.tenantId) && <StopControl tenantId={tenant.tenantId} />}

      <div>
        <h2 className="text-xl font-medium">
          {tenant.name} <span className="text-black/40 dark:text-white/40">({tenant.tenantId})</span>
        </h2>
        <p className="text-black/60 dark:text-white/60 text-sm mt-1">Isolation: {tenant.isolation}</p>
        {tenant.phoenixBaseUrl ? (
          <p className="text-sm mt-1">
            Phoenix:{" "}
            {/* Rows written before POST /api/tenants validated this can still
                hold any scheme, and React renders `javascript:` in an href
                without complaint. Shown as text when it is not an http(s) URL. */}
            {isSafeHttpUrl(tenant.phoenixBaseUrl) ? (
              <a className="text-blue-700 dark:text-blue-400 hover:underline" href={tenantTraceUrl(tenant.phoenixBaseUrl, { environment: "production" })}>
                {tenant.phoenixBaseUrl}
              </a>
            ) : (
              <span className="font-mono text-black/60 dark:text-white/60">{tenant.phoenixBaseUrl}</span>
            )}{" "}
            {phoenixUp === false && <Badge tone="danger">unreachable</Badge>}
            {phoenixUp === true && <Badge tone="success">reachable</Badge>}
          </p>
        ) : (
          <p className="text-sm text-black/40 dark:text-white/40 mt-1">No Phoenix endpoint registered for this app.</p>
        )}
        {traceStats !== null && (
          <p className="text-sm mt-1 text-black/60 dark:text-white/60">
            Last 24h: {traceStats.traceCount} trace(s) in project{" "}
            <code className="text-black/80 dark:text-white/80">{traceStats.projectName}</code>
            {traceStats.errorRate !== null && (
              <>
                {" "}— error rate{" "}
                <Badge tone={traceStats.errorRate > 0.05 ? "danger" : "success"}>
                  {(traceStats.errorRate * 100).toFixed(1)}%
                </Badge>
              </>
            )}
            {/* The query reads the FIRST project the instance reports. With one
                project that is the whole picture; with several it is a slice,
                and the figure was previously presented as the tenant's with no
                indication of which project produced it. */}
            {traceStats.projectCount > 1 && (
              <span className="ml-2 text-amber-700 dark:text-amber-400">
                — this Phoenix has {traceStats.projectCount} projects; only the first is counted
              </span>
            )}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard
          label="Spend this month"
          value={cost.wired ? `$${cost.spentUsd.toFixed(2)}` : "—"}
        />
        <MetricCard
          label="Budget cap"
          value={cost.cap !== null ? `$${cost.cap.toFixed(2)}` : "—"}
        />
        <MetricCard
          label="Unresolved issues"
          // issues.total, not issues.entries.length — the list below is capped
          // and this card used to report the cap as the count, disagreeing with
          // the dashboard's SQL COUNT for the same tenant above 200.
          value={issues.total}
          tone={issues.total > 0 ? "danger" : "success"}
        />
      </div>

      <section>
        <h3 className="text-lg font-medium mb-1">Recent runs</h3>
        <p className="text-sm text-black/60 dark:text-white/60 mb-3">
          Each links to the commit it was built from, and through it to the design and approvals.
        </p>
        {recentRuns.length === 0 ? (
          <p className="text-black/60 dark:text-white/60">No runs reported yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-black/60 dark:text-white/60">
                  <th className="py-1 pr-4 font-medium">Status</th>
                  <th className="py-1 pr-4 font-medium">Started</th>
                  <th className="py-1 pr-4 font-medium">Workflow</th>
                  <th className="py-1 pr-4 font-medium">Commit</th>
                </tr>
              </thead>
              <tbody>
                {recentRuns.map((run) => (
                  <tr key={run.runId} className="border-t border-black/10 dark:border-white/10">
                    <td className="py-1 pr-4"><Badge tone={toneForRunStatus(run.status)}>{run.status}</Badge></td>
                    <td className="py-1 pr-4"><Timestamp value={run.startedAt} /></td>
                    <td className="py-1 pr-4 font-mono text-xs break-all">{run.workflowId ?? "—"}</td>
                    <td className="py-1 pr-4">
                      {run.appCommit ? (
                        <Link
                          className="font-mono text-xs text-blue-700 dark:text-blue-400 hover:underline"
                          href={`/dev/apps/${tenant.tenantId}/commits/${run.appCommit}`}
                        >
                          {run.appCommit.slice(0, 10)}
                        </Link>
                      ) : (
                        <span className="text-black/50 dark:text-white/50">not reported</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h3 className="text-lg font-medium mb-3">
          {cost.wired ? `Cost — last ${cost.history.length} month(s)` : "Cost"}
        </h3>
        {cost.wired ? (
          <CostChart history={cost.history} />
        ) : (
          <p className="text-amber-700 dark:text-amber-400 text-sm">
            Not wired — no gateway has recorded a call against this database yet. This is
            unmeasured, not zero.
          </p>
        )}
      </section>

      <section>
        <h3 className="text-lg font-medium mb-3">
          Unresolved MAJOR / CRITICAL issues
          {isTruncated(issues) && (
            <span className="ml-2 text-sm font-normal text-black/50 dark:text-white/50">
              showing the {issues.limit} most recent of {issues.total}
            </span>
          )}
        </h3>
        {issues.total === 0 ? (
          <p className="text-black/60 dark:text-white/60">None — clean.</p>
        ) : (
          <ul className="space-y-2">
            {issues.entries.map((i) => (
              <li key={i.entryId} className="border border-black/10 dark:border-white/10 rounded-lg p-3 text-sm">
                <Badge tone={toneForLevel(i.level)}>{i.level}</Badge>
                <span className="ml-2">{i.event}</span>{" "}
                <span className="text-black/40 dark:text-white/40">
                  — <Timestamp value={i.timestamp} />
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="text-lg font-medium mb-3">Suggested promotions (shadow eval)</h3>
        {suggestedPromotions === null ? (
          <p className="text-black/60 dark:text-white/60">
            {tenant.phoenixBaseUrl
              ? "Could not read shadow-eval results from Phoenix — this list is unavailable, not empty."
              : "No Phoenix endpoint registered for this app, so nothing has been read — this list is unavailable, not empty."}
          </p>
        ) : suggestedPromotions.failures.length === 0 ? (
          <p className="text-black/60 dark:text-white/60">
            {/* The claim is bounded by what was read. It used to say "in the
                last 24h" for a single page of a cursor-paginated endpoint. */}
            No shadow-eval failures among the {suggestedPromotions.spansScanned} span(s) read
            from the last 24h
            {suggestedPromotions.truncated
              ? " — and this window holds more than one page, so this is a sample, not the window."
              : " — nothing suggested."}
          </p>
        ) : (
          <ul className="space-y-2">
            {suggestedPromotions.truncated && (
              <li className="text-sm text-amber-700 dark:text-amber-400">
                More spans exist in this window than were read — these failures come from the
                most recent {suggestedPromotions.spansScanned}.
              </li>
            )}
            {suggestedPromotions.failures.map((p) => (
              <li key={p.spanId} className="border border-black/10 dark:border-white/10 rounded-lg p-3 text-sm space-y-1">
                <div>
                  <Badge tone="danger">score {p.score.toFixed(2)}</Badge>
                  <span className="ml-2 text-black/40 dark:text-white/40 font-mono text-xs">{p.spanId}</span>
                </div>
                {p.inputValue && <p className="text-black/70 dark:text-white/70">Input: {p.inputValue}</p>}
                {p.outputValue && <p className="text-black/70 dark:text-white/70">Output: {p.outputValue}</p>}
                {p.explanation && <p className="text-black/50 dark:text-white/50 italic">{p.explanation}</p>}
                <p className="text-black/40 dark:text-white/40 text-xs">
                  Review in Phoenix, then run <code>agentsmith promote</code> to add to the golden dataset — never auto-promoted.
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
