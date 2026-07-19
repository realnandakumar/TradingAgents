import fs from "fs";
import os from "os";
import path from "path";

import { readWatchlist } from "@/lib/watchlist-server";

const TRADINGAGENTS_HOME =
  process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");
const REPORT_NAMES = new Set(["market.md", "complete_report.md"]);
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const PM_SUMMARY_FENCE_RE =
  /```(?:yaml|json)?\s*pm_summary\s*\n([\s\S]*?)```/gi;

export type ReportFreshness = "fresh" | "stale" | "missing";

export interface PmLevels {
  proposal?: string;
  bias?: string;
  confidence?: number | null;
  entry_zone_low?: number | null;
  entry_zone_high?: number | null;
  stop?: number | null;
  target_1?: number | null;
  target_2?: number | null;
  atr?: number | null;
  sma_50?: number | null;
  sma_200?: number | null;
  key_support?: string | null;
  key_resistance?: string | null;
  invalidation?: string | null;
  [key: string]: unknown;
}

export interface TraderReport {
  ticker: string;
  process_date?: string | null;
  report_date?: string | null;
  disposition: string;
  entry_type?: string | null;
  zone_low?: number | null;
  zone_high?: number | null;
  stop_loss?: number | null;
  target_1?: number | null;
  target_2?: number | null;
  confidence?: number | null;
  bias?: string | null;
  invalidation?: string | null;
  rationale?: string | null;
  reward_risk?: number | null;
  skip_reason?: string | null;
  saved_at?: string | null;
  source?: "trader.json" | "process_log" | "pending";
  markdown?: string | null;
}

export interface TickerReportMeta {
  ticker: string;
  status: ReportFreshness;
  /** As-of date from saved report path (tech_reports/TICKER/YYYY-MM-DD/). */
  reportDate: string | null;
  ageDays: number | null;
  reportDir: string | null;
  sourceFile: string | null;
}

export function techReportsDir(): string {
  return (
    process.env.TRADINGAGENTS_TECH_ANALYZE_REPORTS_DIR ??
    process.env.TECH_ANALYZE_REPORTS_DIR ??
    path.join(TRADINGAGENTS_HOME, "tech_reports")
  );
}

/** Match ``BHEL.NS`` folders to ``BHEL`` (and the reverse) — same as Python report_loader. */
export function tickerMatchKeys(ticker: string): Set<string> {
  const u = (ticker || "").toUpperCase().trim();
  const keys = new Set<string>();
  if (!u) return keys;
  keys.add(u);
  for (const suf of [".NS", ".BO"] as const) {
    if (u.endsWith(suf)) {
      keys.add(u.slice(0, -suf.length));
      return keys;
    }
  }
  keys.add(`${u}.NS`);
  keys.add(`${u}.BO`);
  return keys;
}

function reportAgeDays(reportDate: string, asOf: string): number {
  const asOfMs = new Date(`${asOf}T12:00:00`).getTime();
  const reportMs = new Date(`${reportDate}T12:00:00`).getTime();
  return Math.floor((asOfMs - reportMs) / (24 * 60 * 60 * 1000));
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function sourcePriority(name: string): number {
  return name === "complete_report.md" ? 1 : 0;
}

function isBetterMeta(next: TickerReportMeta, prev: TickerReportMeta | undefined): boolean {
  if (!prev) return true;
  const nd = next.reportDate ?? "";
  const pd = prev.reportDate ?? "";
  if (nd !== pd) return nd.localeCompare(pd) > 0;
  return sourcePriority(next.sourceFile ?? "") > sourcePriority(prev.sourceFile ?? "");
}

function walkReports(root: string): Map<string, TickerReportMeta> {
  /** Indexed by every match key (bare + .NS) pointing at the same meta. */
  const byKey = new Map<string, TickerReportMeta>();
  if (!fs.existsSync(root)) return byKey;

  const asOf = todayIso();
  const maxAge = Number(process.env.TECH_DESK_MAX_REPORT_AGE_DAYS ?? 14);

  function indexMeta(meta: TickerReportMeta): void {
    for (const key of tickerMatchKeys(meta.ticker)) {
      const existing = byKey.get(key);
      if (isBetterMeta(meta, existing)) {
        byKey.set(key, meta);
      }
    }
  }

  function scanDir(dir: string): void {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const ent of entries) {
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        scanDir(full);
        continue;
      }
      if (!REPORT_NAMES.has(ent.name)) continue;

      const reportDir = dir;
      const parentName = path.basename(reportDir);
      const grandParent = path.basename(path.dirname(reportDir));
      let ticker = grandParent;
      let reportDate = parentName;
      if (!DATE_RE.test(parentName)) {
        ticker = parentName;
        reportDate = "";
      }
      if (!ticker || ticker.startsWith(".")) continue;

      let date = reportDate;
      if (!DATE_RE.test(date)) {
        try {
          date = new Date(fs.statSync(full).mtime).toISOString().slice(0, 10);
        } catch {
          date = asOf;
        }
      }

      const ageDays = reportAgeDays(date, asOf);
      const status: ReportFreshness = ageDays > maxAge ? "stale" : "fresh";
      const displayTicker = ticker.includes(".") ? ticker.toUpperCase() : `${ticker.toUpperCase()}.NS`;

      indexMeta({
        ticker: displayTicker,
        status,
        reportDate: date,
        ageDays,
        reportDir,
        sourceFile: ent.name,
      });
    }
  }

  scanDir(root);
  return byKey;
}

