import { NssBlotter } from "@/components/NssBlotter";
import { PortfolioDeskPage } from "@/components/PortfolioDeskPage";
import { nssBookPath, readNssBook } from "@/lib/nss-server";

export const dynamic = "force-dynamic";

export default function NssDeskPage() {
  const book = readNssBook();
  const updated = book?.updated_at
    ? new Date(book.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;

  return (
    <PortfolioDeskPage
      deskId="nss"
      title="NSE NSS Desk"
      strategyCode="NSS"
      bookPath={nssBookPath()}
      updatedAt={updated}
      positions={book?.positions ?? []}
      hasBook={Boolean(book)}
      blotter={<NssBlotter positions={book?.positions ?? []} />}
      extraBadges={["T1 Full Exit", "Max 4 / Sector"]}
      headerExtra={
        <div>
          NSS exits 100% at Target 1. New entries capped at 4 open names per sector (40-day max, SuperTrend stop).
          BO/VOL ✓ = breakout and volume reference met (informational, not required for entry).
        </div>
      }
      emptyHint="Use Daily run in Desk actions above, or run all dailies from Command center."
    />
  );
}
