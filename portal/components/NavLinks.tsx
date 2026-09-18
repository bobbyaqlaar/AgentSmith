"use client";

// A row of links that marks the one you are on. Client-side only for the
// current path; which links appear is decided by the server component that
// renders this.

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface NavLink {
  href: string;
  text: string;
  /** Mark this link current only on an exact match — for a section's home, which prefixes every other link. */
  exact?: boolean;
  /** Further path prefixes this link stands for (the Apps link, for every page under /dev/apps). */
  covers?: string[];
}

export function NavLinks({ label, links, variant }: { label: string; links: NavLink[]; variant: "area" | "tabs" }) {
  const pathname = usePathname() ?? "/";
  const under = (prefix: string) => pathname === prefix || pathname.startsWith(`${prefix}/`);
  const isCurrent = (l: NavLink) =>
    pathname === l.href || (!l.exact && under(l.href)) || (l.covers ?? []).some(under);
  const base =
    variant === "tabs"
      ? "flex gap-4 text-sm border-b border-black/10 dark:border-white/10"
      : "flex items-center gap-4 text-sm mb-6";
  return (
    <nav aria-label={label} className={base}>
      {links.map((l) => {
        const current = isCurrent(l);
        const tone = current
          ? "text-black dark:text-white"
          : "text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white";
        const underline = variant === "tabs" ? (current ? "pb-2 border-b-2 border-current -mb-px" : "pb-2") : "";
        return (
          <Link key={l.href} href={l.href} aria-current={current ? "page" : undefined} className={`${tone} ${underline}`}>
            {l.text}
          </Link>
        );
      })}
    </nav>
  );
}
