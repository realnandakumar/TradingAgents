"use client";

import { inr } from "@/lib/format";
import type { GapScreenerPick } from "@/lib/gap-screener-server";

function pct(v: number, digits = 1) {
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}%`;
}

export function GapScreenerBlotter({
  picks,
  openTickers = [],
  maxFillPct = 50,
}: {
  picks: GapScreenerPick[];
  openTickers?: string[];
  maxFillPct?: number;
}) {
  const openSet = new Set(openTickers);
  const downs = picks.filter((p) => p.direction === "DOWN");
  const ups = picks.filter((p) => p.direction === "UP");

  const statusFor = (p: GapScreenerPick) => {
    if (openSet.has(p.symbol)) return { label: "In book", tone: "text-accent" };
    if (p.direction === "UP") return { label: "Short only", tone: "text-muted" };
    if (p.fill_pct > maxFillPct) return { label: "Past fill band", tone: "text-bear" };
    return { label: "New", tone: "text-bull" };
  };

  const renderTable = (rows: GapScreenerPick[], title: string) => (
    <section className="card overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border/60 flex items-center gap-2 text-xs">
        <span className="font-semibold uppercase tracking-wide">{title}</span>
        <span className="text-muted">({rows.length})</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="text-muted uppercase border-b border-border">
              <th className="text-left py-2 px-3">#</th>
              <th className="text-left py-2 px-3">Symbol</th>
              <th className="text-left py-2 px-3">Name</th>
              <th className="text-left py-2 px-3">Status</th>
              <th className="text-right py-2 px-3">Gap%</th>
              <th className="text-right py-2 px-3">Age</th>
              <th className="text-right py-2 px-3">Fill%</th>
              <th className="text-right py-2 px-3">RSI</th>
              <th className="text-right py-2 px-3">Close</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const status = statusFor(p);
              return (
                <tr
                  key={`${p.symbol}-${p.rank}`}
                  className={`border-b border-border/40 last:border-0 ${
                    openSet.has(p.symbol) ? "bg-accent/5" : ""
                  }`}
                >
                  <td className="py-2 px-3 text-muted">{p.rank}</td>
                  <td className="py-2 px-3 font-medium">{p.ticker}</td>
                  <td className="py-2 px-3 text-muted max-w-[160px] truncate">{p.stock_name}</td>
                  <td className={`py-2 px-3 ${status.tone}`}>{status.label}</td>
                  <td
                    className={`py-2 px-3 text-right tabular-nums ${
                      p.direction === "DOWN" ? "text-bull" : "text-bear"
                    }`}
                  >
                    {pct(p.gap_pct)}
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums">{p.gap_age}d</td>
                  <td
                    className={`py-2 px-3 text-right tabular-nums ${
                      p.fill_pct > maxFillPct ? "text-bear" : ""
                    }`}
                  >
                    {p.fill_pct.toFixed(0)}%
                  </td>
                  <td className="py-2 px-3 text-right tabular-nums">{p.rsi.toFixed(0)}</td>
                  <td className="py-2 px-3 text-right tabular-nums">{inr(p.close)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );

  if (!picks.length) {
    return <p className="text-muted text-sm text-center py-8">No active gaps in snapshot.</p>;
  }

  return (
    <div className="space-y-4">
      {downs.length > 0 && renderTable(downs, "Gap Down — long fill bias (BUY)")}
      {ups.length > 0 && renderTable(ups, "Gap Up — short fill bias (not paper-traded)")}
    </div>
  );
}
