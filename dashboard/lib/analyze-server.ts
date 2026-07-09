import fs from "fs";
import os from "os";
import path from "path";
import { randomUUID } from "crypto";

const TRADINGAGENTS_HOME =
  process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");
const ANALYZE_HOME = path.join(TRADINGAGENTS_HOME, "analyze");
const REPORTS_DIR = path.join(ANALYZE_HOME, "reports");
const JOBS_DIR = path.join(ANALYZE_HOME, "jobs");
const CACHE_DIR = path.join(TRADINGAGENTS_HOME, "cache");

export interface AnalyzeJobSpec {
  ticker: string;
  analysisDate?: string;
  researchDepth?: number;
  analysts?: string[];
  llmProvider?: string;
}

export interface AnalyzeJob {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  ticker: string;
  analysis_date?: string;
  analysts?: string[];
  research_depth?: number;
  llm_provider?: string;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  failed_at?: string;
  decision?: string;
  report_id?: string;
  report_path?: string;
  error?: string;
}

export interface JobProgress {
  jobId: string;
  status: string;
  stage: string;
  percent: number;
  agentStatus: Record<string, string>;
  messages: { time: string; type: string; content: string }[];
  startedAt?: string;
  updatedAt?: string;
  error?: string | null;
  decision?: string;
  reportId?: string;
}

export interface ReportMeta {
  id: string;
  ticker: string;
  analysisDate: string | null;
  createdAt: string;
  reportPath: string;
  decision?: string;
}

function readJson<T>(filePath: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
  } catch {
    return null;
  }
}

function ensureDirs(): void {
  fs.mkdirSync(REPORTS_DIR, { recursive: true });
  fs.mkdirSync(JOBS_DIR, { recursive: true });
}

export function analyzeHome(): string {
  return ANALYZE_HOME;
}

export function getTickerUniverse(): string[] {
  try {
    if (!fs.existsSync(CACHE_DIR)) return [];
    const files = fs
      .readdirSync(CACHE_DIR)
      .filter((f) => /^nse_nifty500_\d{8}\.csv$/i.test(f))
      .sort()
      .reverse();
    if (files.length === 0) return [];

    const text = fs.readFileSync(path.join(CACHE_DIR, files[0]), "utf-8");
    const lines = text.split(/\r?\n/).filter(Boolean);
    if (lines.length < 2) return [];

    const header = lines[0].split(",").map((h) => h.trim().toLowerCase());
    const symIdx = header.findIndex((h) => h === "symbol" || h === "ticker");
    if (symIdx < 0) return [];

    const symbols: string[] = [];
    const seen = new Set<string>();
    for (const line of lines.slice(1)) {
      const cols = line.split(",");
      const raw = (cols[symIdx] ?? "").trim().toUpperCase();
      if (!raw) continue;
      const sym = raw.includes(".") ? raw : `${raw}.NS`;
      if (!seen.has(sym)) {
        seen.add(sym);
        symbols.push(sym);
      }
    }
    return symbols.sort();
  } catch {
    return [];
  }
}

function parseReportMeta(id: string, dirPath: string): ReportMeta | null {
  const reportPath = path.join(dirPath, "complete_report.md");
  if (!fs.existsSync(reportPath)) return null;

  const stat = fs.statSync(reportPath);
  const ticker = id.replace(/_\d{8}_\d{6}$/, "");

  let analysisDate: string | null = null;
  try {
    const head = fs.readFileSync(reportPath, "utf-8").slice(0, 500);
    const m = head.match(/Generated:\s*(\d{4}-\d{2}-\d{2})/);
    if (m) analysisDate = m[1];
  } catch {
    /* ignore */
  }

  return {
    id,
    ticker,
    analysisDate,
    createdAt: stat.mtime.toISOString(),
    reportPath,
  };
}

export function listReports(): ReportMeta[] {
  if (!fs.existsSync(REPORTS_DIR)) return [];
  const entries = fs.readdirSync(REPORTS_DIR, { withFileTypes: true });
  const reports: ReportMeta[] = [];
  for (const ent of entries) {
    if (!ent.isDirectory()) continue;
    const meta = parseReportMeta(ent.name, path.join(REPORTS_DIR, ent.name));
    if (meta) reports.push(meta);
  }
  return reports.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export function readReport(reportId: string): string | null {
  const safeId = path.basename(reportId);
  const reportPath = path.join(REPORTS_DIR, safeId, "complete_report.md");
  if (!fs.existsSync(reportPath)) return null;
  return fs.readFileSync(reportPath, "utf-8");
}

export function createJob(spec: AnalyzeJobSpec): { jobId: string; job: AnalyzeJob } {
  ensureDirs();
  const jobId = randomUUID();
  const today = new Date().toISOString().slice(0, 10);
  const job: AnalyzeJob = {
    job_id: jobId,
    status: "pending",
    ticker: spec.ticker.trim().toUpperCase(),
    analysis_date: spec.analysisDate ?? today,
    research_depth: spec.researchDepth,
    analysts: spec.analysts,
    llm_provider: spec.llmProvider,
    created_at: new Date().toISOString(),
  };
  const jobPath = path.join(JOBS_DIR, `${jobId}.json`);
  fs.writeFileSync(jobPath, JSON.stringify(job, null, 2), "utf-8");
  return { jobId, job };
}

export function getJob(jobId: string): AnalyzeJob | null {
  const safeId = path.basename(jobId);
  return readJson<AnalyzeJob>(path.join(JOBS_DIR, `${safeId}.json`));
}

export function getJobProgress(jobId: string): JobProgress | null {
  const safeId = path.basename(jobId);
  const progressPath = path.join(JOBS_DIR, `${safeId}.progress.json`);
  const progress = readJson<JobProgress>(progressPath);
  if (progress) return progress;

  const job = getJob(jobId);
  if (!job) return null;
  return {
    jobId,
    status: job.status,
    stage: job.status === "completed" ? "completed" : job.status,
    percent: job.status === "completed" ? 100 : 0,
    agentStatus: {},
    messages: [],
    error: job.error ?? null,
    decision: job.decision,
    reportId: job.report_id,
  };
}

export function repoRootFromDashboard(): string {
  return path.resolve(process.cwd(), "..");
}

export function analyzeJobScriptPath(): string {
  return path.join(repoRootFromDashboard(), "scripts", "run_analyze_job.py");
}
