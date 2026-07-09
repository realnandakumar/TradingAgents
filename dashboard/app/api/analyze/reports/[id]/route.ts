import { NextRequest, NextResponse } from "next/server";

import { readReport } from "@/lib/analyze-server";

export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const markdown = readReport(id);
  if (markdown === null) {
    return NextResponse.json({ error: "Report not found" }, { status: 404 });
  }
  return NextResponse.json({ id, markdown });
}
