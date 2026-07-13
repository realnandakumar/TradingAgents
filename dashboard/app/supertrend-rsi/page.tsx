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
    />
  );
}
