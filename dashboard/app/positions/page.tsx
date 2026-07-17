import { DeskActionsPanel } from "@/components/DeskActionsPanel";
import { OpenPositionsLive } from "@/components/OpenPositionsLive";
import { TechDeskBlotter } from "@/components/TechDeskBlotter";
import { TechDeskClosedHistory } from "@/components/TechDeskClosedHistory";
import { getLatestPaper, paperSnapshotPath } from "@/lib/paper-server";
import {
  computeRsDeskStats,
  readAllRsDeskClosedTrades,
  readRsDeskBook,
  readRsDeskPending,
  rsDeskBookPath,
} from "@/lib/rs-desk-server";

export const dynamic = "force-dynamic";

export default function RsDeskPositionsPage() {
  const book = readRsDeskBook();
  const pending = readRsDeskPending();
  const closedHistory = readAllRsDeskClosedTrades();
  const positions = book?.positions ?? [];
  const stats = computeRsDeskStats(closedHistory);
  const legacyPaper = getLatestPaper();
  const legacyOpen = (legacyPaper?.data.positions ?? []).filter((p) => p.status === "open");
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
          <div className="text-sm font-semibold tracking-tight">RS Desk</div>
          <div className="text-[10px] font-mono text-muted uppercase">
            RS_SCREEN · MA → PM · own book
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
          <div className="font-mono text-[10px] truncate max-w-[280px]">{rsDeskBookPath()}</div>
        </div>
      </div>

      <div className="mx-4 sm:mx-6 mt-4 space-y-4">
        <p className="text-muted text-sm">
          Screening via RS + patterns → Market Analyst on top 10 → same PM / zone / exit rules as{" "}
          <a href="/tech-desk" className="text-accent hover:underline">
            Tech Desk
          </a>
          , separate capital book. Reports share{" "}
          <code className="text-[11px]">tech_reports/</code> (latest wins).
        </p>
        <DeskActionsPanel deskId="positions" />
      </div>

      {!showBlotter ? (
        <div className="card m-4 sm:m-6 p-8 text-center">
          <h2 className="font-medium mb-2">No RS Desk book yet</h2>
          <p className="text-muted text-sm mb-4 max-w-md mx-auto">
            Run <strong>Screen + MA + PM</strong> from Desk actions, or Process zones after a
            screen. Daily run handles stops / targets / zone fills.
          </p>
          <p className="text-muted text-xs font-mono">{rsDeskBookPath()}</p>
        </div>
      ) : (
        <>
          <div className="card overflow-hidden mx-4 sm:mx-6 mt-4 sm:mt-6">
            <TechDeskBlotter
              positions={positions}
              pending={pending}
              maxPositions={20}
              deskId="positions"
            />
          </div>

          {closedHistory.length > 0 ? (
            <div className="mx-4 sm:mx-6 mt-4 mb-6">
              <TechDeskClosedHistory trades={closedHistory} deskLabel="RS Desk" />
            </div>
          ) : null}
        </>
      )}

      {legacyOpen.length > 0 ? (
        <section className="card mx-4 sm:mx-6 mt-4 mb-6 p-5 space-y-3">
          <div>
            <h2 className="text-sm font-medium">Legacy RS paper book</h2>
            <p className="text-xs text-muted mt-0.5">
              Older relative-strength paper positions still open in{" "}
              <code className="font-mono text-[11px]">{paperSnapshotPath()}</code>. New RS Desk
              trades live in the blotter above.
            </p>
          </div>
          <OpenPositionsLive positions={legacyOpen} />
        </section>
      ) : null}
    </div>
  );
}
