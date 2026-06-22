"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { CostByPeriod } from "@/lib/cost";

export function CostChart({ history }: { history: CostByPeriod[] }) {
  if (history.length === 0) {
    return <p className="text-white/60">No cost history yet — the budget table is empty for this tenant.</p>;
  }

  return (
    <div style={{ width: "100%", height: 260 }}>
      <ResponsiveContainer>
        <LineChart data={history}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="period" stroke="#999" />
          <YAxis stroke="#999" tickFormatter={(v) => `$${v}`} />
          <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} contentStyle={{ background: "#1a1d24", border: "1px solid #333" }} />
          <Line type="monotone" dataKey="spentUsd" stroke="#60a5fa" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
