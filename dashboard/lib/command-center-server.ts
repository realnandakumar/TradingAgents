import { listPortfolioDesks } from "@/lib/desk-cli-config";
import { readGapFillBook } from "@/lib/gap-fill-server";
import { readMomentumBook } from "@/lib/momentum-server";
import { readNssBook } from "@/lib/nss-server";
import { readNwEnvelopeBook } from "@/lib/nw-envelope-server";
import { readPatternForecastBook } from "@/lib/pattern-forecast-server";
import { readStrsiBook } from "@/lib/supertrend-rsi-server";
import { readSwingBook } from "@/lib/swing-server";
import { readTechDeskBook } from "@/lib/tech-desk-server";
import { readRsDeskBook } from "@/lib/rs-desk-server";
import { readTramaBook } from "@/lib/trama-server";
import type { SwingBook } from "@/lib/swing-types";

type BookReader = () => { positions: { status: string }[] } | null;

const BOOK_READERS: Record<string, BookReader> = {
  swing: readSwingBook as BookReader,
  momentum: readMomentumBook as BookReader,
  nss: readNssBook as BookReader,
  "supertrend-rsi": readStrsiBook as BookReader,
  trama: readTramaBook as BookReader,
  "gap-fill": readGapFillBook as BookReader,
  "nw-envelope": readNwEnvelopeBook as BookReader,
  "pattern-forecast": readPatternForecastBook as BookReader,
  positions: readRsDeskBook as BookReader,
  "tech-desk": readTechDeskBook as BookReader,
};

export interface PortfolioDeskSummary {
  id: string;
  label: string;
  href: string;
  openCount: number | null;
}

export function getPortfolioDeskSummaries(): PortfolioDeskSummary[] {
  return listPortfolioDesks().map((desk) => {
    const book = BOOK_READERS[desk.id]?.() as SwingBook | null;
    return {
      id: desk.id,
      label: desk.label,
      href: `/${desk.id}`,
      openCount: book
        ? book.positions.filter((p) => p.status === "open").length
        : null,
    };
  });
}
