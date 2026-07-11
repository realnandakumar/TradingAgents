import fs from "fs";
import os from "os";
import path from "path";

import { readWatchlist } from "@/lib/watchlist-server";

const TRADINGAGENTS_HOME =
  process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");
const REPORT_NAMES = new Set(["market.md", "complete_report.md"]);
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export type ReportFreshness = "fresh" | "stale" | "missing";

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

function reportAgeDays(reportDate: string, asOf: string): number {
  const asOfMs = new Date(`${asOf}T12:00:00`).getTime();
  const reportMs = new Date(`${reportDate}T12:00:00`).getTime();
  return Math.floor((asOfMs - reportMs) / (24 * 60 * 60 * 1000));
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function walkReports(root: string): Map<string, TickerReportMeta> {
  const byTicker = new Map<string, TickerReportMeta>();
  if (!fs.existsSync(root)) return byTicker;

  const asOf = todayIso();
  const maxAge = Number(process.env.TECH_DESK_MAX_REPORT_AGE_DAYS ?? 14);

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

      const norm = ticker.toUpperCase();
      let date = reportDate;
      if (!DATE_RE.test(date)) {
        try {
          date = new Date(fs.statSync(full).mtime).toISOString().slice(0, 10);
        } catch {
          date = asOf;
        }
      }

      const ageDays = reportAgeDays(date, asOf);
      const status: ReportFreshness =
        ageDays > maxAge ? "stale" : "fresh";

      const existing = byTicker.get(norm);
      const existingDate = existing?.reportDate ?? "";
      if (!existing || date.localeCompare(existingDate) > 0) {
        byTicker.set(norm, {
          ticker: norm,
          status,
          reportDate: date,
          ageDays,
          reportDir,
          sourceFile: ent.name,
        });
      }
    }
  }

  scanDir(root);
  return byTicker;
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
    const hit = found.get(norm);
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

export function readTechReportMarkdown(ticker: string): string | null {
  const root = techReportsDir();
  const found = walkReports(root);
  const meta = found.get(ticker.toUpperCase());
  if (!meta?.reportDir || !meta.sourceFile) return null;
  const filePath = path.join(meta.reportDir, meta.sourceFile);
  try {
    return fs.readFileSync(filePath, "utf-8");
  } catch {
    return null;
  }
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
