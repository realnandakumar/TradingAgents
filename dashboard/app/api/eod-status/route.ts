import fs from "fs";
import os from "os";
import path from "path";
import { NextResponse } from "next/server";

import { readCustomTickers } from "@/lib/custom-tickers-server";

export const dynamic = "force-dynamic";

const TRADINGAGENTS_HOME =
  process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");

function pricesDbPath(): string {
  return (
    process.env.TRADINGAGENTS_PRICES_DB_PATH ??
    path.join(TRADINGAGENTS_HOME, "prices.db")
  );
}

function cacheDir(): string {
  return process.env.TRADINGAGENTS_CACHE_DIR ?? path.join(TRADINGAGENTS_HOME, "cache");
}

function countStaleSymbols(manifest: { symbols?: Record<string, { last_bar?: string }> }): number {
  const today = new Date();
  const cutoff = new Date(today);
  cutoff.setDate(cutoff.getDate() - 2);
  const cut = cutoff.toISOString().slice(0, 10);
  let stale = 0;
  for (const entry of Object.values(manifest.symbols ?? {})) {
    const last = entry?.last_bar;
    if (!last || last < cut) stale += 1;
  }
  return stale;
}

function todayIst(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
}

export async function GET() {
  try {
    const manifestPath = path.join(cacheDir(), "manifest.json");
    let manifest: {
      last_eod_run?: string;
      symbols?: Record<string, { last_bar?: string }>;
    } = {};
    if (fs.existsSync(manifestPath)) {
      manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8")) as typeof manifest;
    }

    const dbPath = pricesDbPath();
    const custom = readCustomTickers();
    const today = todayIst();
    const lastEod = manifest.last_eod_run ?? null;
    const staleCount = countStaleSymbols(manifest);

    return NextResponse.json({
      last_eod_run: lastEod,
      today_ist: today,
      needs_sync: lastEod !== today || staleCount > 0,
      symbol_count: Object.keys(manifest.symbols ?? {}).length,
      stale_symbol_count: staleCount,
      custom_ticker_count: custom.symbols.length,
      prices_db_path: dbPath,
      prices_db_exists: fs.existsSync(dbPath),
      manifest_path: manifestPath,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to read EOD status";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
