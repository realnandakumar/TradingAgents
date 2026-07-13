import { SwingBlotter } from "@/components/SwingBlotter";
import { PortfolioDeskPage } from "@/components/PortfolioDeskPage";
import { readSwingBook, swingBookPath } from "@/lib/swing-server";

export const dynamic = "force-dynamic";

export default function SwingDeskPage() {
  const book = readSwingBook();
  const updated = book?.updated_at
    ? new Date(book.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;

  return (
    <PortfolioDeskPage
      deskId="swing"
      title="NSE Swing Desk"
      strategyCode="SWING_TRADE_POSITIONAL"
      bookPath={swingBookPath()}
      updatedAt={updated}
      positions={book?.positions ?? []}
      hasBook={Boolean(book)}
      blotter={<SwingBlotter positions={book?.positions ?? []} />}
      emptyHint="Use Daily run in Desk actions above, or run all dailies from Command center."
    />
  );
}
