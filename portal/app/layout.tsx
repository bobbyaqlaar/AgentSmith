import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import "./globals.css";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { WorkspaceSwitcher } from "@/components/WorkspaceSwitcher";
import { currentAccess } from "@/lib/currentAccess";
import { WORKSPACES, workspacesFor } from "@/lib/workspaces";
// Imported, not served from public/: portal/Dockerfile copies .next/static,
// where a static import lands, and not public/. `unoptimized` because Next's
// optimizer needs sharp in standalone mode and the portal does not install it —
// the files are already sized for display (.agent-rfc/designs/portal-brand.md).
import agentSmithMark from "@/assets/brand/agentsmith-mark.png";
import aqlaarMark from "@/assets/brand/aqlaar.png";

export const metadata: Metadata = {
  title: "AgentSmith Portal",
  description: "Every app from design to operation: the Dev and Ops workspaces (docs/DESIGN.md › Universal Observability Platform, Federated Observability)",
};

// Applies the stored theme preference to <html> before React hydrates —
// without this, the page would render light (globals.css's default), then
// flash to dark a moment later for anyone who'd previously chosen dark.
// This must be a plain inline script (not a React effect), since the goal
// is to run before first paint.
const NO_FLASH_THEME_SCRIPT = `
(function () {
  try {
    var t = localStorage.getItem("af-theme");
    if (t === "dark" || (!t && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
      document.documentElement.classList.add("dark");
    }
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const workspaces = workspacesFor(currentAccess()).map((area) => ({
    label: WORKSPACES[area].label,
    home: WORKSPACES[area].home,
  }));
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH_THEME_SCRIPT }} />
      </head>
      <body className="min-h-screen flex flex-col">
        <header className="border-b border-black/10 dark:border-white/10 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2 text-lg font-medium hover:opacity-80">
              {/* Decorative: the link's own text names it, so alt="" keeps a
                  screen reader from saying "AgentSmith" twice. Black on a
                  transparent ground; inverted to white on the dark theme. */}
              <Image src={agentSmithMark} alt="" width={28} height={28} unoptimized priority className="dark:invert" />
              AgentSmith
            </Link>
            <WorkspaceSwitcher workspaces={workspaces} />
          </div>
          <ThemeToggle />
        </header>
        <main className="px-6 py-6 max-w-6xl mx-auto w-full flex-1">{children}</main>
        <footer className="border-t border-black/10 dark:border-white/10 px-6 py-3 text-xs text-black/50 dark:text-white/50">
          <div className="max-w-6xl mx-auto flex flex-wrap items-center gap-x-1.5 gap-y-1">
            <span>AgentSmith is made by</span>
            <span className="inline-flex items-center gap-1.5">
              <Image src={aqlaarMark} alt="" width={20} height={18} unoptimized />
              Aqlaar
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
