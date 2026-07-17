import { NwEnvelopeBlotter } from "@/components/NwEnvelopeBlotter";
import { PortfolioDeskPage } from "@/components/PortfolioDeskPage";
import { nwEnvelopeBookPath, readNwEnvelopeBook } from "@/lib/nw-envelope-server";

export const dynamic = "force-dynamic";

export default function NwEnvelopeDeskPage() {
  const book = readNwEnvelopeBook();
  const updated = book?.updated_at
    ? new Date(book.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;

  return (
    <PortfolioDeskPage
      deskId="nw-envelope"
      title="NW Envelope Desk"
      strategyCode="NW_ENVELOPE"
      bookPath={nwEnvelopeBookPath()}
      updatedAt={updated}
      positions={book?.positions ?? []}
      hasBook={Boolean(book)}
      blotter={<NwEnvelopeBlotter positions={book?.positions ?? []} />}
      extraBadges={["T1 Full Exit", "Max 4 / Sector", "SELL Closes"]}
      headerExtra={
        <div>
          Opens BUY only (close below lower band). Exits 100% at Target 1, stop, 20-day time, or
          matching SELL signal (close above upper). New entries capped at 4 open names per sector.
        </div>
      }
      emptyHint="Use Daily run in Desk actions above, or run all dailies from Command center."
    />
  );
}
