import fs from "fs";
import os from "os";
import path from "path";
import { spawn, spawnSync } from "child_process";

import type {
  ChartBar,
  ChartLineSeries,
  ChartPayload,
  ChartRange,
  ChartTimeframe,
  IntradayRange,
} from "./chart-types";
import {
  collectDeskOverlays,
  mergeDeskOverlays,
  normalizeChartTicker,
} from "./chart-overlays";
import { readWatchlist } from "@/lib/watchlist-server";

const TRADINGAGENTS_HOME =
  process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");

const CHART_ALLOW_YAHOO_FALLBACK =
  (process.env.CHART_ALLOW_YAHOO_FALLBACK ?? "false").toLowerCase() === "true";

const STORE_BAR_CACHE_TTL_MS = 60_000;
const storeBarCache = new Map<string, { expiresAt: number; bars: ChartBar[] }>();
const warmingSymbols = new Map<string, number>();

function repoRootFromDashboard(): string {
  return path.resolve(process.cwd(), "..");
}

function pythonExecutable(): string {
  const repoRoot = repoRootFromDashboard();
  if (process.platform === "win32") {
    const venvPython = path.join(repoRoot, ".venv", "Scripts", "python.exe");
    if (fs.existsSync(venvPython)) return venvPython;
    return "python";
  }
  const venvPython = path.join(repoRoot, ".venv", "bin", "python");
  if (fs.existsSync(venvPython)) return venvPython;
  return "python3";
}

/** Spawn background sync when cache is missing or stale. */
export function ensureSymbolCached(ticker: string): void {
  const now = Date.now();
  const warmingUntil = warmingSymbols.get(ticker) ?? 0;
  if (warmingUntil > now) return;
  warmingSymbols.set(ticker, now + STORE_BAR_CACHE_TTL_MS);
  const cwd = repoRootFromDashboard();
  const pythonCmd = pythonExecutable();
  const child = spawn(pythonCmd, ["scripts/ensure_symbol_cached.py", ticker], {
    cwd,
    detached: true,
    stdio: "ignore",
  });
  child.unref();
}

export function chartCacheDir(): string {
  return process.env.TRADINGAGENTS_CACHE_DIR ?? path.join(TRADINGAGENTS_HOME, "cache");
}

export function normalizeTicker(raw: string): string {
  return normalizeChartTicker(raw);
}

/** Filesystem-safe cache filename for tickers with ``&`` (e.g. M&M.NS → M_M.NS). */
export function symbolCacheFilename(ticker: string): string {
  const sym = ticker.trim().toUpperCase();
  if (!sym || sym.includes("/") || sym.includes("\\") || sym.includes("..")) {
    throw new Error(`invalid ticker: ${ticker}`);
  }
  const safe = sym.replace(/&/g, "_");
  if (!/^[A-Za-z0-9._-]+$/.test(safe)) {
    throw new Error(`invalid ticker for cache filename: ${ticker}`);
  }
  return safe;
}

export function listCachedTickers(): string[] {
  const dir = chartCacheDir();
  if (!fs.existsSync(dir)) return [];

  const manifestPath = path.join(dir, "manifest.json");
  if (fs.existsSync(manifestPath)) {
    try {
      const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf-8")) as {
        symbols?: Record<string, unknown>;
      };
      const keys = Object.keys(manifest.symbols ?? {});
      if (keys.length > 0) return keys.sort();
    } catch {
      /* fall through to directory scan */
    }
  }

  const latest = new Map<string, number>();
  for (const file of fs.readdirSync(dir)) {
    const legacy = file.match(/^(.+)-YFin-data-.+\.csv$/i);
    if (legacy) {
      const ticker = legacy[1].toUpperCase();
      const mtime = fs.statSync(path.join(dir, file)).mtimeMs;
      const prev = latest.get(ticker) ?? 0;
      if (mtime > prev) latest.set(ticker, mtime);
      continue;
    }
    const canonical = file.match(/^(.+)\.csv$/i);
    if (!canonical || canonical[1].toLowerCase() === "manifest") continue;
    const ticker = canonical[1].toUpperCase();
    const mtime = fs.statSync(path.join(dir, file)).mtimeMs;
    const prev = latest.get(ticker) ?? 0;
    if (mtime > prev) latest.set(ticker, mtime);
  }
  return Array.from(latest.keys()).sort();
}

