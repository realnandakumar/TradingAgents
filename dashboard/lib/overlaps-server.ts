/** Cross-desk open position overlap detection. */

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
import { normalizeChartTicker } from "@/lib/chart-overlays";
import type { SwingBook, SwingPosition } from "@/lib/swing-types";
import type { TechDeskPosition } from "@/lib/tech-desk-server";

type OpenPosition = SwingPosition | TechDeskPosition;

type BookReader = () => SwingBook | { positions: OpenPosition[] } | null;

const BOOK_READERS: Record<string, BookReader> = {
  swing: readSwingBook,
  momentum: readMomentumBook,
  nss: readNssBook,
  "supertrend-rsi": readStrsiBook,
  trama: readTramaBook,
  "gap-fill": readGapFillBook,
  "nw-envelope": readNwEnvelopeBook,
  "pattern-forecast": readPatternForecastBook,
  positions: readRsDeskBook,
  "tech-desk": readTechDeskBook,
};

export interface DeskOpenLeg {
  deskId: string;
  deskLabel: string;
  href: string;
  entryPrice: number | null;
  screenDate: string | null;
  sector: string | null;
  stopLoss: number | null;
  target1: number | null;
}

export interface TickerOverlap {
  ticker: string;
  deskCount: number;
  desks: DeskOpenLeg[];
}

export interface OverlapSummary {
  totalOpenLegs: number;
  uniqueTickers: number;
  overlapTickers: TickerOverlap[];
  triplePlus: number;
}

function entryDate(p: OpenPosition): string | null {
  const raw = (p as SwingPosition).screen_date ?? (p as { entry_date?: string }).entry_date;
  return raw ?? null;
}

function sectorOf(p: OpenPosition): string | null {
  const s = (p as SwingPosition).sector;
  return s && s !== "—" ? s : null;
}

function numericLevel(p: OpenPosition, ...keys: string[]): number | null {
  const row = p as unknown as Record<string, unknown>;
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

export function getDeskOverlaps(minDesks = 2): OverlapSummary {
  const desks = listPortfolioDesks();
  const byTicker = new Map<string, DeskOpenLeg[]>();
  let totalOpenLegs = 0;

  for (const desk of desks) {
    const book = BOOK_READERS[desk.id]?.();
    if (!book?.positions) continue;

    for (const p of book.positions) {
      if (p.status !== "open" || !p.ticker) continue;
      const norm = normalizeChartTicker(p.ticker);
      if (!norm) continue;

      totalOpenLegs += 1;
      const leg: DeskOpenLeg = {
        deskId: desk.id,
        deskLabel: desk.label,
        href: desk.id === "tech-desk" ? "/tech-desk" : `/${desk.id}`,
        entryPrice: typeof p.entry_price === "number" ? p.entry_price : null,
        screenDate: entryDate(p),
        sector: sectorOf(p),
        stopLoss: numericLevel(p, "trailing_stop", "stop_loss"),
        target1: numericLevel(p, "target_1", "target_max", "fill_target"),
      };

      const existing = byTicker.get(norm) ?? [];
      if (!existing.some((e) => e.deskId === desk.id)) {
        existing.push(leg);
        byTicker.set(norm, existing);
      }
    }
  }

  const overlapTickers: TickerOverlap[] = [];
  for (const [ticker, legs] of byTicker) {
    if (legs.length >= minDesks) {
      overlapTickers.push({
        ticker,
        deskCount: legs.length,
        desks: legs.sort((a, b) => a.deskLabel.localeCompare(b.deskLabel)),
      });
    }
  }

  overlapTickers.sort((a, b) => {
    if (b.deskCount !== a.deskCount) return b.deskCount - a.deskCount;
    return a.ticker.localeCompare(b.ticker);
  });

  return {
    totalOpenLegs,
    uniqueTickers: byTicker.size,
    overlapTickers,
    triplePlus: overlapTickers.filter((o) => o.deskCount >= 3).length,
  };
}
