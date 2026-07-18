"use client";

import { ChartTickerLink } from "@/components/ChartTickerLink";
import type { CandleScreenerGroup } from "@/lib/candlesticks-server";

function biasClass(bias: string) {
  if (bias === "BULLISH") return "text-bull";
  if (bias === "BEARISH") return "text-bear";
  return "text-muted";
}

export function CandlesticksBlotter({ groups }: { groups: CandleScreenerGroup[] }) {
  if (!groups.length) {
    return <p className="text-muted text-sm text-center py-8">No candlestick hits in snapshot.</p>;
  }

  return (
    <div className="space-y-4">
      {groups.map((g) => (
        <section key={g.pattern_id} className="card overflow-hidden">
          <div className="px-4 py-2.5 border-b border-border/60 flex flex-wrap items-center gap-2 text-xs">
            <span className="font-semibold">{g.pattern_name}</span>
            <span className={`uppercase ${biasClass(g.bias)}`}>{g.bias}</span>
            <span className="text-muted">*{g.stars}</span>
            <span className="text-muted ml-auto">({g.count} hits)</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-muted uppercase border-b border-border">
                  <th className="text-left py-2 px-3">#</th>
                  <th className="text-left py-2 px-3">Symbol</th>
                  <th className="text-left py-2 px-3">Name</th>
                  <th className="text-right py-2 px-3">Age</th>
                  <th className="text-left py-2 px-3">Status</th>
                  <th className="text-right py-2 px-3">Entry</th>
                  <th className="text-right py-2 px-3">Stop</th>
                  <th className="text-right py-2 px-3">T1</th>
                  <th className="text-right py-2 px-3">T2</th>
                  <th className="text-right py-2 px-3">R:R</th>
                  <th className="text-left py-2 px-3">Detail</th>
                </tr>
              </thead>
              <tbody>
                {g.picks.map((p) => (
                  <tr
                    key={`${p.symbol}-${p.pattern_id}-${p.rank}`}
                    className="border-b border-border/40 last:border-0"
                  >
                    <td className="py-2 px-3 text-muted">{p.rank}</td>
                    <td className="py-2 px-3 font-medium">
                      <ChartTickerLink
                        ticker={p.ticker}
                        desk="candlesticks"
                        patternId={p.pattern_id}
                        className="hover:text-accent"
                      />
                    </td>
                    <td className="py-2 px-3 text-muted truncate max-w-[140px]">{p.stock_name}</td>
                    <td className="py-2 px-3 text-right">{p.pattern_age}</td>
                    <td className="py-2 px-3">{p.setup_status}</td>
                    <td className="py-2 px-3 text-right">{p.entry_level.toFixed(2)}</td>
                    <td className="py-2 px-3 text-right text-bear">{p.stop_loss.toFixed(2)}</td>
                    <td className="py-2 px-3 text-right text-bull">{p.target_1.toFixed(2)}</td>
                    <td className="py-2 px-3 text-right">{p.target_2.toFixed(2)}</td>
                    <td className="py-2 px-3 text-right">{p.risk_reward_ratio.toFixed(1)}</td>
                    <td className="py-2 px-3 text-muted truncate max-w-[220px]">{p.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
