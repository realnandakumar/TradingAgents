import { GapFillBlotter } from "@/components/GapFillBlotter";
import { GapScreenerBlotter } from "@/components/GapScreenerBlotter";
import { PortfolioDeskPage } from "@/components/PortfolioDeskPage";
import { gapFillBookPath, readGapFillBook, type GapFillPosition } from "@/lib/gap-fill-server";
import { gapScreenerSnapshotPath, readGapScreenerSnapshot } from "@/lib/gap-screener-server";

export const dynamic = "force-dynamic";

export default function GapFillDeskPage() {
  const book = readGapFillBook();
  const snapshot = readGapScreenerSnapshot();
  const maxFillPct =
    typeof snapshot?.filters?.max_fill_pct === "number" ? snapshot.filters.max_fill_pct : 50;
  const openPositions = (book?.positions ?? []).filter(
    (p) => p.status === "open",
  ) as GapFillPosition[];
  const openTickers = openPositions.map((p) => p.ticker);
  const screenerTickers = (snapshot?.picks ?? []).map((p) => p.symbol);
  const screenerSet = new Set(screenerTickers);
  const openSet = new Set(openTickers);
  const overlap = openTickers.filter((t) => screenerSet.has(t)).length;
  const openPastFill = openPositions.filter(
    (p) => (p.fill_pct ?? 0) > maxFillPct,
  ).length;
  const openNotInScreener = openPositions.filter((p) => !screenerSet.has(p.ticker)).length;
  const newLongCandidates = (snapshot?.picks ?? []).filter(
    (p) => p.direction === "DOWN" && !openSet.has(p.symbol) && p.fill_pct <= maxFillPct,
  ).length;
  const updated = book?.updated_at
    ? new Date(book.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;
  const snapshotUpdated = snapshot?.updated_at
    ? new Date(snapshot.updated_at).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })
    : null;

  return (
    <PortfolioDeskPage
      deskId="gap-fill"
      title="NSE Gap Fill Desk"
      strategyCode="GAP_FILL"
      bookPath={gapFillBookPath()}
      updatedAt={updated}
      positions={book?.positions ?? []}
      hasBook={Boolean(book)}
      blotter={
        <GapFillBlotter
          positions={book?.positions ?? []}
          screenerTickers={screenerTickers}
          maxFillPct={maxFillPct}
        />
      }
      extraBadges={["≤50% fill"]}
      emptyHint="Run screener then daily from Desk actions. Only gaps not yet more than 50% closed are traded."
      headerExtra={
        snapshot ? (
          <div>
            Screener {snapshotUpdated} IST · {snapshot.total_hits} candidate
            {snapshot.total_hits === 1 ? "" : "s"}
          </div>
        ) : null
      }
      screenerPanel={
        <section className="card p-5 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xs font-medium uppercase tracking-wide text-muted">
                Screener candidates
              </h2>
              <p className="text-muted text-sm mt-1">
                Entry band: gap fill progress {10}–{maxFillPct}% (gap down = long). Daily opens{" "}
                <strong>gap-down</strong> names not already in the book; skips if portfolio is full.
              </p>
              {snapshot && openPositions.length > 0 ? (
                <p className="text-muted text-xs mt-2 font-mono">
                  {overlap} in book + screener · {openNotInScreener} open not in screener ·{" "}
                  {openPastFill} open past {maxFillPct}% fill · {newLongCandidates} new long
                  candidate{newLongCandidates === 1 ? "" : "s"}
                </p>
              ) : null}
            </div>
            {snapshot ? (
              <div className="text-right text-xs text-muted font-mono">
                <div>
                  {snapshot.total_hits} gap(s) · checked {snapshot.checked} tickers
                </div>
                <div className="truncate max-w-[280px]">{gapScreenerSnapshotPath()}</div>
              </div>
            ) : null}
          </div>
          {!snapshot ? (
            <p className="text-muted text-sm text-center py-6">
              No screener snapshot yet. Run screener from Desk actions above.
            </p>
          ) : (
            <GapScreenerBlotter
              picks={snapshot.picks}
              openTickers={openTickers}
              maxFillPct={maxFillPct}
            />
          )}
        </section>
      }
    />
  );
}
