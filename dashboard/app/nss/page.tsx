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
    />
  );
}
