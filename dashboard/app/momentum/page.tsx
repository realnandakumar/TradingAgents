import { MomentumBlotter } from "@/components/MomentumBlotter";
import { PortfolioDeskPage } from "@/components/PortfolioDeskPage";
import { momentumBookPath, readMomentumBook } from "@/lib/momentum-server";

export const dynamic = "force-dynamic";

export default function MomentumDeskPage() {
  const book = readMomentumBook();
  const updated = book?.updated_at
    ? new Date(book.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;

  return (
    <PortfolioDeskPage
      deskId="momentum"
      title="NSE Momentum Desk"
      strategyCode="MOMENTUM"
      bookPath={momentumBookPath()}
      updatedAt={updated}
      positions={book?.positions ?? []}
      hasBook={Boolean(book)}
      blotter={<MomentumBlotter positions={book?.positions ?? []} />}
      extraBadges={["T1 Full Exit", "Max 4 / Sector"]}
      headerExtra={
        <div>
          Momentum exits 100% at Target 1. New entries capped at 4 open names per sector (20-day max, SuperTrend stop).
          PB ✓ = HH after EMA pullback (informational, not required for entry).
        </div>
      }
      emptyHint="Use Daily run in Desk actions above, or run all dailies from Command center."
    />
  );
}