function resolveMeta(
  found: Map<string, TickerReportMeta>,
  ticker: string,
  reportDate?: string | null,
): TickerReportMeta | null {
  const keys = [...tickerMatchKeys(ticker)];
  let best: TickerReportMeta | null = null;
  for (const key of keys) {
    const hit = found.get(key);
    if (!hit) continue;
    if (reportDate && hit.reportDate !== reportDate) continue;
    if (!best || isBetterMeta(hit, best)) best = hit;
  }
  if (best) return best;

  // Exact date folder walk when latest differs from position.report_date
  if (reportDate && DATE_RE.test(reportDate)) {
    const root = techReportsDir();
    for (const key of keys) {
      const bare = key.includes(".") ? key.slice(0, key.lastIndexOf(".")) : key;
      for (const folder of [key, bare]) {
        const dir = path.join(root, folder, reportDate);
        for (const name of ["complete_report.md", "market.md"] as const) {
          const filePath = path.join(dir, name);
          if (fs.existsSync(filePath)) {
            return {
              ticker: ticker.toUpperCase(),
              status: "fresh",
              reportDate,
              ageDays: reportAgeDays(reportDate, todayIso()),
              reportDir: dir,
              sourceFile: name,
            };
          }
        }
      }
    }
  }
  return null;
}

export function getReportMetaForTickers(
  tickers: string[],
  maxAgeDays = 14,
): TickerReportMeta[] {
  const root = techReportsDir();
  const found = walkReports(root);
  const asOf = todayIso();

  return tickers.map((raw) => {
    const norm = raw.toUpperCase();
    const hit = resolveMeta(found, norm);
    if (!hit) {
      return {
        ticker: norm,
        status: "missing" as const,
        reportDate: null,
        ageDays: null,
        reportDir: null,
        sourceFile: null,
      };
    }
    const ageDays = hit.reportDate ? reportAgeDays(hit.reportDate, asOf) : null;
    const status: ReportFreshness =
      ageDays != null && ageDays > maxAgeDays ? "stale" : hit.status;
    return { ...hit, ticker: norm, ageDays, status };
  });
}

function safeResolveUnderReports(candidate: string): string | null {
  const root = path.resolve(techReportsDir());
  const resolved = path.resolve(candidate);
  const rel = path.relative(root, resolved);
  if (!rel || rel.startsWith("..") || path.isAbsolute(rel)) return null;
  return resolved;
}

export function readTechReportMarkdown(
  ticker: string,
  opts?: { reportDate?: string | null; reportPath?: string | null },
): string | null {
  if (opts?.reportPath?.trim()) {
    const safe = safeResolveUnderReports(opts.reportPath.trim());
    if (safe && fs.existsSync(safe)) {
      try {
        return fs.readFileSync(safe, "utf-8");
      } catch {
        /* fall through to scan */
      }
    }
  }

  const found = walkReports(techReportsDir());
  const meta = resolveMeta(found, ticker, opts?.reportDate);
  if (!meta?.reportDir || !meta.sourceFile) return null;
  const filePath = path.join(meta.reportDir, meta.sourceFile);
  try {
    return fs.readFileSync(filePath, "utf-8");
  } catch {
    return null;
  }
}