export function listChartSymbolOptions(): string[] {
  const seen = new Set<string>();
  for (const t of listCachedTickers()) seen.add(t);
  try {
    for (const t of readWatchlist().symbols) seen.add(normalizeTicker(t));
  } catch {
    /* ignore */
  }
  return Array.from(seen).sort();
}

function resolveCacheFile(ticker: string): string | null {
  const dir = chartCacheDir();
  if (!fs.existsSync(dir)) return null;

  let canonical: string;
  try {
    canonical = path.join(dir, `${symbolCacheFilename(ticker)}.csv`);
  } catch {
    canonical = path.join(dir, `${ticker}.csv`);
  }
  if (fs.existsSync(canonical)) return canonical;

  const prefix = `${ticker}-YFin-data-`;
  let best: { path: string; mtime: number } | null = null;
  for (const file of fs.readdirSync(dir)) {
    if (!file.startsWith(prefix) || !file.endsWith(".csv")) continue;
    const full = path.join(dir, file);
    const mtime = fs.statSync(full).mtimeMs;
    if (!best || mtime > best.mtime) best = { path: full, mtime };
  }
  return best?.path ?? null;
}

/** SQLite-first read via Python (same path as screeners / backtests). */
function readBarsFromStore(ticker: string): ChartBar[] | null {
  const cached = storeBarCache.get(ticker);
  if (cached && cached.expiresAt > Date.now()) return cached.bars;

  const cwd = repoRootFromDashboard();
  const script = path.join(cwd, "scripts", "chart_bars_json.py");
  if (!fs.existsSync(script)) return null;

  const result = spawnSync(pythonExecutable(), [script, ticker], {
    cwd,
    encoding: "utf-8",
    timeout: 60_000,
    maxBuffer: 32 * 1024 * 1024,
  });
  if (result.status !== 0 || !result.stdout?.trim()) {
    return null;
  }
  try {
    const parsed = JSON.parse(result.stdout) as ChartBar[];
    if (!Array.isArray(parsed)) return null;
    const bars = parsed
      .filter((b) => b?.time && Number.isFinite(b.close))
      .sort((a, b) => barDateKey(a.time).localeCompare(barDateKey(b.time)));
    storeBarCache.set(ticker, {
      expiresAt: Date.now() + STORE_BAR_CACHE_TTL_MS,
      bars,
    });
    return bars;
  } catch {
    return null;
  }
}

function parseCsvBars(filePath: string): ChartBar[] {
  const text = fs.readFileSync(filePath, "utf-8");
  const lines = text.split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];

  const header = lines[0].split(",").map((h) => h.trim().toLowerCase());
  const idx = (name: string) => header.indexOf(name);

  const iDate = idx("date");
  const iOpen = idx("open");
  const iHigh = idx("high");
  const iLow = idx("low");
  const iClose = idx("close");
  const iVol = idx("volume");
  if (iDate < 0 || iClose < 0) return [];

  const bars: ChartBar[] = [];
  for (const line of lines.slice(1)) {
    const cols = line.split(",");
    const time = (cols[iDate] ?? "").slice(0, 10);
    const close = Number(cols[iClose]);
    if (!time || !Number.isFinite(close)) continue;
    bars.push({
      time,
      open: Number(cols[iOpen]) || close,
      high: Number(cols[iHigh]) || close,
      low: Number(cols[iLow]) || close,
      close,
      volume: Number(cols[iVol]) || 0,
    });
  }
  return bars.sort((a, b) => String(a.time).localeCompare(String(b.time)));
}

function barDateKey(time: ChartBar["time"]): string {
  if (typeof time === "number") {
    return new Date(time * 1000).toISOString().slice(0, 10);
  }
  return time.slice(0, 10);
}

/** True when the last cached daily bar is more than ~2 calendar days behind today. */
export function isDailyCacheStale(bars: ChartBar[], today = new Date()): boolean {
  if (bars.length === 0) return false;
  const lastDate = barDateKey(bars[bars.length - 1].time);
  const last = new Date(`${lastDate}T12:00:00Z`);
  const t = new Date(
    Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate(), 12),
  );
  const daysBehind = Math.floor((t.getTime() - last.getTime()) / (24 * 60 * 60 * 1000));
  return daysBehind > 2;
}

