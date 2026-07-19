import { NextRequest, NextResponse } from "next/server";

import { readTechDeskReportBundle } from "@/lib/tech-reports-server";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const ticker = req.nextUrl.searchParams.get("ticker")?.trim();
  if (!ticker) {
    return NextResponse.json({ error: "ticker query param required" }, { status: 400 });
  }

  const reportDate = req.nextUrl.searchParams.get("date")?.trim() || null;
  const reportPath = req.nextUrl.searchParams.get("path")?.trim() || null;

  const bundle = readTechDeskReportBundle(ticker, { reportDate, reportPath });
  if (bundle == null) {
    return NextResponse.json(
      {
        error: "Report not found",
        ticker: ticker.toUpperCase(),
        date: reportDate,
      },
      { status: 404 },
    );
  }

  return NextResponse.json(bundle);
}
