import { TechDeskActionsPanel } from "@/components/TechDeskActionsPanel";
import { TechDeskActivityPanel } from "@/components/TechDeskActivityPanel";
import { TechDeskClosedHistory } from "@/components/TechDeskClosedHistory";
import { TechDeskPipelineCard } from "@/components/TechDeskPipelineCard";
import { TechWatchlistPanel } from "@/components/TechWatchlistPanel";
import { TechDeskBlotter } from "@/components/TechDeskBlotter";
import {
  computeTechDeskStats,
  readAllClosedTrades,
  readTechDeskBook,
  readTechDeskPending,
  techDeskBookPath,
} from "@/lib/tech-desk-server";

export const dynamic = "force-dynamic";

export default function TechDeskPage() {
  const book = readTechDeskBook();
  const pending = readTechDeskPending();
  const closedHistory = readAllClosedTrades();
  const positions = book?.positions ?? [];
  const open = positions.filter((p) => p.status === "open");
  const stats = computeTechDeskStats(closedHistory);
  const updated = book?.updated_at
    ? new Date(book.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;
  const hasBook = Boolean(book);
  const hasPending = pending.length > 0;
  const showBlotter = hasBook || hasPending;

  return (
    <div className="space-y-0 -mx-4 sm:-mx-6 max-w-none">
      <div className="px-4 sm:px-6 py-3 border-b border-border bg-surface flex flex-wrap items-center gap-4">
        <div>
          <div className="text-sm font-semibold tracking-tight">Tech Desk</div>
          <div className="text-[10px] font-mono text-muted uppercase">
            TECH_DESK · Trader + script · shared tech_reports
          </div>
        </div>
        <div className="flex gap-1.5 text-[10px] font-mono uppercase">
          <span className="px-2 py-0.5 rounded bg-accent/20 text-accent">Paper</span>
          <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">NSE</span>
          <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">20 slots</span>
        </div>
        <div className="ml-auto text-right text-xs text-muted">
          {updated ? <div>Book updated {updated} IST</div> : null}
          {stats.trades > 0 ? (
            <div>
              Win {stats.winRate?.toFixed(0)}% · avg R {stats.avgR?.toFixed(2) ?? "—"} · P&L{" "}
              {stats.totalPnl.toLocaleString("en-IN", {
                style: "currency",
                currency: "INR",
                maximumFractionDigits: 0,
              })}
            </div>
          ) : null}
          <div className="font-mono text-[10px] truncate max-w-[280px]">{techDeskBookPath()}</div>
        </div>
      </div>

      <div className="mx-4 sm:mx-6 mt-4 space-y-4">
        <TechDeskPipelineCard />
        <TechWatchlistPanel />
        <TechDeskActionsPanel />
        <TechDeskActivityPanel />
      </div>

      {!showBlotter ? (
        <div className="card m-4 sm:m-6 p-8 text-center">
          <h2 className="font-medium mb-2">No Tech Desk book yet</h2>
          <p className="text-muted text-sm mb-4 max-w-md mx-auto">
            Use the watchlist above, run <strong>Analyze entire watchlist</strong>, then{" "}
            <strong>Process zones</strong>. Run <strong>Daily run</strong> each day.
          </p>
          <p className="text-muted text-xs font-mono">{techDeskBookPath()}</p>
        </div>
      ) : (
        <>
          <div className="card overflow-hidden mx-4 sm:mx-6 mt-4 sm:mt-6">
            <TechDeskBlotter positions={positions} pending={pending} maxPositions={20} />
          </div>

          {open.length === 0 && !hasPending && hasBook && (
            <p className="text-muted text-sm text-center py-8">
              No open Tech Desk positions or pending zones.
            </p>
          )}
        </>
      )}

      <TechDeskClosedHistory trades={closedHistory} />
    </div>
  );
}
