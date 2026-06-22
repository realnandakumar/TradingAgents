import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Free, no-key quote source (Yahoo Finance, ~15-min delayed for NSE).
// Fetched server-side to avoid browser CORS and to keep the source swappable.
const CHART = "https://query1.finance.yahoo.com/v8/finance/chart";

interface Quote {
  price: number | null;
  prevClose: number | null;
  changePct: number | null;
}

async function fetchOne(symbol: string): Promise<[string, Quote]> {
  try {
    const res = await fetch(`${CHART}/${encodeURIComponent(symbol)}?interval=1d&range=1d`, {
      headers: { "User-Agent": "Mozilla/5.0" },
      cache: "no-store",
    });
    if (!res.ok) return [symbol, { price: null, prevClose: null, changePct: null }];
    const json = await res.json();
    const meta = json?.chart?.result?.[0]?.meta ?? {};
    const price = meta.regularMarketPrice ?? null;
    const prevClose = meta.chartPreviousClose ?? meta.previousClose ?? null;
    const changePct =
      price != null && prevClose ? ((price - prevClose) / prevClose) * 100 : null;
    return [symbol, { price, prevClose, changePct }];
  } catch {
    return [symbol, { price: null, prevClose: null, changePct: null }];
  }
}

export async function GET(req: NextRequest) {
  const raw = req.nextUrl.searchParams.get("symbols") ?? "";
  const symbols = raw.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 50);
  if (symbols.length === 0) return NextResponse.json({});

  const entries = await Promise.all(symbols.map(fetchOne));
  return NextResponse.json(Object.fromEntries(entries));
}
