"use client";

import { useState } from "react";

import { ChartTickerLink } from "@/components/ChartTickerLink";
import { DeskOpenMetaCells, deskOpenMetaHeaders } from "@/components/DeskOpenMetaCells";
import { DeskReportModal, type DeskReportTarget } from "@/components/DeskReportModal";
import { inr, pct, shortSymbol } from "@/lib/format";
import { useQuotes } from "@/lib/useQuotes";
import type { TechDeskPendingEntry, TechDeskPosition } from "@/lib/tech-desk-server";

function cushionPct(last: number | null, stop: number): number | null {
  if (last == null || last <= 0) return null;
  return ((last - stop) / last) * 100;
}

export function TechDeskBlotter({
  positions,
  pending,
  maxPositions = 20,
  deskId = "tech-desk",
}: {
  positions: TechDeskPosition[];
  pending: TechDeskPendingEntry[];
  maxPositions?: number;
  deskId?: string;
}) {
  const { quotes, loading } = useQuotes(positions.map((p) => p.ticker));
  const open = positions.filter((p) => p.status === "open");
  const closedCount = positions.filter((p) => p.status === "closed").length;
  const [reportTarget, setReportTarget] = useState<DeskReportTarget | null>(null);

  const openReport = (
    ticker: string,
    opts?: { reportDate?: string | null; reportPath?: string | null },
  ) => {
    setReportTarget({
      ticker,
      reportDate: opts?.reportDate,
      reportPath: opts?.reportPath,
    });
  };

  const rows = open.map((p) => {
    const q = quotes[p.ticker];
    const live = q?.price ?? p.entry_price;
    const stop = p.stop_loss;
    const mtmPct = ((live - p.entry_price) / p.entry_price) * 100;
    const mtmAbs = (live - p.entry_price) * (p.shares ?? 0);
    const cushion = cushionPct(live, stop);
    const tight = cushion != null && cushion < 3;
    return { p, live, stop, mtmPct, mtmAbs, cushion, tight, hasQuote: q?.price != null };
  });
  const quotedRows = rows.filter((row) => row.hasQuote);
  const mtmSum = quotedRows.reduce((sum, row) => sum + row.mtmAbs, 0);
  const haveLive = quotedRows.length > 0;

  const avgConf =
    open.reduce((s, p) => s + (p.confidence ?? 0), 0) / (open.length || 1);

  return (
    <div className="space-y-0">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 border-b border-border bg-surface-2/50">
        {[
          { label: "Open", value: `${open.length}/${maxPositions}`, sub: "slots" },
          {
            label: "MTM P&L",
            value: haveLive ? inr(mtmSum) : loading ? "…" : inr(0),
            sub: "rupee",
            tone: haveLive ? (mtmSum >= 0 ? "text-bull" : "text-bear") : "text-muted",
          },
          { label: "Pending", value: String(pending.length), sub: "zone waits" },
          { label: "Slots free", value: String(Math.max(0, maxPositions - open.length)), sub: "capacity" },
          { label: "Avg conf", value: open.length ? String(Math.round(avgConf)) : "—", sub: "0–100" },
          { label: "Closed", value: String(closedCount), sub: "lifetime" },
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
              {deskOpenMetaHeaders().map((h) => (
                <th key={h} className={`py-2 px-2 whitespace-nowrap ${h === "OK" ? "text-center" : "text-right"}`}>
                  {h}
                </th>
              ))}
              <th className="text-right py-2 px-2">Conf</th>
              <th className="text-right py-2 px-2">Last</th>
              <th className="text-right py-2 px-2">MTM</th>
              <th className="text-right py-2 px-2">SL</th>
              <th className="text-right py-2 px-2">Cush</th>
              <th className="text-right py-2 px-2">T1</th>
              <th className="text-left py-2 px-2">Bias</th>
              <th className="text-left py-2 px-3">Rpt</th>
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
                  <ChartTickerLink ticker={p.ticker} desk={deskId} />
                </td>
                <DeskOpenMetaCells p={p} />
                <td className="py-2 px-2 text-right tabular-nums">{p.confidence ?? "—"}</td>
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
                <td className="py-2 px-2 text-right tabular-nums text-bull">{inr(p.target_1)}</td>
                <td className="py-2 px-2 text-muted">{p.bias ?? "—"}</td>
                <td className="py-2 px-3">
                  <button
                    type="button"
                    onClick={() =>
                      openReport(p.ticker, {
                        reportDate: p.report_date,
                        reportPath: p.report_path,
                      })
                    }
                    className="text-accent hover:underline text-[11px]"
                  >
                    {p.report_date ?? "view"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pending.length > 0 && (
        <div className="px-4 py-3 border-t border-border bg-surface-2/20 text-xs font-mono">
          <div className="text-[10px] uppercase text-muted mb-2">Pending pullback zones</div>
          {pending.map((pe) => (
            <div key={pe.ticker} className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted py-0.5">
              <span>
                {shortSymbol(pe.ticker)} · {pe.zone_low}–{pe.zone_high} · conf {pe.confidence ?? "—"}
              </span>
              <button
                type="button"
                onClick={() =>
                  // Prefer latest report folder so Trader/Levels resolve after re-analyze.
                  openReport(pe.ticker)
                }
                className="text-accent hover:underline text-[11px]"
              >
                MA / Trader
              </button>
            </div>
          ))}
        </div>
      )}

      <DeskReportModal target={reportTarget} onClose={() => setReportTarget(null)} />
    </div>
  );
}
