"use client";

import { inr, pct, shortSymbol } from "@/lib/format";
import { useQuotes } from "@/lib/useQuotes";
import type { SwingPosition } from "@/lib/swing-types";
import { shortSector } from "@/lib/swing-types";
import { ChartTickerLink } from "@/components/ChartTickerLink";
import { DeskOpenMetaCells, deskOpenMetaHeaders } from "@/components/DeskOpenMetaCells";

const MAX_POSITIONS = 20;

function cushionPct(last: number | null, stop: number): number | null {
  if (last == null || last <= 0) return null;
  return ((last - stop) / last) * 100;
}

export function SwingBlotter({ positions }: { positions: SwingPosition[] }) {
  const { quotes, loading } = useQuotes(positions.map((p) => p.ticker));
  const open = positions.filter((p) => p.status === "open");

  const rows = open.map((p) => {
    const q = quotes[p.ticker];
    const live = q?.price ?? p.entry_price;
    const stop = p.trailing_stop ?? p.stop_loss;
    const rem = (p.remaining_pct ?? 100) / 100;
    const mtmPct = ((live - p.entry_price) / p.entry_price) * 100;
    const mtmAbs = (live - p.entry_price) * rem;
    const cushion = cushionPct(live, stop);
    const tight = cushion != null && cushion < 7;
    return { p, live, stop, mtmPct, mtmAbs, cushion, tight, hasQuote: q?.price != null };
  });
  const quotedRows = rows.filter((row) => row.hasQuote);
  const mtmSum = quotedRows.reduce((sum, row) => sum + row.mtmAbs, 0);
  const haveLive = quotedRows.length > 0;

  const avgRisk =
    open.reduce((s, p) => s + Math.abs(p.stop_loss_pct), 0) / (open.length || 1);
  const avgT1 = open.reduce((s, p) => s + p.target_1_pct, 0) / (open.length || 1);

  const sectors: Record<string, number> = {};
  for (const p of open) sectors[p.sector] = (sectors[p.sector] ?? 0) + 1;

  return (
    <div className="space-y-0">
      {/* KPI strip */}
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
          { label: "Avg risk", value: pct(-avgRisk), sub: "to stop", tone: "text-bear" },
          { label: "Avg T1", value: pct(avgT1, 2), sub: "upside", tone: "text-bull" },
          { label: "Closed", value: String(positions.filter((p) => p.status === "closed").length), sub: "lifetime" },
        ].map((k) => (
          <div key={k.label} className="px-4 py-3 border-r border-border/60 last:border-r-0">
            <div className="text-[10px] uppercase tracking-wider text-muted">{k.label}</div>
            <div className={`text-lg font-semibold tabular-nums ${k.tone ?? ""}`}>{k.value}</div>
            <div className="text-[10px] text-muted">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-[1fr_240px]">
        {/* Blotter */}
        <div className="border-r border-border min-w-0">
          <div className="px-4 py-2.5 border-b border-border/60 flex items-center gap-2 text-xs">
            <span className="font-medium uppercase tracking-wide">Position blotter</span>
            <span className="text-muted">{open.length} lines</span>
            <span className="ml-auto text-muted">1D · T1 full exit · 20d</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-muted uppercase tracking-wide border-b border-border bg-surface/40">
                  {["SYM", "NAME", "SECT", ...deskOpenMetaHeaders(), "LAST", "MTM%", "STOP", "RISK%", "T1", "UPSIDE", "CUSH%", "RSI", "ADX"].map(
                    (h) => (
                      <th
                        key={h}
                        className={`font-medium py-2 px-2 whitespace-nowrap ${
                          ["LAST", "MTM%", "STOP", "RISK%", "T1", "UPSIDE", "CUSH%", "RSI", "ADX", ...deskOpenMetaHeaders()].includes(h)
                            ? "text-right"
                            : "text-left"
                        }`}
                      >
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.map(({ p, live, stop, mtmPct, cushion, tight }) => (
                  <tr
                    key={p.ticker}
                    className={`border-b border-border/40 hover:bg-surface-2/30 ${tight ? "bg-bear/5" : ""}`}
                  >
                    <td className="py-2 px-2 font-semibold">
                      <ChartTickerLink ticker={p.ticker} desk="swing" className="font-semibold hover:text-accent" />
                    </td>
                    <td className="py-2 px-2 text-muted max-w-[140px] truncate">{p.stock_name.replace(" Ltd.", "")}</td>
                    <td className="py-2 px-2 text-muted">{shortSector(p.sector)}</td>
                    <DeskOpenMetaCells p={p} />
                    <td className="py-2 px-2 text-right tabular-nums">{inr(live)}</td>
                    <td className={`py-2 px-2 text-right tabular-nums ${mtmPct >= 0 ? "text-bull" : "text-bear"}`}>
                      {pct(mtmPct, 2)}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums text-bear">{inr(stop)}</td>
                    <td className="py-2 px-2 text-right tabular-nums text-bear">{pct(p.stop_loss_pct, 2)}</td>
                    <td className="py-2 px-2 text-right tabular-nums text-bull">{inr(p.target_1)}</td>
                    <td className="py-2 px-2 text-right tabular-nums text-bull">{pct(p.target_1_pct, 2)}</td>
                    <td className={`py-2 px-2 text-right tabular-nums ${tight ? "text-bear font-semibold" : ""}`}>
                      {cushion == null ? "—" : pct(cushion, 2)}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums">{p.rsi?.toFixed(1) ?? "—"}</td>
                    <td className="py-2 px-2 text-right tabular-nums">{p.adx?.toFixed(1) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Book panel */}
        <div className="p-4 space-y-5 text-xs">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted mb-2">Capacity</div>
            <div className="h-2 rounded-full bg-surface-2 overflow-hidden flex">
              {open.map((p, i) => (
                <div
                  key={p.ticker}
                  className="h-full"
                  style={{
                    width: `${100 / MAX_POSITIONS}%`,
                    background: `hsl(${(i * 67) % 360} 55% 50%)`,
                  }}
                  title={shortSymbol(p.ticker)}
                />
              ))}
            </div>
            <div className="flex justify-between mt-1 text-muted">
              <span>{open.length} deployed</span>
              <span>{MAX_POSITIONS - open.length} free</span>
            </div>
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted mb-2">Sector exposure</div>
            <ul className="space-y-1.5">
              {Object.entries(sectors)
                .sort((a, b) => b[1] - a[1])
                .map(([sector, count]) => (
                  <li key={sector} className="flex justify-between">
                    <span>{shortSector(sector)}</span>
                    <span className="text-muted">{count}</span>
                  </li>
                ))}
            </ul>
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted mb-2">Schedule</div>
            <p>09:30 · 11:45 · 14:30 IST</p>
            <p className="text-muted mt-1">Mon–Fri swing-daily</p>
          </div>

          <div className="text-[10px] text-muted pt-2 border-t border-border">
            {loading ? "Refreshing quotes…" : "Quotes ~15m delayed"}
          </div>
        </div>
      </div>
    </div>
  );
}
