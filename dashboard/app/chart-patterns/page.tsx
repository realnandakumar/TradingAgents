import { ChartPatternsBlotter } from "@/components/ChartPatternsBlotter";
import {
  chartPatternScreenerSnapshotPath,
  readChartPatternScreenerSnapshot,
} from "@/lib/chart-patterns-server";

export const dynamic = "force-dynamic";

export default function ChartPatternsScreenerPage() {
  const snapshot = readChartPatternScreenerSnapshot();
  const updated = snapshot?.updated_at
    ? new Date(snapshot.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;
  const rowCount = snapshot?.groups.reduce((n, g) => n + g.picks.length, 0) ?? 0;

  return (
    <div className="space-y-0 -mx-4 sm:-mx-6 max-w-none">
      <div className="px-4 sm:px-6 py-3 border-b border-border bg-surface flex flex-wrap items-center gap-4">
        <div>
          <div className="text-sm font-semibold tracking-tight">NSE Chart Patterns</div>
          <div className="text-[10px] font-mono text-muted uppercase">CHART_PATTERNS · PURE SCREENER</div>
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
              {rowCount} row(s) · {snapshot.group_count} pattern table(s) · checked {snapshot.checked}
            </div>
          ) : null}
          <div className="font-mono text-[10px] truncate max-w-[320px]">
            {chartPatternScreenerSnapshotPath()}
          </div>
        </div>
      </div>

      {!snapshot ? (
        <div className="card m-4 sm:m-6 p-8 text-center">
          <h2 className="font-medium mb-2">No chart patterns snapshot yet</h2>
          <p className="text-muted text-sm mb-4">
            Run <code className="text-accent">python scripts/run_chart_patterns_screener_now.py</code> or{" "}
            <code className="text-accent">tradingagents chart-patterns</code> to refresh.
          </p>
          <p className="text-muted text-xs font-mono">{chartPatternScreenerSnapshotPath()}</p>
        </div>
      ) : (
        <div className="m-4 sm:m-6">
          <ChartPatternsBlotter groups={snapshot.groups} />
        </div>
      )}
    </div>
  );
}
