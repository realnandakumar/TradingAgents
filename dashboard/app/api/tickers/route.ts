import { NextResponse } from "next/server";

import { getTickerUniverse } from "@/lib/analyze-server";

export const dynamic = "force-dynamic";

export async function GET() {
  const tickers = getTickerUniverse();
  return NextResponse.json({ tickers });
}
