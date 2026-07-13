import { NextRequest, NextResponse } from "next/server";

import { loadIntradayChartPayload, normalizeTicker } from "@/lib/chart-server";
import type { ChartTimeframe, IntradayRange } from "@/lib/chart-types";

export const dynamic = "force-dynamic";

const INTERVALS = new Set<ChartTimeframe>(["5m", "15m"]);
const RANGES = new Set<IntradayRange>(["1d", "5d"]);

export async function GET(req: NextRequest) {
  const ticker = req.nextUrl.searchParams.get("ticker")?.trim();
  if (!ticker) {
    return NextResponse.json({ error: "ticker required" }, { status: 400 });
  }

  const intervalRaw = req.nextUrl.searchParams.get("interval") ?? "5m";
  const interval = (INTERVALS.has(intervalRaw as ChartTimeframe)
    ? intervalRaw
    : "5m") as "5m" | "15m";

  const rangeRaw = req.nextUrl.searchParams.get("range") ?? "5d";
  const range = (RANGES.has(rangeRaw as IntradayRange) ? rangeRaw : "5d") as IntradayRange;

  const payload = await loadIntradayChartPayload(normalizeTicker(ticker), interval, range);
  if (payload.bars.length === 0) {
    return NextResponse.json(
      { error: `No intraday OHLCV for ${payload.ticker}`, ticker: payload.ticker },
      { status: 404 },
    );
  }

  return NextResponse.json(payload);
}
