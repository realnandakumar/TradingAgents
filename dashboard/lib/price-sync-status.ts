import fs from "fs";
import os from "os";
import path from "path";

const TRADINGAGENTS_HOME =
  process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");

export interface EodSyncStep {
  synced?: number;
  skipped?: number | boolean;
  failed?: number;
  errors?: string[];
  reason?: string;
}

export interface LatestEodReport {
  path: string;
  started_at?: string;
  completed_at?: string;
  last_eod_run?: string;
  sync?: EodSyncStep;
}

export function todayIst(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
}

export function expectedCompletedSessionIst(now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hourCycle: "h23",
  }).formatToParts(now);
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  const istDate = new Date(Date.UTC(get("year"), get("month") - 1, get("day")));
  if (get("hour") < 16) istDate.setUTCDate(istDate.getUTCDate() - 1);
  while (istDate.getUTCDay() === 0 || istDate.getUTCDay() === 6) {
    istDate.setUTCDate(istDate.getUTCDate() - 1);
  }
  return istDate.toISOString().slice(0, 10);
}

export function tradingagentsHome(): string {
  return TRADINGAGENTS_HOME;
}

export function cacheDir(): string {
  return process.env.TRADINGAGENTS_CACHE_DIR ?? path.join(TRADINGAGENTS_HOME, "cache");
}

export function pricesDbPath(): string {
  return (
    process.env.TRADINGAGENTS_PRICES_DB_PATH ??
    path.join(TRADINGAGENTS_HOME, "prices.db")
  );
}

export function logsDir(): string {
  return process.env.TRADINGAGENTS_RESULTS_DIR ?? path.join(TRADINGAGENTS_HOME, "logs");
}

export function readManifest(): {
  last_eod_run?: string;
  symbols?: Record<string, { last_bar?: string }>;
} {
  const manifestPath = path.join(cacheDir(), "manifest.json");
  if (!fs.existsSync(manifestPath)) return {};
  try {
    return JSON.parse(fs.readFileSync(manifestPath, "utf-8")) as {
      last_eod_run?: string;
      symbols?: Record<string, { last_bar?: string }>;
    };
  } catch {
    return {};
  }
}

export function maxLastBarFromManifest(
  manifest: { symbols?: Record<string, { last_bar?: string }> },
): string | null {
  let max: string | null = null;
  for (const entry of Object.values(manifest.symbols ?? {})) {
    const lb = entry?.last_bar;
    if (lb && (!max || lb > max)) max = lb;
  }
  return max;
}

export function countStaleSymbols(
  manifest: { symbols?: Record<string, { last_bar?: string }> },
  staleDays = 2,
): number {
  const cutoff = new Date(`${todayIst()}T00:00:00Z`);
  cutoff.setDate(cutoff.getDate() - staleDays);
  const cut = cutoff.toISOString().slice(0, 10);
  let stale = 0;
  for (const entry of Object.values(manifest.symbols ?? {})) {
    const last = entry?.last_bar;
    if (!last || last < cut) stale += 1;
  }
  return stale;
}

export function readLatestEodReport(): LatestEodReport | null {
  const dir = logsDir();
  if (!fs.existsSync(dir)) return null;
  const files = fs
    .readdirSync(dir)
    .filter((f) => /^eod_\d{8}\.json$/.test(f))
    .sort()
    .reverse();
  if (files.length === 0) return null;
  const filePath = path.join(dir, files[0]!);
  try {
    const raw = JSON.parse(fs.readFileSync(filePath, "utf-8")) as {
      started_at?: string;
      completed_at?: string;
      last_eod_run?: string;
      steps?: { sync?: EodSyncStep };
    };
    return {
      path: filePath,
      started_at: raw.started_at,
      completed_at: raw.completed_at,
      last_eod_run: raw.last_eod_run,
      sync: raw.steps?.sync,
    };
  } catch {
    return null;
  }
}

/** True when the latest stored bar is before the latest completed NSE weekday session. */
export function pricesBehindToday(
  maxLastBar: string | null,
  today = expectedCompletedSessionIst(),
): boolean {
  if (!maxLastBar) return true;
  return maxLastBar < today;
}

export function describeSyncGap(
  maxLastBar: string | null,
  today: string,
  sync?: EodSyncStep | null,
): string | null {
  if (pricesBehindToday(maxLastBar, today)) {
    const skippedAll =
      sync &&
      typeof sync.skipped === "number" &&
      sync.synced === 0 &&
      sync.failed === 0 &&
      sync.skipped > 0;
    if (skippedAll) {
      return `Prices stop at ${maxLastBar}; last EOD synced 0 symbols (all ${sync.skipped} skipped as "fresh"). Use Sync now.`;
    }
    return `Prices stop at ${maxLastBar}; need bars through ${today}.`;
  }
  if (sync && (sync.failed ?? 0) > 0) {
    return `Last sync: ${sync.failed} failed, ${sync.synced ?? 0} synced.`;
  }
  return null;
}
