import fs from "fs";
import os from "os";
import path from "path";

import { listRecentJobsForDesk } from "@/lib/desk-cli-server";
import { checkLlmApiKey } from "@/lib/env-server";
import { isTradingDayIst, todayIstIso } from "@/lib/market-calendar";
import {
  readAllClosedTrades,
  readTechDeskBook,
  readTechDeskPending,
} from "@/lib/tech-desk-server";
import { readWatchlist } from "@/lib/watchlist-server";
import { summarizeReportFreshness } from "@/lib/tech-reports-server";

const TRADINGAGENTS_HOME =
  process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");
const TECH_DESK_DIR = path.join(TRADINGAGENTS_HOME, "tech_desk");

function readJsonFile<T>(filePath: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
  } catch {
    return null;
  }
}

function latestJsonIn(dir: string, excludePrefix?: string): Record<string, unknown> | null {
  if (!fs.existsSync(dir)) return null;
  const files = fs
    .readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .filter((f) => !excludePrefix || !f.startsWith(excludePrefix))
    .sort()
    .reverse();
  if (files.length === 0) return null;
  return readJsonFile(path.join(dir, files[0]!));
}

function latestReviewMarkdown(): { date: string | null; markdown: string | null } {
  const processDir = path.join(TECH_DESK_DIR, "process");
  if (!fs.existsSync(processDir)) return { date: null, markdown: null };
  const files = fs
    .readdirSync(processDir)
    .filter((f) => f.startsWith("review_") && f.endsWith(".json"))
    .sort()
    .reverse();
  if (files.length === 0) return { date: null, markdown: null };
  const data = readJsonFile<{ review_markdown?: string; date?: string }>(
    path.join(processDir, files[0]!),
  );
  return {
    date: data?.date ?? files[0]!.replace("review_", "").replace(".json", ""),
    markdown: data?.review_markdown ?? null,
  };
}

function jobSummary(
  jobs: ReturnType<typeof listRecentJobsForDesk>,
  actionIds: string[],
) {
  const hit = jobs.find((j) => actionIds.includes(j.action_id));
  if (!hit) return { at: null, status: null, actionId: null as string | null };
  return {
    at: hit.completed_at ?? hit.started_at ?? hit.created_at ?? null,
    status: hit.status,
    actionId: hit.action_id,
  };
}

function realizedPnl30d(closed: ReturnType<typeof readAllClosedTrades>): number {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - 30);
  const cutoffStr = cutoff.toISOString().slice(0, 10);
  return closed
    .filter((t) => (t.exit_date ?? "") >= cutoffStr)
    .reduce((s, t) => s + (t.rupee_pnl ?? 0), 0);
}

export interface TechDeskPnlSummary {
  realizedTotal: number;
  realizedTrades: number;
  winRate: number | null;
  realized30d: number;
  openCount: number;
  pendingCount: number;
}

export interface DailyOpsStatus {
  isTradingDay: boolean;
  todayIst: string;
  lastDailyDate: string | null;
  dailyDue: boolean;
}

export interface PipelineNextAction {
  message: string;
  actionId?: string;
  tone: "accent" | "bull" | "bear" | "muted";
}

export interface TechDeskStatus {
  apiKey: ReturnType<typeof checkLlmApiKey>;
  watchlist: { count: number; path: string };
  reports: ReturnType<typeof summarizeReportFreshness>;
  pnl: TechDeskPnlSummary;
  dailyOps: DailyOpsStatus;
  nextAction: PipelineNextAction;
  pipeline: {
    analyze: { at: string | null; status: string | null; actionId: string | null };
    process: { at: string | null; status: string | null };
    daily: { at: string | null; status: string | null };
    review: { at: string | null; status: string | null };
  };
  latestProcess: Record<string, unknown> | null;
  latestDaily: Record<string, unknown> | null;
  latestReview: { date: string | null; markdown: string | null };
}

function computeNextAction(
  reports: ReturnType<typeof summarizeReportFreshness>,
  dailyOps: DailyOpsStatus,
  openCount: number,
): PipelineNextAction {
  const staleMissing = reports.stale + reports.missing;
  if (reports.total > 0 && staleMissing > 0) {
    return {
      message: `${reports.fresh} fresh · ${reports.stale} stale · ${reports.missing} missing — refresh stale reports before Process`,
      actionId: "analyze-stale",
      tone: "accent",
    };
  }
  if (reports.fresh > 0 && openCount === 0) {
    return {
      message: `${reports.fresh} fresh reports ready — run Process to open trades or set pullback zones`,
      actionId: "process",
      tone: "accent",
    };
  }
  if (dailyOps.dailyDue) {
    return {
      message: "Trading day — Daily run not completed yet (exits + zone fills)",
      actionId: "daily",
      tone: "accent",
    };
  }
  if (reports.fresh === reports.total && reports.total > 0) {
    return {
      message: "Research pipeline healthy — run Daily each trading day; Review weekly if needed",
      tone: "bull",
    };
  }
  if (reports.total === 0) {
    return {
      message: "Add tickers to the watchlist, then Analyze",
      tone: "muted",
    };
  }
  return { message: "Pipeline up to date", tone: "bull" };
}

export function getTechDeskStatus(): TechDeskStatus {
  const { symbols, path: watchlistPath } = readWatchlist();
  const jobs = listRecentJobsForDesk("tech-desk", 30);
  const processDir =
    process.env.TRADINGAGENTS_TECH_DESK_PROCESS_LOG_DIR ??
    path.join(TECH_DESK_DIR, "process");
  const dailyDir =
    process.env.TRADINGAGENTS_TECH_DESK_DAILY_DIR ??
    path.join(TECH_DESK_DIR, "daily");

  const book = readTechDeskBook();
  const pending = readTechDeskPending();
  const closed = readAllClosedTrades();
  const reports = summarizeReportFreshness(symbols);
  const latestDaily = latestJsonIn(dailyDir);
  const todayIst = todayIstIso();
  const lastDailyDate = (latestDaily?.date as string | undefined) ?? null;
  const isTradingDay = isTradingDayIst();
  const dailyDue = isTradingDay && lastDailyDate !== todayIst;

  const dailyOps: DailyOpsStatus = {
    isTradingDay,
    todayIst,
    lastDailyDate,
    dailyDue,
  };

  const openCount = book?.positions.filter((p) => p.status === "open").length ?? 0;

  const wins = closed.filter((t) => (t.raw_return ?? 0) > 0).length;
  const winRate = closed.length > 0 ? (100 * wins) / closed.length : null;

  const pnl: TechDeskPnlSummary = {
    realizedTotal: closed.reduce((s, t) => s + (t.rupee_pnl ?? 0), 0),
    realizedTrades: closed.length,
    winRate,
    realized30d: realizedPnl30d(closed),
    openCount,
    pendingCount: pending.length,
  };

  return {
    apiKey: checkLlmApiKey(),
    watchlist: { count: symbols.length, path: watchlistPath },
    reports,
    pnl,
    dailyOps,
    nextAction: computeNextAction(reports, dailyOps, openCount),
    pipeline: {
      analyze: jobSummary(jobs, [
        "analyze-watchlist",
        "analyze-stale",
        "analyze-ticker",
      ]),
      process: jobSummary(jobs, ["process", "process-apply"]),
      daily: jobSummary(jobs, ["daily"]),
      review: jobSummary(jobs, ["review", "review-apply"]),
    },
    latestProcess: latestJsonIn(processDir, "review_"),
    latestDaily,
    latestReview: latestReviewMarkdown(),
  };
}
