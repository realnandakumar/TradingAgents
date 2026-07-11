import { NextRequest, NextResponse } from "next/server";

import { getTechDeskStatus } from "@/lib/tech-desk-status-server";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    return NextResponse.json(getTechDeskStatus());
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to load Tech Desk status";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
