// Small pieces every Dev page shares (portal phase 1, S5).

import Link from "next/link";

import { Badge, toneForVerdict, verdictLabel } from "@/components/ui/Badge";
import { Timestamp } from "@/components/ui/Timestamp";
import type { DevDesign } from "@/lib/devIngest";
import { freshness, STALE_AFTER_HOURS } from "@/lib/devView";

export function VerdictBadge({ verdict }: { verdict: string }) {
  return <Badge tone={toneForVerdict(verdict)}>{verdictLabel(verdict)}</Badge>;
}

/** "Last received …", in three distinct states: never, fresh, stale. */
export function Freshness({ lastReceived, provider }: { lastReceived: string | null; provider: string | null }) {
  if (provider === "gitlab") {
    return (
      <span className="text-black/50 dark:text-white/50">
        Gate data is not available for GitLab repositories yet
      </span>
    );
  }
  const state = freshness(lastReceived);
  if (state === "never" || !lastReceived) {
    return (
      <span className="text-black/50 dark:text-white/50">
        No data received — CI has not sent a gate result
      </span>
    );
  }
  return (
    <span className={state === "stale" ? "text-amber-700 dark:text-amber-400" : "text-black/60 dark:text-white/60"}>
      Last received <Timestamp value={lastReceived} />
      {state === "stale" && ` — older than ${STALE_AFTER_HOURS} hours`}
    </span>
  );
}

/** applies · n/a · gap · deviation counts for a design's pillars. */
export function PillarSummary({ design }: { design: DevDesign | null }) {
  if (!design || !design.resolved) return <span className="text-black/40 dark:text-white/40">—</span>;
  if (Object.keys(design.pillars).length === 0) {
    return <span className="text-black/40 dark:text-white/40" title="this design has no pillar answers">no answers</span>;
  }
  const counts = { applies: 0, "n/a": 0, gap: 0, deviation: 0, unrecognised: 0 };
  for (const kind of Object.values(design.pillars)) counts[kind] += 1;
  return (
    <span className="font-mono text-xs text-black/60 dark:text-white/60 whitespace-nowrap" title="applies · n/a · gap · deviation">
      {counts.applies} · {counts["n/a"]} · {counts.gap} · {counts.deviation}
      {counts.unrecognised > 0 && <span className="text-amber-700 dark:text-amber-400"> · {counts.unrecognised} unrecognised</span>}
    </span>
  );
}

export function ShortSha({ sha, href }: { sha: string; href: string | null }) {
  const short = <code className="font-mono text-xs">{sha.slice(0, 10)}</code>;
  return href ? (
    <a className="text-blue-700 dark:text-blue-400 hover:underline" href={href} rel="noreferrer" target="_blank">
      {short}
    </a>
  ) : (
    short
  );
}

export function Crumbs({ items }: { items: { href?: string; text: string }[] }) {
  return (
    <div className="text-sm text-black/60 dark:text-white/60 mb-2">
      {items.map((item, i) => (
        <span key={i}>
          {i > 0 && <span className="mx-1.5">/</span>}
          {item.href ? (
            <Link href={item.href} className="hover:text-black dark:hover:text-white">{item.text}</Link>
          ) : (
            <span className="text-black/80 dark:text-white/80">{item.text}</span>
          )}
        </span>
      ))}
    </div>
  );
}
