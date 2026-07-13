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
    />
  );
}
