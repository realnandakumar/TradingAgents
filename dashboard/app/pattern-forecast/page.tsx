import { PatternForecastBlotter } from "@/components/PatternForecastBlotter";
import { patternForecastBookPath, readPatternForecastBook } from "@/lib/pattern-forecast-server";

export const dynamic = "force-dynamic";

export default function PatternForecastDeskPage() {
  const book = readPatternForecastBook();
  const open = book?.positions.filter((p) => p.status === "open") ?? [];
  const closed = book?.positions.filter((p) => p.status === "closed") ?? [];
  const updated = book?.updated_at
    ? new Date(book.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;

  return (
    <div className="space-y-0 -mx-4 sm:-mx-6 max-w-none">
      <div className="px-4 sm:px-6 py-3 border-b border-border bg-surface flex flex-wrap items-center gap-4">
        <div>
          <div className="text-sm font-semibold tracking-tight">NSE Pattern Forecast Desk</div>
          <div className="text-[10px] font-mono text-muted uppercase">PATTERN_FORECAST · 5D</div>
        </div>
        <div className="flex gap-1.5 text-[10px] font-mono uppercase">
          <span className="px-2 py-0.5 rounded bg-accent/20 text-accent">Paper</span>
          <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">NSE</span>
          <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">5D hold</span>
        </div>
        <div className="ml-auto text-right text-xs text-muted">
          {updated ? <div>Book updated {updated} IST</div> : null}
          <div className="font-mono text-[10px] truncate max-w-[280px]">{patternForecastBookPath()}</div>
        </div>
      </div>

      {!book ? (
        <div className="card m-4 sm:m-6 p-8 text-center">
          <h2 className="font-medium mb-2">No Pattern Forecast book found</h2>
          <p className="text-muted text-sm mb-4">
            Run <code className="text-accent">tradingagents pattern-forecast-daily</code> to open positions.
          </p>
          <p className="text-muted text-xs font-mono">{patternForecastBookPath()}</p>
        </div>
      ) : (
        <>
          <div className="card overflow-hidden mx-4 sm:mx-6 mt-4 sm:mt-6">
            <PatternForecastBlotter positions={book.positions} />
          </div>

          {closed.length > 0 && (
            <section className="card mx-4 sm:mx-6 mt-4 p-5">
              <h2 className="text-xs font-medium uppercase tracking-wide text-muted mb-3">
                Closed trades ({closed.length})
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="text-muted uppercase border-b border-border">
                      <th className="text-left py-2 pr-3">SYM</th>
                      <th className="text-right py-2 pr-3">Return</th>
                      <th className="text-left py-2">Exit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closed.map((p) => (
                      <tr key={p.ticker} className="border-b border-border/40">
                        <td className="py-2 pr-3">{p.ticker.replace(".NS", "")}</td>
                        <td className="py-2 pr-3 text-right tabular-nums">
                          {p.raw_return != null ? `${(p.raw_return * 100).toFixed(1)}%` : "—"}
                        </td>
                        <td className="py-2 text-muted">{p.exit_reason ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {open.length === 0 && (
            <p className="text-muted text-sm text-center py-8">No open Pattern Forecast positions.</p>
          )}
        </>
      )}
    </div>
  );
}
