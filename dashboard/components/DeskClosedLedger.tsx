"use client";

import { Fragment } from "react";
import { inr, pctFromFraction, shortSymbol } from "@/lib/format";
import {
  daysInTrade,
  entryDate,
  partialLegs,
  purchaseNotional,
  slotBudget,
  withinBudget,
  type DeskPositionMeta,
} from "@/lib/desk-position";

export function DeskClosedLedger({
  positions,
  showAlpha = true,
}: {
  positions: DeskPositionMeta[];
  showAlpha?: boolean;
}) {
  if (positions.length === 0) {
    return <p className="text-muted text-sm">No closed trades yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-muted uppercase border-b border-border">
            <th className="text-left py-2 pr-2">SYM</th>
            <th className="text-right py-2 pr-2">Entry</th>
            <th className="text-right py-2 pr-2">Exit</th>
            <th className="text-right py-2 pr-2">Days</th>
            <th className="text-right py-2 pr-2">Qty</th>
            <th className="text-right py-2 pr-2">Purchase</th>
            <th className="text-right py-2 pr-2">Budget</th>
            <th className="text-center py-2 pr-2">OK</th>
            <th className="text-right py-2 pr-2">Return</th>
            {showAlpha && <th className="text-right py-2 pr-2">Alpha</th>}
            <th className="text-right py-2 pr-2">P&amp;L</th>
            <th className="text-left py-2">Reason</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p, idx) => (
            <Fragment key={`${p.ticker}-${p.exit_date ?? idx}`}>
              <tr className="border-b border-border/40">
                <td className="py-2 pr-2 font-medium">{shortSymbol(p.ticker)}</td>
                <td className="py-2 pr-2 text-right tabular-nums text-muted">{entryDate(p)}</td>
                <td className="py-2 pr-2 text-right tabular-nums text-muted">{p.exit_date ?? "—"}</td>
                <td className="py-2 pr-2 text-right tabular-nums">{daysInTrade(p)}</td>
                <td className="py-2 pr-2 text-right tabular-nums">{p.shares ?? "—"}</td>
                <td className="py-2 pr-2 text-right tabular-nums">{inr(purchaseNotional(p))}</td>
                <td className="py-2 pr-2 text-right tabular-nums text-muted">
                  {slotBudget(p) ? inr(slotBudget(p)) : "—"}
                </td>
                <td
                  className={`py-2 pr-2 text-center text-[10px] ${
                    withinBudget(p) ? "text-bull" : "text-bear font-semibold"
                  }`}
                >
                  {withinBudget(p) ? "OK" : "OVER"}
                </td>
                <td
                  className={`py-2 pr-2 text-right tabular-nums ${
                    (p.raw_return ?? 0) >= 0 ? "text-bull" : "text-bear"
                  }`}
                >
                  {pctFromFraction(p.raw_return)}
                </td>
                {showAlpha && (
                  <td
                    className={`py-2 pr-2 text-right tabular-nums ${
                      (p.alpha_return ?? 0) >= 0 ? "text-bull" : "text-bear"
                    }`}
                  >
                    {pctFromFraction(p.alpha_return)}
                  </td>
                )}
                <td className="py-2 pr-2 text-right tabular-nums">
                  {p.rupee_pnl != null ? inr(p.rupee_pnl) : "—"}
                </td>
                <td className="py-2 text-muted">{p.exit_reason ?? "—"}</td>
              </tr>
              {partialLegs(p).map((leg, i) => (
                <tr key={`${p.ticker}-leg-${i}`} className="border-b border-border/20 bg-surface-2/20">
                  <td className="py-1 pr-2 pl-3 text-muted">
                    {i === partialLegs(p).length - 1 ? "└" : "├"} {leg.reason ?? "partial"}
                  </td>
                  <td className="py-1 pr-2" />
                  <td className="py-1 pr-2 text-right tabular-nums text-muted">{leg.date ?? "—"}</td>
                  <td className="py-1 pr-2" />
                  <td className="py-1 pr-2 text-right tabular-nums">{leg.pct != null ? `${leg.pct}%` : "—"}</td>
                  <td className="py-1 pr-2 text-right tabular-nums">{leg.price != null ? inr(leg.price) : "—"}</td>
                  <td colSpan={showAlpha ? 4 : 3} className="py-1 pr-2 text-right tabular-nums text-muted">
                    {leg.rupee_pnl != null ? inr(leg.rupee_pnl) : "—"}
                  </td>
                  <td className="py-1 text-muted text-[10px]">partial</td>
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
