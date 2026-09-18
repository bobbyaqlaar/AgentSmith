import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { WorkspaceSwitcher } from "@/components/WorkspaceSwitcher";
import { currentAccess } from "@/lib/currentAccess";
import { WORKSPACES, workspacesFor } from "@/lib/workspaces";

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
      <body>
        <header className="border-b border-black/10 dark:border-white/10 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/" className="text-lg font-medium hover:opacity-80">
              AgentSmith
            </Link>
            <WorkspaceSwitcher workspaces={workspaces} />
          </div>
          <ThemeToggle />
        </header>
        <main className="px-6 py-6 max-w-6xl mx-auto">{children}</main>
      </body>
    </html>
  );
}