/** Append Yahoo bars newer than the cache tail; dedupe by date, sort ascending. */
export function mergeDailyBars(cacheBars: ChartBar[], yahooBars: ChartBar[]): ChartBar[] {
  if (cacheBars.length === 0) return yahooBars;
  if (yahooBars.length === 0) return cacheBars;
  const lastCacheDate = barDateKey(cacheBars[cacheBars.length - 1].time);
  const tail = yahooBars.filter((b) => barDateKey(b.time) > lastCacheDate);
  if (tail.length === 0) return cacheBars;
  const byDate = new Map<string, ChartBar>();
  for (const b of cacheBars) byDate.set(barDateKey(b.time), b);
  for (const b of tail) byDate.set(barDateKey(b.time), b);
  return Array.from(byDate.values()).sort((a, b) =>
    barDateKey(a.time).localeCompare(barDateKey(b.time)),
  );
}

function filterByRange(bars: ChartBar[], range: ChartRange): ChartBar[] {
  if (range === "max" || bars.length === 0) return bars;
  const months: Record<Exclude<ChartRange, "max">, number> = {
    "3m": 3,
    "6m": 6,
    "1y": 12,
    "3y": 36,
    "5y": 60,
  };
  const m = months[range];
  const lastTime = bars[bars.length - 1].time;
  const lastStr = typeof lastTime === "number"
    ? new Date(lastTime * 1000).toISOString().slice(0, 10)
    : lastTime;
  const last = new Date(`${lastStr}T12:00:00Z`);
  const cutoff = new Date(last);
  cutoff.setUTCMonth(cutoff.getUTCMonth() - m);
  const cut = cutoff.toISOString().slice(0, 10);
  return bars.filter((b) => {
    const t = typeof b.time === "number"
      ? new Date(b.time * 1000).toISOString().slice(0, 10)
      : b.time;
    return t >= cut;
  });
}

function computeSma(bars: ChartBar[], period: number): { time: ChartBar["time"]; value: number }[] {
  if (bars.length < period) return [];
  const out: { time: ChartBar["time"]; value: number }[] = [];
  let sum = 0;
  for (let i = 0; i < bars.length; i++) {
    sum += bars[i].close;
    if (i >= period) sum -= bars[i - period].close;
    if (i >= period - 1) {
      out.push({ time: bars[i].time, value: sum / period });
    }
  }
  return out;
}

async function fetchBarsFromYahoo(ticker: string, range: ChartRange): Promise<ChartBar[]> {
  const yahooRange: Record<ChartRange, string> = {
    "3m": "3mo",
    "6m": "6mo",
    "1y": "1y",
    "3y": "3y",
    "5y": "5y",
    max: "max",
  };
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=1d&range=${yahooRange[range]}`;
  const res = await fetch(url, {
    headers: { "User-Agent": "Mozilla/5.0" },
    cache: "no-store",
  });
  if (!res.ok) return [];
  const json = await res.json();
  const result = json?.chart?.result?.[0];
  const timestamps: number[] = result?.timestamp ?? [];
  const q = result?.indicators?.quote?.[0] ?? {};
  const bars: ChartBar[] = [];
  for (let i = 0; i < timestamps.length; i++) {
    const close = q.close?.[i];
    if (close == null || !Number.isFinite(close)) continue;
    const open = q.open?.[i] ?? close;
    const high = q.high?.[i] ?? close;
    const low = q.low?.[i] ?? close;
    const volume = q.volume?.[i] ?? 0;
    bars.push({
      time: new Date(timestamps[i] * 1000).toISOString().slice(0, 10),
      open,
      high,
      low,
      close,
      volume,
    });
  }
  return bars.sort((a, b) => {
    const ta = typeof a.time === "number" ? a.time : a.time;
    const tb = typeof b.time === "number" ? b.time : b.time;
    return ta < tb ? -1 : ta > tb ? 1 : 0;
  });
}

async function fetchIntradayFromYahoo(
  ticker: string,
  interval: "5m" | "15m",
  range: IntradayRange,
): Promise<ChartBar[]> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=${interval}&range=${range}`;
  const res = await fetch(url, {
    headers: { "User-Agent": "Mozilla/5.0" },
    cache: "no-store",
  });
  if (!res.ok) return [];
  const json = await res.json();
  const result = json?.chart?.result?.[0];
  const timestamps: number[] = result?.timestamp ?? [];
  const q = result?.indicators?.quote?.[0] ?? {};
  const bars: ChartBar[] = [];
  for (let i = 0; i < timestamps.length; i++) {
    const close = q.close?.[i];
    if (close == null || !Number.isFinite(close)) continue;
    const open = q.open?.[i] ?? close;
    const high = q.high?.[i] ?? close;
    const low = q.low?.[i] ?? close;
    const volume = q.volume?.[i] ?? 0;
    bars.push({
      time: timestamps[i],
      open,
      high,
      low,
      close,
      volume,
    });
  }
  return bars.sort((a, b) => (a.time as number) - (b.time as number));
}

