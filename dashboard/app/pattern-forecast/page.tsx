import { PatternForecastBlotter } from "@/components/PatternForecastBlotter";
import { PortfolioDeskPage } from "@/components/PortfolioDeskPage";
import { patternForecastBookPath, readPatternForecastBook } from "@/lib/pattern-forecast-server";

export const dynamic = "force-dynamic";

export default function PatternForecastDeskPage() {
  const book = readPatternForecastBook();
  const updated = book?.updated_at
    ? new Date(book.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;

  return (
    <PortfolioDeskPage
      deskId="pattern-forecast"
      title="Pattern Forecast Desk"
      strategyCode="PATTERN_FORECAST"
      bookPath={patternForecastBookPath()}
      updatedAt={updated}
      positions={book?.positions ?? []}
      hasBook={Boolean(book)}
      blotter={<PatternForecastBlotter positions={book?.positions ?? []} />}
      extraBadges={["5D hold"]}
    />
  );
}
