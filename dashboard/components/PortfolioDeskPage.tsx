import Link from "next/link";
import type { ReactNode } from "react";

import { DeskActionsPanel } from "@/components/DeskActionsPanel";
import { DeskClosedLedger } from "@/components/DeskClosedLedger";

import type { SwingPosition } from "@/lib/swing-types";

export interface PortfolioDeskPageProps {
  deskId: string;
  title: string;
  strategyCode: string;
  bookPath: string;
  updatedAt?: string | null;
  positions: SwingPosition[];
  blotter: ReactNode;
  hasBook: boolean;
  emptyTitle?: string;
  emptyHint?: string;
  chartBadge?: string;
  extraBadges?: string[];
  headerExtra?: ReactNode;
  /** Optional screener/candidates panel shown below desk actions (e.g. Gap Fill). */
  screenerPanel?: ReactNode;
}

export function PortfolioDeskPage({
  deskId,
  title,
  strategyCode,
  bookPath,
  updatedAt,
  positions,
  blotter,
  hasBook,
  emptyTitle,
  emptyHint,
  chartBadge = "1D",
  extraBadges = [],
  headerExtra,
  screenerPanel,
}: PortfolioDeskPageProps) {
  const open = positions.filter((p) => p.status === "open");
  const closed = positions.filter((p) => p.status === "closed");

  return (
    <div className="space-y-0 -mx-4 sm:-mx-6 max-w-none">
      <div className="px-4 sm:px-6 py-3 border-b border-border bg-surface flex flex-wrap items-center gap-4">
        <div>
          <div className="text-sm font-semibold tracking-tight">{title}</div>
          <div className="text-[10px] font-mono text-muted uppercase">{strategyCode}</div>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[10px] font-mono uppercase">
          <span className="px-2 py-0.5 rounded bg-accent/20 text-accent">Paper</span>
          <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">NSE</span>
          <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">{chartBadge}</span>
          {extraBadges.map((b) => (
            <span
              key={b}
              className="px-2 py-0.5 rounded bg-surface-2 border border-border"
            >
              {b}
            </span>
          ))}
        </div>
        <div className="ml-auto text-right text-xs text-muted">
          {updatedAt ? <div>Book updated {updatedAt} IST</div> : null}
          {headerExtra}
          <div className="font-mono text-[10px] truncate max-w-[280px]">{bookPath}</div>
        </div>
      </div>

      <div className="mx-4 sm:mx-6 mt-4" id="desk-commands">
        <DeskActionsPanel deskId={deskId} />
      </div>

      {screenerPanel ? <div className="mx-4 sm:mx-6 mt-4 sm:mt-6">{screenerPanel}</div> : null}

      {!hasBook ? (
        <div className="card m-4 sm:m-6 p-8 text-center">
          <h2 className="font-medium mb-2">{emptyTitle ?? `No ${title} book found`}</h2>
          <p className="text-muted text-sm mb-4 max-w-md mx-auto">
            {emptyHint ??
              "Use the Desk actions panel above to run the daily job, or open Command center for bulk runs."}
          </p>
          <Link
            href="/command-center"
            className="inline-block text-xs text-accent hover:underline mb-3"
          >
            Open Command center
          </Link>
          <p className="text-muted text-xs font-mono">{bookPath}</p>
        </div>
      ) : (
        <>
          <div className="card overflow-hidden mx-4 sm:mx-6 mt-4 sm:mt-6">{blotter}</div>

          {closed.length > 0 && (
            <section className="card mx-4 sm:mx-6 mt-4 p-5">
              <h2 className="text-xs font-medium uppercase tracking-wide text-muted mb-3">
                Closed trades ({closed.length})
              </h2>
              <DeskClosedLedger positions={closed} />
            </section>
          )}

          {open.length === 0 && closed.length === 0 && (
            <p className="text-muted text-sm text-center py-8">No positions in this book yet.</p>
          )}
          {open.length === 0 && closed.length > 0 && (
            <p className="text-muted text-sm text-center py-6">No open positions.</p>
          )}
        </>
      )}
    </div>
  );
}
