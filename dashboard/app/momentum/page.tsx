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
    />
  );
}
