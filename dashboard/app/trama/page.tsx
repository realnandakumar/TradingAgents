import { PortfolioDeskPage } from "@/components/PortfolioDeskPage";
import { TramaBlotter } from "@/components/TramaBlotter";
import { readTramaBook, tramaBookPath } from "@/lib/trama-server";

export const dynamic = "force-dynamic";

export default function TramaDeskPage() {
  const book = readTramaBook();
  const updated = book?.updated_at
    ? new Date(book.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;

  return (
    <PortfolioDeskPage
      deskId="trama"
      title="TRAMA Desk"
      strategyCode="TRAMA"
      bookPath={tramaBookPath()}
      updatedAt={updated}
      positions={book?.positions ?? []}
      hasBook={Boolean(book)}
      blotter={<TramaBlotter positions={book?.positions ?? []} />}
      extraBadges={["T1 Full Exit", "Max 4 / Sector", "SELL Closes"]}
      headerExtra={
        <div>
          Opens BUY only. Exits 100% at Target 1, stop, 20-day time, or matching SELL signal.
          New entries capped at 4 open names per sector (sectors from universe metadata).
        </div>
      }
      emptyHint="Use Daily run in Desk actions above, or run all dailies from Command center."
    />
  );
}
