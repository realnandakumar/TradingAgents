"use client";

import Link from "next/link";

import { ChartTickerLink } from "@/components/ChartTickerLink";
import { inr, pct, shortSymbol } from "@/lib/format";
import type { OverlapSummary, TickerOverlap } from "@/lib/overlaps-server";
import { useQuotes } from "@/lib/useQuotes";

function deskShort(label: string): string {
  return label.replace(/ Desk$/, "");
}

function mtmPct(entry: number | null, live: number | null): number | null {
  if (entry == null || live == null || entry <= 0) return null;
  return ((live - entry) / entry) * 100;
}

function cushionPct(live: number | null, stop: number | null): number | null {
  if (live == null || stop == null || live <= 0) return null;
  return ((live - stop) / live) * 100;
}

export function OverlapsTable({ summary }: { summary: OverlapSummary }) {
  const { overlapTickers } = summary;
  const symbols = overlapTickers.map((o) => o.ticker);
  const { quotes, loading } = useQuotes(symbols);

  if (overlapTickers.length === 0) {
    return (
      <div className="card p-8 text-center">
        <h2 className="font-medium mb-2">No cross-desk overlaps</h2>
        <p className="text-muted text-sm max-w-md mx-auto">
          No ticker is open on more than one desk right now. Each desk book is independent — this
          view only flags names you are running in parallel.
        </p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-3 border-b border-border flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-medium">Open on multiple desks</h2>
        <span className="text-xs text-muted">
          {overlapTickers.length} ticker(s) · live ≈15m delayed · auto-refresh
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="text-muted uppercase tracking-wide border-b border-border bg-surface-2/30">
              <th className="text-left font-medium py-2 px-3">Ticker</th>
              <th className="text-center font-medium py-2 px-2">#</th>
              <th className="text-left font-medium py-2 px-3">Desk</th>
              <th className="text-right font-medium py-2 px-3">SL</th>
              <th className="text-right font-medium py-2 px-3">Entry</th>
              <th className="text-right font-medium py-2 px-3">T1</th>
              <th className="text-right font-medium py-2 px-3">Live</th>
              <th className="text-right font-medium py-2 px-3">MTM%</th>
              <th className="text-right font-medium py-2 px-3">Cush%</th>
              <th className="text-right font-medium py-2 px-3">Chart</th>
            </tr>
          </thead>
          <tbody>
            {overlapTickers.map((row) => (
              <OverlapTickerRows
                key={row.ticker}
                row={row}
                quote={quotes[row.ticker]}
                loading={loading}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function OverlapTickerRows({
  row,
  quote,
  loading,
}: {
  row: TickerOverlap;
  quote: { price: number | null } | undefined;
  loading: boolean;
}) {
  const live = quote?.price ?? null;
  const legs = row.desks;

  return (
    <>
      {legs.map((d, i) => {
        const mtm = mtmPct(d.entryPrice, live);
        const cushion = cushionPct(live, d.stopLoss);
        const tight = cushion != null && cushion < 7;
        const isFirst = i === 0;

        return (
          <tr
            key={`${row.ticker}-${d.deskId}`}
            className={`border-b border-border/40 hover:bg-surface-2/30 ${tight ? "bg-bear/5" : ""} ${
              !isFirst ? "border-t-0" : ""
            }`}
          >
            {isFirst ? (
              <>
                <td
                  rowSpan={legs.length}
                  className="py-2 px-3 font-semibold align-top border-r border-border/30"
                >
                  <ChartTickerLink ticker={row.ticker} className="font-semibold hover:text-accent" />
                  <div className="text-[10px] text-muted font-sans font-normal mt-0.5">
                    {shortSymbol(row.ticker)}
                  </div>
                  {d.sector ? (
                    <div className="text-[10px] text-muted font-sans font-normal">{d.sector}</div>
                  ) : null}
                </td>
                <td
                  rowSpan={legs.length}
                  className="py-2 px-2 text-center align-top border-r border-border/30"
                >
                  <span
                    className={`inline-flex min-w-[1.5rem] justify-center px-1.5 py-0.5 rounded text-xs ${
                      row.deskCount >= 3
                        ? "bg-bear/15 text-bear border border-bear/30"
                        : "bg-accent/15 text-accent border border-accent/30"
                    }`}
                  >
                    {row.deskCount}
                  </span>
                </td>
              </>
            ) : null}
            <td className="py-2 px-3">
              <Link
                href={d.href}
                className="text-[11px] font-sans px-1.5 py-0.5 rounded border border-border hover:border-accent/40 hover:text-accent"
              >
                {deskShort(d.deskLabel)}
              </Link>
              {d.screenDate ? (
                <div className="text-[10px] text-muted font-sans mt-0.5">{d.screenDate}</div>
              ) : null}
            </td>
            <td className="py-2 px-3 text-right tabular-nums text-bear">
              {d.stopLoss != null ? inr(d.stopLoss) : "—"}
            </td>
            <td className="py-2 px-3 text-right tabular-nums">{inr(d.entryPrice)}</td>
            <td className="py-2 px-3 text-right tabular-nums text-bull">
              {d.target1 != null ? inr(d.target1) : "—"}
            </td>
            {isFirst ? (
              <td
                rowSpan={legs.length}
                className={`py-2 px-3 text-right tabular-nums align-top font-semibold ${
                  live == null ? "text-muted" : ""
                }`}
              >
                {live != null ? inr(live) : loading ? "…" : "—"}
              </td>
            ) : null}
            <td
              className={`py-2 px-3 text-right tabular-nums ${
                mtm == null ? "text-muted" : mtm >= 0 ? "text-bull" : "text-bear"
              }`}
            >
              {mtm != null ? pct(mtm, 2) : "—"}
            </td>
            <td
              className={`py-2 px-3 text-right tabular-nums ${
                cushion == null ? "text-muted" : tight ? "text-bear" : ""
              }`}
            >
              {cushion != null ? pct(cushion, 1) : "—"}
            </td>
            {isFirst ? (
              <td rowSpan={legs.length} className="py-2 px-3 text-right align-top">
                <Link
                  href={`/charts?ticker=${encodeURIComponent(row.ticker)}`}
                  className="text-xs font-sans text-accent hover:underline"
                >
                  Chart
                </Link>
              </td>
            ) : null}
          </tr>
        );
      })}
    </>
  );
}
