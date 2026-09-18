"use client";

// The header's area switcher. A client component only because it needs the
// current path to mark the area you are in; which areas appear is decided on
// the server (lib/workspaces.workspacesFor) and passed in.

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface WorkspaceLink {
  label: string;
  home: string;
}

export function WorkspaceSwitcher({ workspaces }: { workspaces: WorkspaceLink[] }) {
  const pathname = usePathname() ?? "/";
  // One area: nothing to switch between, so no switcher at all.
  if (workspaces.length < 2) return null;
  return (
    <nav aria-label="Workspace" className="flex items-center gap-1 text-sm">
      {workspaces.map((w) => {
        const current = pathname === w.home || pathname.startsWith(`${w.home}/`);
        return (
          <Link
            key={w.home}
            href={w.home}
            aria-current={current ? "page" : undefined}
            className={`px-3 py-1 rounded-md ${
              current
                ? "bg-black/[0.06] dark:bg-white/[0.1] text-black dark:text-white"
                : "text-black/60 dark:text-white/60 hover:text-black dark:hover:text-white"
            }`}
          >
            {w.label}
          </Link>
        );
      })}
    </nav>
  );
}
