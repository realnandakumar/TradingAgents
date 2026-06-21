import { RatingBadge, SignalList } from "@/components/Badges";
import { SetupNotice, EmptyState } from "@/components/SetupNotice";
import { getLatestPaper } from "@/lib/data";
import { inr, pctFromFraction, shortSymbol } from "@/lib/format";
import { isConfigured } from "@/lib/supabase";
import type { Position } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function PositionsPage() {
  if (!isConfigured()) return <SetupNotice />;

  const paper = await getLatestPaper();
  const positions = paper?.data.positions ?? [];
  const open = positions.filter((p) => p.status === "open");
  const closed = positions.filter((p) => p.status === "closed");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Paper positions</h1>
        <p className="text-muted text-sm">
          Simulated trades — no real money. Closed trades are scored on return and alpha vs Nifty.
        </p>
      </div>

      {positions.length === 0 ? (
        <EmptyState title="No paper positions yet" hint="Bullish screen calls open positions here." />
      ) : (
        <>
          <section className="card p-5">
            <h2 className="font-medium mb-3">Open ({open.length})</h2>
            {open.length === 0 ? (
              <p className="text-muted text-sm">No open positions.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-muted text-xs uppercase tracking-wide border-b border-border">
                      <th className="text-left font-medium py-2 pr-3">Ticker</th>
                      <th className="text-left font-medium py-2 pr-3">Rating</th>
                      <th className="text-left font-medium py-2 pr-3">Entry date</th>
                      <th className="text-right font-medium py-2 pr-3">Entry</th>
                      <th className="text-left font-medium py-2">Signals</th>
                    </tr>
                  </thead>
                  <tbody>
                    {open.map((p) => (
                      <tr key={p.ticker} className="border-b border-border/50 last:border-0">
                        <td className="py-2.5 pr-3 font-medium">{shortSymbol(p.ticker)}</td>
                        <td className="py-2.5 pr-3"><RatingBadge rating={p.rating} /></td>
                        <td className="py-2.5 pr-3 text-muted">{p.entry_date}</td>
                        <td className="py-2.5 pr-3 text-right tabular-nums">{inr(p.entry_price)}</td>
                        <td className="py-2.5"><SignalList signals={p.signals} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="card p-5">
            <h2 className="font-medium mb-3">Closed ({closed.length})</h2>
            {closed.length === 0 ? (
              <p className="text-muted text-sm">No closed trades yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-muted text-xs uppercase tracking-wide border-b border-border">
                      <th className="text-left font-medium py-2 pr-3">Ticker</th>
                      <th className="text-right font-medium py-2 pr-3">Return</th>
                      <th className="text-right font-medium py-2 pr-3">Alpha vs Nifty</th>
                      <th className="text-right font-medium py-2 pr-3">Held</th>
                      <th className="text-left font-medium py-2">Signals</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closed.map((p: Position) => (
                      <tr key={`${p.ticker}-${p.entry_date}`} className="border-b border-border/50 last:border-0">
                        <td className="py-2.5 pr-3 font-medium">{shortSymbol(p.ticker)}</td>
                        <td className={`py-2.5 pr-3 text-right tabular-nums ${ (p.raw_return ?? 0) >= 0 ? "text-bull" : "text-bear"}`}>
                          {pctFromFraction(p.raw_return)}
                        </td>
                        <td className={`py-2.5 pr-3 text-right tabular-nums ${ (p.alpha_return ?? 0) >= 0 ? "text-bull" : "text-bear"}`}>
                          {pctFromFraction(p.alpha_return)}
                        </td>
                        <td className="py-2.5 pr-3 text-right tabular-nums text-muted">
                          {p.holding_days_actual != null ? `${p.holding_days_actual}d` : "—"}
                        </td>
                        <td className="py-2.5"><SignalList signals={p.signals} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
