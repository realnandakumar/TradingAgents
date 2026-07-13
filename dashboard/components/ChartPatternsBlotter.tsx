"use client";

import { ChartTickerLink } from "@/components/ChartTickerLink";
import { computePatternTradeLevels } from "@/lib/chart-pattern-levels";
import { inr } from "@/lib/format";
import type { ChartPatternScreenerGroup } from "@/lib/chart-patterns-server";

function biasClass(bias: string) {
  if (bias === "BULLISH") return "text-bull";
  if (bias === "BEARISH") return "text-bear";
  return "text-muted";
}

function statusClass(status: string) {
  if (status === "AT_TRIGGER") return "text-bull font-semibold";
  if (status === "APPROACHING") return "text-accent";
  return "text-muted";
}

function rrLabel(rr: number): string {
  return `${rr.toFixed(1)}:1`;
}

export function ChartPatternsBlotter({ groups }: { groups: ChartPatternScreenerGroup[] }) {
  if (!groups.length) {
    return <p className="text-muted text-sm text-center py-8">No chart patterns in snapshot.</p>;
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
                  <th className="text-right py-2 px-3">Dist%</th>
                  <th className="text-right py-2 px-3">Score</th>
                  <th className="text-right py-2 px-3">Close</th>
                  <th className="text-right py-2 px-3">Trigger</th>
                  <th className="text-right py-2 px-3">Stop</th>
                  <th className="text-right py-2 px-3">T1</th>
                  <th className="text-right py-2 px-3">R:R</th>
                </tr>
              </thead>
              <tbody>
                {g.picks.map((p) => {
                  const levels = computePatternTradeLevels(p);
                  return (
                    <tr key={`${p.symbol}-${p.pattern_id}-${p.rank}`} className="border-b border-border/40 last:border-0">
                      <td className="py-2 px-3 text-muted">{p.rank}</td>
                      <td className="py-2 px-3 font-medium">
                        <ChartTickerLink ticker={p.ticker} desk="chart-patterns" className="hover:text-accent" />
                      </td>
                      <td className="py-2 px-3 text-muted max-w-[140px] truncate">{p.stock_name}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{p.pattern_age}d</td>
                      <td className={`py-2 px-3 ${statusClass(p.setup_status)}`}>{p.setup_status}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{p.distance_to_trigger_pct.toFixed(1)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{p.actionability_score.toFixed(0)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{inr(p.close)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{inr(p.trigger_level)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">
                        {levels ? inr(levels.stop) : "—"}
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums">
                        {levels ? inr(levels.t1) : "—"}
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums">
                        {levels ? rrLabel(levels.riskReward) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
