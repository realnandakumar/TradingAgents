import { NextRequest, NextResponse } from "next/server";

/** Foreclosure/replacements disabled — always return an empty list. */
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const deskId = req.nextUrl.searchParams.get("deskId")?.trim();
  if (!deskId) {
    return NextResponse.json({ error: "deskId query param required" }, { status: 400 });
  }

  return NextResponse.json({
    deskId,
    replacements: [],
    processDate: null,
    message: "Foreclosure is disabled. Positions exit via stop/target only.",
  });
}
