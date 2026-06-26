import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export const metadata: Metadata = {
  title: "AgentSmith — Ops Portal",
  description: "Cross-tenant operations dashboard (SPECS.md §15, §26)",
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
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH_THEME_SCRIPT }} />
      </head>
      <body>
        <header className="border-b border-black/10 dark:border-white/10 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/" className="text-lg font-medium hover:opacity-80">
              AgentSmith <span className="text-black/40 dark:text-white/40">Ops Portal</span>
            </Link>
            <nav className="flex items-center gap-4 text-sm text-black/60 dark:text-white/60">
              <Link href="/" className="hover:text-black dark:hover:text-white">Tenants</Link>
              <Link href="/dlq" className="hover:text-black dark:hover:text-white">Dead-letter queue</Link>
              <Link href="/audit" className="hover:text-black dark:hover:text-white">Audit log</Link>
            </nav>
          </div>
          <ThemeToggle />
        </header>
        <main className="px-6 py-6 max-w-6xl mx-auto">{children}</main>
      </body>
    </html>
  );
}
