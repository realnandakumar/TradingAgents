"use client";

import { RatingBadge, SignalList } from "@/components/Badges";
import { dateTimeIST, inr, pct, qty, shortSymbol } from "@/lib/format";
import { useQuotes } from "@/lib/useQuotes";
import type { Position } from "@/lib/types";

export function OpenPositionsLive({ positions }: { positions: Position[] }) {
  const { quotes, loading } = useQuotes(positions.map((p) => p.ticker));

  if (positions.length === 0) return <p className="text-muted text-sm">No open positions.</p>;

  let totalPnl = 0;
  let haveLive = false;

  const rows = positions.map((p) => {
    const q = quotes[p.ticker];
    const live = q?.price ?? null;
    const sincePct = live != null ? ((live - p.entry_price) / p.entry_price) * 100 : null;
    const pnl = live != null ? (live - p.entry_price) * p.shares : null;
    if (pnl != null) {
      totalPnl += pnl;
      haveLive = true;
    }
    return { p, live, sincePct, pnl };
  });

  return (
    <div>
      <div className="flex items-center gap-3 mb-3 text-sm">
        <span className="text-muted">Live unrealized P&amp;L:</span>
        <span
          className={`font-semibold tabular-nums ${
            !haveLive ? "text-muted" : totalPnl >= 0 ? "text-bull" : "text-bear"
          }`}
        >
          {haveLive ? inr(totalPnl) : loading ? "loading…" : "—"}
        </span>
        <span className="text-muted text-xs">≈15-min delayed · auto-refreshes</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs uppercase tracking-wide border-b border-border">
              <th className="text-left font-medium py-2 pr-3">Ticker</th>
              <th className="text-left font-medium py-2 pr-3">Rating</th>
              <th className="text-right font-medium py-2 pr-3">Qty</th>
              <th className="text-right font-medium py-2 pr-3">Entry</th>
              <th className="text-right font-medium py-2 pr-3">Cost</th>
              <th className="text-right font-medium py-2 pr-3">Stop / Target</th>
              <th className="text-left font-medium py-2 pr-3">Ordered</th>
              <th className="text-left font-medium py-2 pr-3">Executes</th>
              <th className="text-right font-medium py-2 pr-3">Live</th>
              <th className="text-right font-medium py-2 pr-3">Value</th>
              <th className="text-right font-medium py-2 pr-3">Since entry</th>
              <th className="text-right font-medium py-2 pr-3">P&amp;L</th>
              <th className="text-left font-medium py-2">Signals</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ p, live, sincePct, pnl }) => (
              <tr key={`${p.ticker}-${p.entry_date}`} className="border-b border-border/50 last:border-0">
                <td className="py-2 pr-3 font-medium">{shortSymbol(p.ticker)}</td>
                <td className="py-2 pr-3"><RatingBadge rating={p.rating} /></td>
                <td className="py-2 pr-3 text-right tabular-nums text-muted whitespace-nowrap">{qty(p.shares)}</td>
                <td className="py-2 pr-3 text-right tabular-nums text-muted whitespace-nowrap">{inr(p.entry_price)}</td>
                <td className="py-2 pr-3 text-right tabular-nums text-muted whitespace-nowrap">{inr(p.alloc)}</td>
                <td className="py-2 pr-3 text-right text-xs whitespace-nowrap">
                  {p.stoploss != null ? (
                    <>
                      <div className="text-bear">{inr(p.stoploss)}{p.stop_pct != null && ` (${pct(p.stop_pct)})`}</div>
                      <div className="text-bull">{inr(p.target)}{p.target_pct != null && ` (${pct(p.target_pct)})`}</div>
                    </>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </td>
                <td className="py-2 pr-3 text-muted text-xs whitespace-nowrap">
                  {p.order_time ? dateTimeIST(p.order_time) : p.entry_date}
                </td>
                <td className="py-2 pr-3 text-xs whitespace-nowrap">
                  {p.execution_time ? dateTimeIST(p.execution_time) : "—"}
                  {p.execution_deferred && (
                    <span className="block text-[10px] text-accent">next open</span>
                  )}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{live != null ? inr(live) : "—"}</td>
                <td className="py-2 pr-3 text-right tabular-nums whitespace-nowrap">{live != null ? inr(live * p.shares) : "—"}</td>
                <td className={`py-2 pr-3 text-right tabular-nums whitespace-nowrap ${ sincePct == null ? "text-muted" : sincePct >= 0 ? "text-bull" : "text-bear"}`}>
                  {sincePct == null ? "—" : pct(sincePct)}
                </td>
                <td className={`py-2 pr-4 text-right tabular-nums whitespace-nowrap min-w-[80px] ${ pnl == null ? "text-muted" : pnl >= 0 ? "text-bull" : "text-bear"}`}>
                  {pnl == null ? "—" : inr(pnl)}
                </td>
                <td className="py-2 pl-1 min-w-[160px]"><SignalList signals={p.signals} abbrev /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
