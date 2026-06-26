"use client";

import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { CostByPeriod } from "@/lib/cost";

export function CostChart({ history }: { history: CostByPeriod[] }) {
  // Recharts renders raw SVG presentational attributes (stroke/fill), which
  // don't respond to Tailwind's `dark:` className variants the way regular
  // CSS does — read the `dark` class on <html> directly instead (same
  // source of truth as components/ui/ThemeToggle.tsx) for the few colors
  // that need to flip between light/dark.
  const [isDark, setIsDark] = useState(false);
  useEffect(() => {
    setIsDark(document.documentElement.classList.contains("dark"));
    const observer = new MutationObserver(() => setIsDark(document.documentElement.classList.contains("dark")));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  if (history.length === 0) {
    return (
      <p className="text-black/60 dark:text-white/60">
        No cost history yet — the budget table is empty for this tenant.
      </p>
    );
  }

  const axisColor = isDark ? "#9aa0aa" : "#6b7280";
  const gridColor = isDark ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)";

  return (
    <div className="bg-black/[0.03] dark:bg-white/[0.03] rounded-lg p-4" style={{ width: "100%", height: 280 }}>
      <ResponsiveContainer>
        <LineChart data={history}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
          <XAxis dataKey="period" stroke={axisColor} tick={{ fontSize: 12, fill: axisColor }} />
          <YAxis stroke={axisColor} tick={{ fontSize: 12, fill: axisColor }} tickFormatter={(v) => `$${v}`} />
          <Tooltip
            formatter={(v: number) => `$${v.toFixed(2)}`}
            contentStyle={{
              background: isDark ? "#1a1d24" : "#ffffff",
              border: `1px solid ${isDark ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.1)"}`,
              borderRadius: 8,
              color: isDark ? "#e6e6e6" : "#16181d",
            }}
          />
          <Line type="monotone" dataKey="spentUsd" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
