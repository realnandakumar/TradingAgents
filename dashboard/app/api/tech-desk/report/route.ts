import { NextRequest, NextResponse } from "next/server";

import { readTechReportMarkdown } from "@/lib/tech-reports-server";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const ticker = req.nextUrl.searchParams.get("ticker")?.trim();
  if (!ticker) {
    return NextResponse.json({ error: "ticker query param required" }, { status: 400 });
  }

  const markdown = readTechReportMarkdown(ticker);
  if (markdown == null) {
    return NextResponse.json({ error: "Report not found" }, { status: 404 });
  }

  return NextResponse.json({ ticker: ticker.toUpperCase(), markdown });
}
