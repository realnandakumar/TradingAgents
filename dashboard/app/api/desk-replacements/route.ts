import { NextRequest, NextResponse } from "next/server";

import { listPendingReplacements } from "@/lib/desk-replacements-server";
import { REPLACEMENT_DESK_IDS } from "@/lib/desk-replacements-types";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const deskId = req.nextUrl.searchParams.get("deskId")?.trim();
  if (!deskId) {
    return NextResponse.json({ error: "deskId query param required" }, { status: 400 });
  }
  if (!(REPLACEMENT_DESK_IDS as readonly string[]).includes(deskId)) {
    return NextResponse.json({ error: "Unknown desk for replacements" }, { status: 400 });
  }

  const replacements = listPendingReplacements(deskId);
  const processDate =
    deskId === "tech-desk" ? (replacements[0]?.processDate ?? null) : null;

  return NextResponse.json({ deskId, replacements, processDate });
}
