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
      extraBadges={["5D hold", "Target Full Exit", "Max 4 / Sector", "UP only"]}
      headerExtra={
        <div>
          Opens UP forecasts only. Exits 100% at projected 5d max high, stop, or day-5 time.
          New entries capped at 4 open names per sector. Existing over-cap names exit naturally.
        </div>
      }
      emptyHint="Use Daily run in Desk actions above, or run all dailies from Command center."
    />
  );
}
