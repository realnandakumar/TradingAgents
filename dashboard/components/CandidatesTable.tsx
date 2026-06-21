import { RatingBadge, SignalList } from "@/components/Badges";
import { inr, shortSymbol } from "@/lib/format";
import type { Candidate } from "@/lib/types";

export function CandidatesTable({ candidates }: { candidates: Candidate[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-muted text-xs uppercase tracking-wide border-b border-border">
            <th className="text-left font-medium py-2 pr-3">#</th>
            <th className="text-left font-medium py-2 pr-3">Ticker</th>
            <th className="text-right font-medium py-2 pr-3">RS %</th>
            <th className="text-right font-medium py-2 pr-3">Score</th>
            <th className="text-right font-medium py-2 pr-3">Close</th>
            <th className="text-left font-medium py-2 pr-3">Signals</th>
            <th className="text-left font-medium py-2">AI rating</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr key={c.symbol} className="border-b border-border/50 last:border-0">
              <td className="py-2.5 pr-3 text-muted tabular-nums">{c.rank}</td>
              <td className="py-2.5 pr-3 font-medium">
                {shortSymbol(c.symbol)}
                {c.opened && (
                  <span className="ml-2 text-[10px] text-bull border border-bull/30 rounded px-1 py-0.5 align-middle">
                    paper
                  </span>
                )}
              </td>
              <td className="py-2.5 pr-3 text-right tabular-nums">{c.rs_percentile.toFixed(0)}</td>
              <td className="py-2.5 pr-3 text-right tabular-nums">{c.composite.toFixed(2)}</td>
              <td className="py-2.5 pr-3 text-right tabular-nums text-muted">{inr(c.close)}</td>
              <td className="py-2.5 pr-3">
                <SignalList signals={c.signals} />
              </td>
              <td className="py-2.5">
                <RatingBadge rating={c.rating} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
