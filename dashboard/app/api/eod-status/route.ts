import fs from "fs";
import { NextResponse } from "next/server";

import {
  countStaleSymbols,
  describeSyncGap,
  expectedCompletedSessionIst,
  maxLastBarFromManifest,
  pricesDbPath,
  readLatestEodReport,
  readManifest,
  todayIst,
} from "@/lib/price-sync-status";

export const dynamic = "force-dynamic";

import { readCustomTickers } from "@/lib/custom-tickers-server";

export async function GET() {
  try {
    const manifest = readManifest();
    const custom = readCustomTickers();
    const today = todayIst();
    const expectedSession = expectedCompletedSessionIst();
    const lastEod = manifest.last_eod_run ?? null;
    const staleCount = countStaleSymbols(manifest);
    const maxLastBar = maxLastBarFromManifest(manifest);
    const latestEod = readLatestEodReport();
    const behind = maxLastBar !== null && maxLastBar < expectedSession;
    const syncWarning = describeSyncGap(maxLastBar, expectedSession, latestEod?.sync);

    return NextResponse.json({
      last_eod_run: lastEod,
      today_ist: today,
      expected_session: expectedSession,
      max_last_bar: maxLastBar,
      prices_behind_today: behind,
      sync_warning: syncWarning,
      last_eod_sync: latestEod?.sync ?? null,
      last_eod_completed_at: latestEod?.completed_at ?? null,
      needs_sync:
        behind ||
        !lastEod ||
        lastEod < expectedSession ||
        staleCount > 0,
      symbol_count: Object.keys(manifest.symbols ?? {}).length,
      stale_symbol_count: staleCount,
      custom_ticker_count: custom.symbols.length,
      prices_db_path: pricesDbPath(),
      prices_db_exists: fs.existsSync(pricesDbPath()),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to read EOD status";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
