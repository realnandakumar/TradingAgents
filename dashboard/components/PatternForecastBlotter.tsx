"use client";

import { inr, pct, shortSymbol } from "@/lib/format";
import { useQuotes } from "@/lib/useQuotes";
import type { PatternForecastPosition } from "@/lib/pattern-forecast-server";
import { shortSector } from "@/lib/swing-types";
import { ChartTickerLink } from "@/components/ChartTickerLink";
import { DeskOpenMetaCells, deskOpenMetaHeaders } from "@/components/DeskOpenMetaCells";

const MAX_POSITIONS = 20;
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

  const sectors: Record<string, number> = {};
  for (const p of open) sectors[p.sector] = (sectors[p.sector] ?? 0) + 1;

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

      <div className="grid lg:grid-cols-[1fr_240px]">
        <div className="border-r border-border min-w-0">
          <div className="px-4 py-2.5 border-b border-border/60 flex items-center gap-2 text-xs">
            <span className="font-medium uppercase tracking-wide">Position blotter</span>
            <span className="text-muted">{open.length} lines</span>
            <span className="ml-auto text-muted">1D · target full · UP only · 5d</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-muted uppercase border-b border-border bg-surface-2/30">
                  <th className="text-left py-2 px-3">SYM</th>
                  {deskOpenMetaHeaders().map((h) => (
                    <th key={h} className={`py-2 px-2 whitespace-nowrap ${h === "OK" ? "text-center" : "text-right"}`}>
                      {h}
                    </th>
                  ))}
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
                    <td className="py-2 px-3 font-medium">
                      <ChartTickerLink ticker={p.ticker} desk="pattern-forecast" className="hover:text-accent" />
                    </td>
                    <DeskOpenMetaCells p={p} />
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
                    <td className="py-2 px-3 text-muted truncate max-w-[100px]">
                      {shortSector(p.sector)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="p-4 space-y-4 text-xs">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted mb-2">Sector exposure</div>
            <p className="text-muted mb-1.5">Max 4 open names per sector on new entries</p>
            <ul className="space-y-1.5">
              {Object.entries(sectors)
                .sort((a, b) => b[1] - a[1])
                .map(([sector, count]) => (
                  <li key={sector} className="flex justify-between">
                    <span>{shortSector(sector)}</span>
                    <span className={count >= 4 ? "text-bear" : "text-muted"}>{count}</span>
                  </li>
                ))}
            </ul>
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted mb-2">Remarks</div>
            {rows.length === 0 ? (
              <p className="text-muted">No open positions.</p>
            ) : (
              <ul className="space-y-2 font-mono text-[10px] leading-snug">
                {rows.slice(0, 8).map(({ p, mtmPct }) => (
                  <li key={p.ticker} className="border-b border-border/30 pb-2">
                    <div className="font-medium">{shortSymbol(p.ticker)}</div>
                    <div className="text-muted">{p.remark ?? "—"}</div>
                    <div className={mtmPct >= 0 ? "text-bull" : "text-bear"}>
                      {pct(mtmPct, 1)}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
