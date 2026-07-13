import fs from "fs";
import os from "os";
import path from "path";

import type {
  ChartBar,
  ChartHLine,
  ChartLineSeries,
  ChartMarker,
  ChartPayload,
  ChartRange,
  ChartTimeframe,
  ChartZone,
  IntradayRange,
} from "./chart-types";
import {
  collectDeskOverlays,
  mergeDeskOverlays,
  normalizeChartTicker,
  parseDeskFilter,
  type DeskChartOverlay,
} from "./chart-overlays";
import { readWatchlist } from "@/lib/watchlist-server";

const TRADINGAGENTS_HOME =
  process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");

export function chartCacheDir(): string {
  return process.env.TRADINGAGENTS_CACHE_DIR ?? path.join(TRADINGAGENTS_HOME, "cache");
}

export function normalizeTicker(raw: string): string {
  return normalizeChartTicker(raw);
}

export function listCachedTickers(): string[] {
  const dir = chartCacheDir();
  if (!fs.existsSync(dir)) return [];
  const latest = new Map<string, number>();
  for (const file of fs.readdirSync(dir)) {
    const m = file.match(/^(.+)-YFin-data-.+\.csv$/i);
    if (!m) continue;
    const ticker = m[1].toUpperCase();
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

/** Daily candles only — cache CSV or Yahoo 1d fallback. */
export async function loadChartPayload(
  rawTicker: string,
  range: ChartRange = "1y",
  enabledDesks?: Set<string>,
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
  let bars = cacheFile ? parseCsvBars(cacheFile) : [];
  let source: "cache" | "yahoo" = "cache";

  if (bars.length === 0) {
    bars = await fetchBarsFromYahoo(ticker, range);
    source = "yahoo";
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

  const deskOverlays = collectDeskOverlays(ticker);
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
