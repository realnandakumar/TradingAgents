import { NextRequest, NextResponse } from "next/server";

import {
  addToWatchlist,
  readWatchlist,
  removeFromWatchlist,
  saveWatchlist,
} from "@/lib/watchlist-server";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const { symbols, path: filePath } = readWatchlist();
    return NextResponse.json({ symbols, path: filePath });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to read watchlist";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

/** Replace the full watchlist. Body: { symbols: string[] } */
export async function PUT(req: NextRequest) {
  try {
    const body = (await req.json()) as { symbols?: string[] };
    if (!Array.isArray(body.symbols)) {
      return NextResponse.json({ error: "symbols array is required" }, { status: 400 });
    }
    const result = saveWatchlist(body.symbols);
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to save watchlist";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

/** Add or remove tickers. Body: { add?: string[], remove?: string[] } */
export async function PATCH(req: NextRequest) {
  try {
    const body = (await req.json()) as { add?: string[]; remove?: string[] };
    const hasAdd = Array.isArray(body.add) && body.add.length > 0;
    const hasRemove = Array.isArray(body.remove) && body.remove.length > 0;
    if (!hasAdd && !hasRemove) {
      return NextResponse.json(
        { error: "Provide add and/or remove symbol arrays" },
        { status: 400 },
      );
    }

    let result = readWatchlist();
    if (hasRemove) result = removeFromWatchlist(body.remove!);
    if (hasAdd) result = addToWatchlist(body.add!);
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to update watchlist";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