/** Resolve report directory for a ticker (optional date / path hint). */
export function resolveTechReportDir(
  ticker: string,
  opts?: { reportDate?: string | null; reportPath?: string | null },
): { reportDir: string; reportDate: string | null; sourceFile: string | null } | null {
  if (opts?.reportPath?.trim()) {
    const safe = safeResolveUnderReports(opts.reportPath.trim());
    if (safe && fs.existsSync(safe)) {
      const reportDir = path.dirname(safe);
      const parent = path.basename(reportDir);
      return {
        reportDir,
        reportDate: DATE_RE.test(parent) ? parent : opts.reportDate ?? null,
        sourceFile: path.basename(safe),
      };
    }
  }
  const found = walkReports(techReportsDir());
  const meta = resolveMeta(found, ticker, opts?.reportDate);
  if (!meta?.reportDir) return null;
  return {
    reportDir: meta.reportDir,
    reportDate: meta.reportDate,
    sourceFile: meta.sourceFile,
  };
}

export function stripPmSummaryFence(markdown: string): {
  narrative: string;
  levelsFromFence: PmLevels | null;
} {
  let levelsFromFence: PmLevels | null = null;
  const narrative = markdown.replace(PM_SUMMARY_FENCE_RE, (_full, raw: string) => {
    if (!levelsFromFence) {
      try {
        const data = JSON.parse(String(raw).trim()) as Record<string, unknown>;
        const inner =
          data && typeof data === "object" && data.pm_summary && typeof data.pm_summary === "object"
            ? (data.pm_summary as PmLevels)
            : (data as PmLevels);
        levelsFromFence = inner;
      } catch {
        /* ignore parse errors */
      }
    }
    return "";
  });
  return { narrative: narrative.replace(/\n{3,}/g, "\n\n").trim(), levelsFromFence };
}

