import { OverlapsTable } from "@/components/OverlapsTable";
import { getDeskOverlaps } from "@/lib/overlaps-server";

export const dynamic = "force-dynamic";

export default function OverlapsPage() {
  const summary = getDeskOverlaps(2);
  const { overlapTickers, totalOpenLegs, uniqueTickers, triplePlus } = summary;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Desk overlaps</h1>
        <p className="text-muted text-sm mt-1">
          Tickers with an <strong className="font-medium text-foreground">open</strong> position on
          two or more portfolio desks. Per-desk <span className="font-mono text-[11px]">SL · Entry · T1</span>{" "}
          with a shared <span className="font-mono text-[11px]">Live</span> quote per symbol.
        </p>
      </div>

      <div className="grid sm:grid-cols-3 gap-3">
        <div className="card p-4">
          <div className="text-[10px] uppercase text-muted tracking-wide">Overlapping tickers</div>
          <div className="text-2xl font-semibold tabular-nums mt-1">{overlapTickers.length}</div>
          <div className="text-xs text-muted mt-1">
            {triplePlus > 0 ? `${triplePlus} on 3+ desks` : "none on 3+ desks"}
          </div>
        </div>
        <div className="card p-4">
          <div className="text-[10px] uppercase text-muted tracking-wide">Unique open tickers</div>
          <div className="text-2xl font-semibold tabular-nums mt-1">{uniqueTickers}</div>
          <div className="text-xs text-muted mt-1">across all desks</div>
        </div>
        <div className="card p-4">
          <div className="text-[10px] uppercase text-muted tracking-wide">Open legs</div>
          <div className="text-2xl font-semibold tabular-nums mt-1">{totalOpenLegs}</div>
          <div className="text-xs text-muted mt-1">position slots (may double-count overlaps)</div>
        </div>
      </div>

      <OverlapsTable summary={summary} />

      <p className="text-muted text-xs max-w-2xl">
        Cush% = distance from live to stop. Rows highlighted when cushion &lt; 7%. Pending zones not
        included.
      </p>
    </div>
  );
}
