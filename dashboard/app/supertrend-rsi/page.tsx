import { PortfolioDeskPage } from "@/components/PortfolioDeskPage";
import { SuperTrendRSIBlotter } from "@/components/SuperTrendRSIBlotter";
import { readStrsiBook, strsiBookPath } from "@/lib/supertrend-rsi-server";

export const dynamic = "force-dynamic";

export default function SuperTrendRSIDeskPage() {
  const book = readStrsiBook();
  const updated = book?.updated_at
    ? new Date(book.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;

  return (
    <PortfolioDeskPage
      deskId="supertrend-rsi"
      title="SuperTrend + RSI Desk"
      strategyCode="SUPERTREND_RSI"
      bookPath={strsiBookPath()}
      updatedAt={updated}
      positions={book?.positions ?? []}
      hasBook={Boolean(book)}
      blotter={<SuperTrendRSIBlotter positions={book?.positions ?? []} />}
      extraBadges={["T1 Full Exit", "Max 4 / Sector", "SELL Closes"]}
      headerExtra={
        <div>
          Opens BUY only. Exits 100% at Target 1, stop, 20-day time, or matching SELL signal.
          New entries capped at 4 open names per sector.
        </div>
      }
      emptyHint="Use Daily run in Desk actions above, or run all dailies from Command center."
    />
  );
}
