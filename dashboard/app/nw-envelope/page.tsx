import { DeskActionsPanel } from "@/components/DeskActionsPanel";
import { NwEnvelopeBlotter } from "@/components/NwEnvelopeBlotter";
import { DeskClosedLedger } from "@/components/DeskClosedLedger";
import { readNwEnvelopeBook, nwEnvelopeBookPath } from "@/lib/nw-envelope-server";

export const dynamic = "force-dynamic";

export default function NwEnvelopeDeskPage() {
  const book = readNwEnvelopeBook();
  const open = book?.positions.filter((p) => p.status === "open") ?? [];
  const closed = book?.positions.filter((p) => p.status === "closed") ?? [];
  const updated = book?.updated_at
    ? new Date(book.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;

  return (
    <div className="space-y-0 -mx-4 sm:-mx-6 max-w-none">
      <div className="px-4 sm:px-6 py-3 border-b border-border bg-surface flex flex-wrap items-center gap-4">
        <div>
          <div className="text-sm font-semibold tracking-tight">NSE NW Envelope Desk</div>
          <div className="text-[10px] font-mono text-muted uppercase">NW_ENVELOPE</div>
        </div>
        <div className="flex gap-1.5 text-[10px] font-mono uppercase">
          <span className="px-2 py-0.5 rounded bg-accent/20 text-accent">Paper</span>
          <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">NSE</span>
          <span className="px-2 py-0.5 rounded bg-surface-2 border border-border">1D</span>
        </div>
        <div className="ml-auto text-right text-xs text-muted">
          {updated ? <div>Book updated {updated} IST</div> : null}
          <div className="font-mono text-[10px] truncate max-w-[280px]">{nwEnvelopeBookPath()}</div>
        </div>
      </div>

      <div className="mx-4 sm:mx-6 mt-4">
        <DeskActionsPanel deskId="nw-envelope" />
      </div>

      {!book ? (
        <div className="card m-4 sm:m-6 p-8 text-center">
          <h2 className="font-medium mb-2">No NW Envelope book found</h2>
          <p className="text-muted text-sm mb-4">
            Run <code className="text-accent">tradingagents nw-envelope-daily</code> to open positions.
          </p>
          <p className="text-muted text-xs font-mono">{nwEnvelopeBookPath()}</p>
        </div>
      ) : (
        <>
          <div className="card overflow-hidden mx-4 sm:mx-6 mt-4 sm:mt-6">
            <NwEnvelopeBlotter positions={book.positions} />
          </div>

          {closed.length > 0 && (
            <section className="card mx-4 sm:mx-6 mt-4 p-5">
              <h2 className="text-xs font-medium uppercase tracking-wide text-muted mb-3">
                Closed trades ({closed.length})
              </h2>
              <DeskClosedLedger positions={closed} />
            </section>
          )}

          {open.length === 0 && (
            <p className="text-muted text-sm text-center py-8">No open NW Envelope positions.</p>
          )}
        </>
      )}
    </div>
  );
}
