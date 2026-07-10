import { GapScreenerBlotter } from "@/components/GapScreenerBlotter";
import { gapScreenerSnapshotPath, readGapScreenerSnapshot } from "@/lib/gap-screener-server";

export const dynamic = "force-dynamic";

export default function GapScreenerPage() {
  const snapshot = readGapScreenerSnapshot();
  const updated = snapshot?.updated_at
    ? new Date(snapshot.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;

  return (
    <div className="space-y-0 -mx-4 sm:-mx-6 max-w-none">
      <div className="px-4 sm:px-6 py-3 border-b border-border bg-surface flex flex-wrap items-center gap-4">
        <div>
          <div className="text-sm font-semibold tracking-tight">NSE Gap Screener</div>
          <div className="text-[10px] font-mono text-muted uppercase">GAP_FILL · PURE SCREENER</div>
        </div>
        <div className="flex gap-1.5 text-[10px] font-mono uppercase">
          <span className="px-2 py-0.5 rounded bg-accent/20 text-accent">Screener</span>
          <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">NSE</span>
          <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">1D</span>
        </div>
        <div className="ml-auto text-right text-xs text-muted">
          {updated ? <div>Snapshot {updated} IST</div> : null}
          {snapshot ? (
            <div>
              {snapshot.total_hits} gap(s) · checked {snapshot.checked} tickers
            </div>
          ) : null}
          <div className="font-mono text-[10px] truncate max-w-[320px]">{gapScreenerSnapshotPath()}</div>
        </div>
      </div>

      {!snapshot ? (
        <div className="card m-4 sm:m-6 p-8 text-center">
          <h2 className="font-medium mb-2">No gap screener snapshot yet</h2>
          <p className="text-muted text-sm mb-4">
            Run <code className="text-accent">python scripts/run_gap_fill_screener_now.py</code> or{" "}
            <code className="text-accent">tradingagents gap-fill</code> to refresh.
          </p>
          <p className="text-muted text-xs font-mono">{gapScreenerSnapshotPath()}</p>
        </div>
      ) : (
        <div className="m-4 sm:m-6">
          <GapScreenerBlotter picks={snapshot.picks} />
        </div>
      )}
    </div>
  );
}
