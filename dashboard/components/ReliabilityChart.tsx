"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { signalLabel } from "@/lib/format";
import type { Stats } from "@/lib/types";

export function ReliabilityChart({ stats }: { stats: Stats }) {
  const data = Object.entries(stats.per_signal)
    .map(([name, agg]) => ({
      name: signalLabel(name),
      winRate: agg.win_rate ?? 0,
      trades: agg.trades,
    }))
    .sort((a, b) => b.winRate - a.winRate);

  if (data.length === 0) {
    return (
      <div className="text-muted text-sm h-[260px] grid place-items-center">
        No closed trades yet — per-signal reliability appears once positions reach their holding
        period.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 30 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#262a36" vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fill: "#8b90a0", fontSize: 11 }}
          angle={-20}
          textAnchor="end"
          interval={0}
          height={50}
        />
        <YAxis tick={{ fill: "#8b90a0", fontSize: 11 }} domain={[0, 100]} unit="%" />
        <Tooltip
          cursor={{ fill: "#ffffff08" }}
          contentStyle={{
            background: "#1b1e27",
            border: "1px solid #262a36",
            borderRadius: 10,
            color: "#e6e8ee",
          }}
          formatter={(value, _name, item) => {
            const trades = (item?.payload as { trades?: number } | undefined)?.trades ?? 0;
            return [`${Number(value)}% win · ${trades} trades`, "Win rate"];
          }}
        />
        <Bar dataKey="winRate" radius={[6, 6, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.winRate >= 50 ? "#2ecc71" : "#ff5470"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
