import { NextResponse } from "next/server";

import { listReports } from "@/lib/analyze-server";

export const dynamic = "force-dynamic";

export async function GET() {
  const reports = listReports();
  return NextResponse.json({ reports });
}