function readJsonFile(filePath: string): unknown | null {
  try {
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch {
    return null;
  }
}

export function readPmSummaryLevels(
  ticker: string,
  opts?: { reportDate?: string | null; reportPath?: string | null },
): PmLevels | null {
  const resolved = resolveTechReportDir(ticker, opts);
  if (!resolved) return null;
  const fromFile = readJsonFile(path.join(resolved.reportDir, "pm_summary.json"));
  if (fromFile && typeof fromFile === "object") {
    const obj = fromFile as Record<string, unknown>;
    if (obj.pm_summary && typeof obj.pm_summary === "object") {
      return obj.pm_summary as PmLevels;
    }
    return obj as PmLevels;
  }
  const md = readTechReportMarkdown(ticker, opts);
  if (!md) return null;
  return stripPmSummaryFence(md).levelsFromFence;
}

function techDeskHome(): string {
  return process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");
}

function processLogDirs(): string[] {
  const home = techDeskHome();
  return [
    path.join(home, "tech_desk", "process"),
    path.join(home, "rs_desk", "process"),
  ];
}

function traderFromProcessLog(ticker: string): TraderReport | null {
  const keys = tickerMatchKeys(ticker);
  for (const dir of processLogDirs()) {
    if (!fs.existsSync(dir)) continue;
    let files: string[] = [];
    try {
      files = fs
        .readdirSync(dir)
        .filter((f) => DATE_RE.test(f.replace(/\.json$/, "")))
        .sort()
        .reverse();
    } catch {
      continue;
    }
    for (const file of files) {
      const data = readJsonFile(path.join(dir, file));
      if (!data || typeof data !== "object") continue;
      const log = data as {
        date?: string;
        decision?: {
          opens?: Array<Record<string, unknown>>;
          waits?: Array<Record<string, unknown>>;
          skips?: Array<{ ticker?: string; reason?: string }>;
        };
        trader_skips?: Array<{ ticker?: string; reason?: string }>;
      };
      const processDate = log.date ?? file.replace(/\.json$/, "");
      const decision = log.decision;
      if (!decision) continue;

      for (const list of [decision.opens ?? [], decision.waits ?? []]) {
        for (const p of list) {
          const t = String(p.ticker ?? "").toUpperCase();
          if (![...keys].some((k) => k === t || tickerMatchKeys(t).has(k))) continue;
          return {
            ticker: t,
            process_date: processDate,
            report_date: null,
            disposition: String(p.action ?? "wait"),
            entry_type: p.entry_type != null ? String(p.entry_type) : null,
            zone_low: typeof p.zone_low === "number" ? p.zone_low : null,
            zone_high: typeof p.zone_high === "number" ? p.zone_high : null,
            stop_loss: typeof p.stop_loss === "number" ? p.stop_loss : null,
            target_1: typeof p.target_1 === "number" ? p.target_1 : null,
            target_2: typeof p.target_2 === "number" ? p.target_2 : null,
            confidence: typeof p.confidence === "number" ? p.confidence : null,
            bias: p.bias != null ? String(p.bias) : null,
            invalidation: p.invalidation != null ? String(p.invalidation) : null,
            rationale: p.rationale != null ? String(p.rationale) : null,
            reward_risk: null,
            skip_reason: null,
            source: "process_log",
          };
        }
      }
      for (const s of [...(decision.skips ?? []), ...(log.trader_skips ?? [])]) {
        const t = String(s.ticker ?? "").toUpperCase();
        if (![...keys].some((k) => k === t || tickerMatchKeys(t).has(k))) continue;
        return {
          ticker: t,
          process_date: processDate,
          disposition: "skip",
          skip_reason: s.reason ?? null,
          source: "process_log",
        };
      }
    }
  }
  return null;
}

export function readTraderReport(
  ticker: string,
  opts?: { reportDate?: string | null; reportPath?: string | null },
): TraderReport | null {
  const resolved = resolveTechReportDir(ticker, opts);
  if (resolved) {
    const jsonPath = path.join(resolved.reportDir, "trader.json");
    const raw = readJsonFile(jsonPath);
    if (raw && typeof raw === "object") {
      const obj = raw as TraderReport;
      let markdown: string | null = null;
      const mdPath = path.join(resolved.reportDir, "trader.md");
      try {
        if (fs.existsSync(mdPath)) markdown = fs.readFileSync(mdPath, "utf-8");
      } catch {
        markdown = null;
      }
      return {
        ...obj,
        ticker: (obj.ticker || ticker).toUpperCase(),
        report_date: obj.report_date ?? resolved.reportDate,
        source: "trader.json",
        markdown,
      };
    }
  }
  return traderFromProcessLog(ticker);
}

export function readTechDeskReportBundle(
  ticker: string,
  opts?: { reportDate?: string | null; reportPath?: string | null },
): {
  ticker: string;
  date: string | null;
  narrative: string | null;
  markdown: string | null;
  levels: PmLevels | null;
  trader: TraderReport | null;
} | null {
  const raw = readTechReportMarkdown(ticker, opts);
  const resolved = resolveTechReportDir(ticker, opts);
  if (raw == null && !resolved) {
    const traderOnly = readTraderReport(ticker, opts);
    if (!traderOnly) return null;
    return {
      ticker: ticker.toUpperCase(),
      date: opts?.reportDate ?? null,
      narrative: null,
      markdown: null,
      levels: null,
      trader: traderOnly,
    };
  }

  const { narrative, levelsFromFence } = stripPmSummaryFence(raw ?? "");
  const levels = readPmSummaryLevels(ticker, opts) ?? levelsFromFence;
  const trader = readTraderReport(ticker, opts);

  return {
    ticker: ticker.toUpperCase(),
    date: resolved?.reportDate ?? opts?.reportDate ?? null,
    narrative: narrative || null,
    markdown: narrative || null,
    levels,
    trader,
  };
}

export function getStaleAndMissingTickers(): string[] {
  const { symbols } = readWatchlist();
  const rows = getReportMetaForTickers(symbols);
  return rows
    .filter((r) => r.status === "stale" || r.status === "missing")
    .map((r) => r.ticker);
}

export function writeTempWatchlistFile(symbols: string[]): string {
  const dir = path.join(
    process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents"),
    "desk_cli",
  );
  fs.mkdirSync(dir, { recursive: true });
  const filePath = path.join(dir, "stale_watchlist.txt");
  const normalized = symbols.map((s) => s.trim().toUpperCase()).filter(Boolean);
  fs.writeFileSync(
    filePath,
    normalized.length ? `${normalized.join("\n")}\n` : "",
    "utf-8",
  );
  return filePath;
}

export function summarizeReportFreshness(tickers: string[], maxAgeDays = 14) {
  const rows = getReportMetaForTickers(tickers, maxAgeDays);
  return {
    total: tickers.length,
    fresh: rows.filter((r) => r.status === "fresh").length,
    stale: rows.filter((r) => r.status === "stale").length,
    missing: rows.filter((r) => r.status === "missing").length,
    rows,
    reportsDir: techReportsDir(),
    maxAgeDays,
  };
}
