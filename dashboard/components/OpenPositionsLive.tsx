"use client";

import { RatingBadge, SignalList } from "@/components/Badges";
import { inr, pct, shortSymbol } from "@/lib/format";
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
              <th className="text-right font-medium py-2 pr-3">Entry</th>
              <th className="text-right font-medium py-2 pr-3">Live</th>
              <th className="text-right font-medium py-2 pr-3">Since entry</th>
              <th className="text-right font-medium py-2 pr-3">P&amp;L</th>
              <th className="text-left font-medium py-2">Signals</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ p, live, sincePct, pnl }) => (
              <tr key={`${p.ticker}-${p.entry_date}`} className="border-b border-border/50 last:border-0">
                <td className="py-2.5 pr-3 font-medium">{shortSymbol(p.ticker)}</td>
                <td className="py-2.5 pr-3"><RatingBadge rating={p.rating} /></td>
                <td className="py-2.5 pr-3 text-right tabular-nums text-muted">{inr(p.entry_price)}</td>
                <td className="py-2.5 pr-3 text-right tabular-nums">{live != null ? inr(live) : "—"}</td>
                <td className={`py-2.5 pr-3 text-right tabular-nums ${ sincePct == null ? "text-muted" : sincePct >= 0 ? "text-bull" : "text-bear"}`}>
                  {sincePct == null ? "—" : pct(sincePct)}
                </td>
                <td className={`py-2.5 pr-3 text-right tabular-nums ${ pnl == null ? "text-muted" : pnl >= 0 ? "text-bull" : "text-bear"}`}>
                  {pnl == null ? "—" : inr(pnl)}
                </td>
                <td className="py-2.5"><SignalList signals={p.signals} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
