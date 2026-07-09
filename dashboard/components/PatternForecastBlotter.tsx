"use client";

import { inr, pct, shortSymbol } from "@/lib/format";
import { useQuotes } from "@/lib/useQuotes";
import type { PatternForecastPosition } from "@/lib/pattern-forecast-server";
import { shortSector } from "@/lib/swing-types";

const MAX_POSITIONS = 10;
const MAX_HOLD_DAYS = 5;

function cushionPct(last: number | null, stop: number): number | null {
  if (last == null || last <= 0) return null;
  return ((last - stop) / last) * 100;
}

export function PatternForecastBlotter({ positions }: { positions: PatternForecastPosition[] }) {
  const { quotes, loading } = useQuotes(positions.map((p) => p.ticker));
  const open = positions.filter((p) => p.status === "open");

  let mtmSum = 0;
  let haveLive = false;

  const rows = open.map((p) => {
    const q = quotes[p.ticker];
    const live = q?.price ?? p.entry_price;
    const stop = p.stop_loss;
    const mtmPct = ((live - p.entry_price) / p.entry_price) * 100;
    const mtmAbs = live - p.entry_price;
    if (q?.price != null) {
      mtmSum += mtmAbs;
      haveLive = true;
    }
    const cushion = cushionPct(live, stop);
    const tight = cushion != null && cushion < 3;
    return { p, live, stop, mtmPct, cushion, tight };
  });

  const avgRisk =
    open.reduce((s, p) => s + Math.abs(p.stop_loss_pct), 0) / (open.length || 1);
  const avgTarget =
    open.reduce((s, p) => s + (p.target_max_pct ?? 0), 0) / (open.length || 1);

  return (
    <div className="space-y-0">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 border-b border-border bg-surface-2/50">
        {[
          { label: "Open", value: `${open.length}/${MAX_POSITIONS}`, sub: "slots" },
          {
            label: "MTM P&L",
            value: haveLive ? inr(mtmSum) : loading ? "…" : inr(0),
            sub: "per share",
            tone: haveLive ? (mtmSum >= 0 ? "text-bull" : "text-bear") : "text-muted",
          },
          { label: "Slots free", value: String(MAX_POSITIONS - open.length), sub: "capacity" },
          { label: "Avg risk", value: pct(-avgRisk), sub: "to SL", tone: "text-bear" },
          { label: "Avg max 5d", value: pct(avgTarget, 2), sub: "target", tone: "text-bull" },
          { label: "Max hold", value: `${MAX_HOLD_DAYS}d`, sub: "time exit" },
        ].map((k) => (
          <div key={k.label} className="px-4 py-3 border-r border-border/60 last:border-r-0">
            <div className="text-[10px] uppercase tracking-wider text-muted">{k.label}</div>
            <div className={`text-lg font-semibold tabular-nums ${k.tone ?? ""}`}>{k.value}</div>
            <div className="text-[10px] text-muted">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="text-muted uppercase border-b border-border bg-surface-2/30">
              <th className="text-left py-2 px-3">SYM</th>
              <th className="text-right py-2 px-2">Prob%</th>
              <th className="text-right py-2 px-2">Last</th>
              <th className="text-right py-2 px-2">MTM</th>
              <th className="text-right py-2 px-2">SL</th>
              <th className="text-right py-2 px-2">Cush</th>
              <th className="text-right py-2 px-2">Max5d</th>
              <th className="text-right py-2 px-2">Proj5d</th>
              <th className="text-left py-2 px-3">Sector</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ p, live, stop, mtmPct, cushion, tight }) => (
              <tr
                key={p.ticker}
                className={`border-b border-border/40 hover:bg-surface-2/40 ${
                  tight ? "bg-bear/5" : ""
                }`}
              >
                <td className="py-2 px-3 font-medium">{shortSymbol(p.ticker)}</td>
                <td className="py-2 px-2 text-right tabular-nums">{p.probability?.toFixed(1) ?? "—"}</td>
                <td className="py-2 px-2 text-right tabular-nums">{inr(live)}</td>
                <td
                  className={`py-2 px-2 text-right tabular-nums ${
                    mtmPct >= 0 ? "text-bull" : "text-bear"
                  }`}
                >
                  {pct(mtmPct, 1)}
                </td>
                <td className="py-2 px-2 text-right tabular-nums text-bear">{inr(stop)}</td>
                <td className="py-2 px-2 text-right tabular-nums">
                  {cushion != null ? pct(cushion, 1) : "—"}
                </td>
                <td className="py-2 px-2 text-right tabular-nums text-bull">
                  {p.target_max != null ? inr(p.target_max) : "—"}
                </td>
                <td className="py-2 px-2 text-right tabular-nums text-muted">
                  {p.projected_close_5d != null ? inr(p.projected_close_5d) : "—"}
                </td>
                <td className="py-2 px-3 text-muted">{shortSector(p.sector)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
