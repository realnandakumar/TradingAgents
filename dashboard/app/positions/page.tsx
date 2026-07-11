import { DeskActionsPanel } from "@/components/DeskActionsPanel";
import { SignalList } from "@/components/Badges";
import { OpenPositionsLive } from "@/components/OpenPositionsLive";
import { DeskClosedLedger } from "@/components/DeskClosedLedger";
import { EmptyState } from "@/components/SetupNotice";
import { getLatestPaper } from "@/lib/paper-server";

export const dynamic = "force-dynamic";

export default async function PositionsPage() {
  const paper = getLatestPaper();
  const positions = paper?.data.positions ?? [];
  const open = positions.filter((p) => p.status === "open");
  const closed = positions.filter((p) => p.status === "closed");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Paper positions</h1>
        <p className="text-muted text-sm">
          Simulated trades — no real money. Closed trades are scored on return and alpha vs Nifty.
        </p>
      </div>

      <DeskActionsPanel deskId="positions" />

      {positions.length === 0 ? (
        <EmptyState title="No paper positions yet" hint="Run `tradingagents screen` to open positions here." />
      ) : (
        <>
          <section className="card p-5">
            <h2 className="font-medium mb-3">Open ({open.length})</h2>
            <OpenPositionsLive positions={open} />
          </section>

          <section className="card p-5">
            <h2 className="font-medium mb-3">Closed ({closed.length})</h2>
            {closed.length === 0 ? (
              <p className="text-muted text-sm">No closed trades yet.</p>
            ) : (
              <DeskClosedLedger positions={closed.map((p) => ({ ...p, screen_date: p.entry_date, trading_days_held: p.holding_days_actual }))} />
            )}
          </section>
        </>
      )}
    </div>
  );
}