function formatMetaTime(time: ChartBar["time"] | undefined): string | null {
  if (time == null) return null;
  if (typeof time === "number") {
    return new Date(time * 1000).toISOString();
  }
  return time;
}

/** Daily candles — prices.db (SQLite-first) with CSV / Yahoo fallback. */
export async function loadChartPayload(
  rawTicker: string,
  range: ChartRange = "1y",
  enabledDesks?: Set<string>,
  patternId?: string | null,
): Promise<ChartPayload> {
  const ticker = normalizeTicker(rawTicker);
  const empty: ChartPayload = {
    ticker,
    timeframe: "1d",
    range,
    source: "cache",
    cacheFile: null,
    bars: [],
    lines: [],
    hlines: [],
    zones: [],
    markers: [],
    deskOverlays: [],
    meta: { barCount: 0, first: null, last: null, lastClose: null },
  };
  if (!ticker) return empty;

  const cacheFile = resolveCacheFile(ticker);
  const storeBars = readBarsFromStore(ticker);
  let bars = storeBars ?? (cacheFile ? parseCsvBars(cacheFile) : []);
  let source: ChartPayload["source"] = storeBars ? "prices.db" : "cache";

  if (bars.length === 0) {
    ensureSymbolCached(ticker);
    if (CHART_ALLOW_YAHOO_FALLBACK) {
      bars = await fetchBarsFromYahoo(ticker, range);
      source = "yahoo";
    }
  } else if (isDailyCacheStale(bars)) {
    ensureSymbolCached(ticker);
    if (CHART_ALLOW_YAHOO_FALLBACK) {
      const yahooBars = await fetchBarsFromYahoo(ticker, range);
      const merged = mergeDailyBars(bars, yahooBars);
      if (merged.length > bars.length) {
        bars = merged;
        source = "cache+yahoo";
      }
    }
  }

  bars = filterByRange(bars, range);
  const lines: ChartLineSeries[] = [
    {
      id: "sma50",
      label: "SMA 50",
      color: "#f59e0b",
      data: computeSma(bars, 50),
    },
    {
      id: "sma200",
      label: "SMA 200",
      color: "#a78bfa",
      data: computeSma(bars, 200),
    },
  ];

  const deskOverlays = collectDeskOverlays(ticker, patternId, bars);
  const merged = mergeDeskOverlays(deskOverlays, enabledDesks);

  return {
    ticker,
    timeframe: "1d",
    range,
    source,
    cacheFile,
    bars,
    lines,
    hlines: merged.hlines,
    zones: merged.zones,
    markers: merged.markers,
    deskOverlays,
    patternHighlight: merged.patternHighlight,
    meta: {
      barCount: bars.length,
      first: formatMetaTime(bars[0]?.time),
      last: formatMetaTime(bars[bars.length - 1]?.time),
      lastClose: bars[bars.length - 1]?.close ?? null,
    },
  };
}

export async function loadIntradayChartPayload(
  rawTicker: string,
  interval: ChartTimeframe & ("5m" | "15m") = "5m",
  range: IntradayRange = "5d",
): Promise<ChartPayload> {
  const ticker = normalizeTicker(rawTicker);
  const empty: ChartPayload = {
    ticker,
    timeframe: interval,
    range,
    source: "yahoo",
    cacheFile: null,
    bars: [],
    lines: [],
    hlines: [],
    zones: [],
    markers: [],
    deskOverlays: [],
    meta: { barCount: 0, first: null, last: null, lastClose: null },
  };
  if (!ticker) return empty;

  const bars = await fetchIntradayFromYahoo(ticker, interval, range);

  return {
    ticker,
    timeframe: interval,
    range,
    source: "yahoo",
    cacheFile: null,
    bars,
    lines: [],
    hlines: [],
    zones: [],
    markers: [],
    deskOverlays: [],
    meta: {
      barCount: bars.length,
      first: formatMetaTime(bars[0]?.time),
      last: formatMetaTime(bars[bars.length - 1]?.time),
      lastClose: bars[bars.length - 1]?.close ?? null,
    },
  };
}
