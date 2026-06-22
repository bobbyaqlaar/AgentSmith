import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgenticFramework — Ops Portal",
  description: "Cross-tenant operations dashboard (SPECS.md §15, §26)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-white/10 px-6 py-4">
          <h1 className="text-lg font-semibold">AgenticFramework Ops Portal</h1>
        </header>
        <main className="px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
