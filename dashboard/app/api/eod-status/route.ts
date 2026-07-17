import fs from "fs";
import { NextResponse } from "next/server";

import { listRecentJobsForDesk } from "@/lib/desk-cli-server";
import { readCustomTickers } from "@/lib/custom-tickers-server";
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

function latestSyncJobFailure(): {
  job_id: string;
  error: string;
  completed_at: string | null;
} | null {
  const jobs = listRecentJobsForDesk("control-center", 20);
  for (const job of jobs) {
    if (job.action_id !== "eod-sync-now" && job.action_id !== "eod-pipeline") {
      continue;
    }
    if (job.status !== "failed") continue;
    const err = job.error?.trim();
    if (!err) continue;
    return {
      job_id: job.job_id,
      error: err,
      completed_at: job.completed_at ?? null,
    };
  }
  return null;
}

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
    const lastFailedSync = latestSyncJobFailure();

    return NextResponse.json({
      last_eod_run: lastEod,
      today_ist: today,
      expected_session: expectedSession,
      max_last_bar: maxLastBar,
      prices_behind_today: behind,
      sync_warning: syncWarning,
      last_eod_sync: latestEod?.sync ?? null,
      last_eod_completed_at: latestEod?.completed_at ?? null,
      last_failed_sync: lastFailedSync,
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
