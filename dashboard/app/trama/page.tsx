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
    />
  );
}
