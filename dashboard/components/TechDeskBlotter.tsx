"use client";

import Link from "next/link";
import { useState } from "react";

import { ChartTickerLink } from "@/components/ChartTickerLink";
import { MarkdownViewer } from "@/components/MarkdownViewer";
import { inr, pct, shortSymbol } from "@/lib/format";
import { useQuotes } from "@/lib/useQuotes";
import type { TechDeskPendingEntry, TechDeskPosition } from "@/lib/tech-desk-server";
import { DeskOpenMetaCells, deskOpenMetaHeaders } from "@/components/DeskOpenMetaCells";

const MAX_POSITIONS = 10;

function cushionPct(last: number | null, stop: number): number | null {
  if (last == null || last <= 0) return null;
  return ((last - stop) / last) * 100;
}

export function TechDeskBlotter({
  positions,
  pending,
}: {
  positions: TechDeskPosition[];
  pending: TechDeskPendingEntry[];
}) {
  const { quotes, loading } = useQuotes(positions.map((p) => p.ticker));
  const open = positions.filter((p) => p.status === "open");
  const closedCount = positions.filter((p) => p.status === "closed").length;
  const [reportTicker, setReportTicker] = useState<string | null>(null);
  const [reportMd, setReportMd] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  const openReport = async (ticker: string) => {
    setReportTicker(ticker);
    setReportLoading(true);
    setReportMd(null);
    try {
      const res = await fetch(
        `/api/tech-desk/report?ticker=${encodeURIComponent(ticker)}`,
      );
      const data = await res.json();
      if (res.ok) setReportMd(data.markdown);
      else setReportMd(`Report not found for ${ticker}. Run analyze first.`);
    } catch {
      setReportMd("Failed to load report.");
    } finally {
      setReportLoading(false);
    }
  };

  let mtmSum = 0;
  let haveLive = false;

  const rows = open.map((p) => {
    const q = quotes[p.ticker];
    const live = q?.price ?? p.entry_price;
    const stop = p.stop_loss;
    const mtmPct = ((live - p.entry_price) / p.entry_price) * 100;
    const mtmAbs = (live - p.entry_price) * (p.shares ?? 0);
    if (q?.price != null) {
      mtmSum += mtmAbs;
      haveLive = true;
    }
    const cushion = cushionPct(live, stop);
    const tight = cushion != null && cushion < 3;
    return { p, live, stop, mtmPct, cushion, tight };
  });

  const avgConf =
    open.reduce((s, p) => s + (p.confidence ?? 0), 0) / (open.length || 1);

  return (
    <div className="space-y-0">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 border-b border-border bg-surface-2/50">
        {[
          { label: "Open", value: `${open.length}/${MAX_POSITIONS}`, sub: "slots" },
          {
            label: "MTM P&L",
            value: haveLive ? inr(mtmSum) : loading ? "…" : inr(0),
            sub: "rupee",
            tone: haveLive ? (mtmSum >= 0 ? "text-bull" : "text-bear") : "text-muted",
          },
          { label: "Pending", value: String(pending.length), sub: "zone waits" },
          { label: "Slots free", value: String(MAX_POSITIONS - open.length), sub: "capacity" },
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
                  <ChartTickerLink ticker={p.ticker} desk="tech-desk" />
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
                  {p.report_date ? (
                    <button
                      type="button"
                      onClick={() => openReport(p.ticker)}
                      className="text-accent hover:underline text-[11px]"
                    >
                      {p.report_date}
                    </button>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
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
            <div key={pe.ticker} className="text-muted">
              {shortSymbol(pe.ticker)} · {pe.zone_low}–{pe.zone_high} · conf {pe.confidence ?? "—"}
            </div>
          ))}
        </div>
      )}

      {reportTicker ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="card max-w-2xl w-full max-h-[85vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h3 className="text-sm font-medium font-mono">{shortSymbol(reportTicker)} report</h3>
              <button
                type="button"
                onClick={() => {
                  setReportTicker(null);
                  setReportMd(null);
                }}
                className="text-muted hover:text-foreground text-lg leading-none"
              >
                ×
              </button>
            </div>
            <div className="p-4 overflow-y-auto flex-1">
              {reportLoading ? (
                <p className="text-sm text-muted">Loading…</p>
              ) : reportMd ? (
                <MarkdownViewer text={reportMd} />
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
