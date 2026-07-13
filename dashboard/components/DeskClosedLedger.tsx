"use client";

import { Fragment } from "react";
import { inr, shortSymbol } from "@/lib/format";
import {
  averageExitPrice,
  daysInTrade,
  entryDate,
  ledgerExitLegs,
  legSaleProceeds,
  purchaseNotional,
  realizedReturnPct,
  realizedRupeePnl,
  saleProceeds,
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
            <th className="text-right py-2 pr-2">@Buy</th>
            <th className="text-right py-2 pr-2">Purchase</th>
            <th className="text-right py-2 pr-2">@Sell</th>
            <th className="text-right py-2 pr-2">Sale</th>
            <th className="text-right py-2 pr-2">Gain</th>
            <th className="text-right py-2 pr-2">Gain%</th>
            {showAlpha && <th className="text-right py-2 pr-2">Alpha</th>}
            <th className="text-left py-2">Reason</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p, idx) => {
            const purchase = purchaseNotional(p);
            const sale = saleProceeds(p);
            const gain = realizedRupeePnl(p);
            const gainPct = realizedReturnPct(p);
            const sellPx = averageExitPrice(p);

            return (
              <Fragment key={`${p.ticker}-${p.exit_date ?? idx}`}>
                <tr className="border-b border-border/40">
                  <td className="py-2 pr-2 font-medium">{shortSymbol(p.ticker)}</td>
                  <td className="py-2 pr-2 text-right tabular-nums text-muted">{entryDate(p)}</td>
                  <td className="py-2 pr-2 text-right tabular-nums text-muted">{p.exit_date ?? "—"}</td>
                  <td className="py-2 pr-2 text-right tabular-nums">{daysInTrade(p)}</td>
                  <td className="py-2 pr-2 text-right tabular-nums">{p.shares ?? "—"}</td>
                  <td className="py-2 pr-2 text-right tabular-nums text-muted">
                    {p.entry_price != null ? inr(p.entry_price) : "—"}
                  </td>
                  <td className="py-2 pr-2 text-right tabular-nums">{inr(purchase)}</td>
                  <td className="py-2 pr-2 text-right tabular-nums text-muted">
                    {sellPx != null ? inr(sellPx) : "—"}
                  </td>
                  <td className="py-2 pr-2 text-right tabular-nums">{sale > 0 ? inr(sale) : "—"}</td>
                  <td
                    className={`py-2 pr-2 text-right tabular-nums font-medium ${
                      (gain ?? 0) >= 0 ? "text-bull" : "text-bear"
                    }`}
                  >
                    {gain != null ? inr(gain) : "—"}
                  </td>
                  <td
                    className={`py-2 pr-2 text-right tabular-nums ${
                      (gainPct ?? 0) >= 0 ? "text-bull" : "text-bear"
                    }`}
                  >
                    {gainPct != null ? `${gainPct >= 0 ? "+" : ""}${gainPct.toFixed(2)}%` : "—"}
                  </td>
                  {showAlpha && (
                    <td
                      className={`py-2 pr-2 text-right tabular-nums ${
                        (p.alpha_return ?? 0) >= 0 ? "text-bull" : "text-bear"
                      }`}
                    >
                      {p.alpha_return != null
                        ? `${(p.alpha_return * 100).toFixed(1)}%`
                        : "—"}
                    </td>
                  )}
                  <td className="py-2 text-muted">{p.exit_reason ?? "—"}</td>
                </tr>
                {ledgerExitLegs(p).map((leg, i) => {
                  const legSale = legSaleProceeds(p, leg);
                  return (
                    <tr
                      key={`${p.ticker}-leg-${i}`}
                      className="border-b border-border/20 bg-surface-2/20"
                    >
                      <td className="py-1 pr-2 pl-3 text-muted">- {leg.reason ?? "leg"}</td>
                      <td className="py-1 pr-2" colSpan={2} />
                      <td className="py-1 pr-2 text-right tabular-nums text-muted">
                        {leg.date ?? "—"}
                      </td>
                      <td className="py-1 pr-2 text-right tabular-nums">
                        {leg.pct != null ? `${leg.pct}%` : "—"}
                      </td>
                      <td className="py-1 pr-2" />
                      <td className="py-1 pr-2" />
                      <td className="py-1 pr-2 text-right tabular-nums text-muted">
                        {leg.price != null ? inr(leg.price) : "—"}
                      </td>
                      <td className="py-1 pr-2 text-right tabular-nums">{inr(legSale)}</td>
                      <td
                        className={`py-1 pr-2 text-right tabular-nums ${
                          (leg.rupee_pnl ?? 0) >= 0 ? "text-bull" : "text-bear"
                        }`}
                      >
                        {leg.rupee_pnl != null ? inr(leg.rupee_pnl) : "—"}
                      </td>
                      <td colSpan={showAlpha ? 2 : 1} />
                      <td />
                    </tr>
                  );
                })}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      <p className="text-[10px] text-muted mt-2 leading-relaxed">
        Purchase = qty × entry price · Sale = qty × exit price (blended across partial legs) · Gain
        = Sale − Purchase
      </p>
    </div>
  );
}
