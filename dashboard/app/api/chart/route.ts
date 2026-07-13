import { NextRequest, NextResponse } from "next/server";

import { listChartSymbolOptions, loadChartPayload, normalizeTicker } from "@/lib/chart-server";
import { parseDeskFilter } from "@/lib/chart-overlays";
import type { ChartRange } from "@/lib/chart-types";

export const dynamic = "force-dynamic";

const RANGES = new Set<ChartRange>(["3m", "6m", "1y", "3y", "5y", "max"]);

export async function GET(req: NextRequest) {
  const ticker = req.nextUrl.searchParams.get("ticker")?.trim();
  const list = req.nextUrl.searchParams.get("list");

  if (list === "1") {
    return NextResponse.json({ tickers: listChartSymbolOptions() });
  }

  if (!ticker) {
    return NextResponse.json({ error: "ticker required" }, { status: 400 });
  }

  const rangeRaw = req.nextUrl.searchParams.get("range") ?? "1y";
  const range = (RANGES.has(rangeRaw as ChartRange) ? rangeRaw : "1y") as ChartRange;
  const desksRaw = req.nextUrl.searchParams.get("desks");
  const enabledDesks = parseDeskFilter(desksRaw);

  const payload = await loadChartPayload(normalizeTicker(ticker), range, enabledDesks);
  if (payload.bars.length === 0) {
    return NextResponse.json(
      { error: `No OHLCV data for ${payload.ticker}`, ticker: payload.ticker },
      { status: 404 },
    );
  }

  return NextResponse.json(payload);
}
