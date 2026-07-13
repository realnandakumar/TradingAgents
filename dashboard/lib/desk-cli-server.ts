import fs from "fs";
import os from "os";
import path from "path";
import { randomUUID } from "crypto";

import { getDeskAction } from "@/lib/desk-cli-config";
import {
  getStaleAndMissingTickers,
  writeTempWatchlistFile,
} from "@/lib/tech-reports-server";

const TRADINGAGENTS_HOME =
  process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");
const DESK_CLI_HOME = path.join(TRADINGAGENTS_HOME, "desk_cli");
const JOBS_DIR = path.join(DESK_CLI_HOME, "jobs");

export interface DeskCliJob {
  job_id: string;
  desk_id: string;
  action_id: string;
  cli_args: string[];
  /** Relative path from repo root when running a Python script instead of cli.main. */
  script?: string;
  command: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  exit_code?: number;
  error?: string;
}

export interface DeskCliJobProgress {
  jobId: string;
  deskId: string;
  actionId: string;
  command: string;
  status: string;
  percent: number;
  lines: string[];
  error?: string | null;
  startedAt?: string;
  updatedAt?: string;
  completedAt?: string;
  exitCode?: number;
}

function readJson<T>(filePath: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8")) as T;
  } catch {
    return null;
  }
}

function ensureDirs(): void {
  fs.mkdirSync(JOBS_DIR, { recursive: true });
}

export function repoRootFromDashboard(): string {
  return path.resolve(process.cwd(), "..");
}

export function pythonExecutable(): string {
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

export function deskCliJobScriptPath(): string {
  return path.join(repoRootFromDashboard(), "scripts", "run_desk_cli_job.py");
}

export function createJob(
  deskId: string,
  actionId: string,
  ticker?: string,
  options?: { force?: boolean; proposalIds?: string[]; processDate?: string },
): { jobId: string; job: DeskCliJob } {
  if (actionId === "analyze-stale") {
    const { jobId, job } = createStaleAnalyzeJob();
    return { jobId, job };
  }

  const action = getDeskAction(deskId, actionId);
  if (!action) {
    throw new Error(`Unknown desk action: ${deskId}/${actionId}`);
  }
  if (action.scriptPath) {
    return createScriptJob(deskId, actionId, action.scriptPath);
  }
  if (action.cliArgs.length === 0) {
    throw new Error(`Action ${deskId}/${actionId} has no CLI args`);
  }
  if (action.needsTicker && !ticker?.trim()) {
    throw new Error("Ticker is required for this action");
  }

  ensureDirs();
  const jobId = randomUUID();
  const cliArgs = [...action.cliArgs];
  if (options?.force && action.supportsForce) {
    cliArgs.push("--force");
  }
  if (options?.proposalIds?.length) {
    cliArgs.push("--ids", options.proposalIds.join(","));
  }
  if (options?.processDate?.trim() && deskId === "tech-desk" && actionId === "process-apply") {
    cliArgs.push("--date", options.processDate.trim());
  }
  if (action.needsTicker && ticker?.trim()) {
    const sym = ticker.trim().toUpperCase();
    if (action.tickerAsOption) {
      cliArgs.push(action.tickerFlag ?? "--ticker", sym);
    } else {
      cliArgs.push(sym);
    }
  }

  const job: DeskCliJob = {
    job_id: jobId,
    desk_id: deskId,
    action_id: actionId,
    cli_args: cliArgs,
    command: ["tradingagents", ...cliArgs].join(" "),
    status: "pending",
    created_at: new Date().toISOString(),
  };

  const jobPath = path.join(JOBS_DIR, `${jobId}.json`);
  fs.writeFileSync(jobPath, JSON.stringify(job, null, 2), "utf-8");
  return { jobId, job };
}

export function createScriptJob(
  deskId: string,
  actionId: string,
  scriptPath: string,
): { jobId: string; job: DeskCliJob } {
  ensureDirs();
  const jobId = randomUUID();
  const job: DeskCliJob = {
    job_id: jobId,
    desk_id: deskId,
    action_id: actionId,
    cli_args: [],
    script: scriptPath,
    command: `python ${scriptPath}`,
    status: "pending",
    created_at: new Date().toISOString(),
  };

  const jobPath = path.join(JOBS_DIR, `${jobId}.json`);
  fs.writeFileSync(jobPath, JSON.stringify(job, null, 2), "utf-8");
  return { jobId, job };
}

export function createStaleAnalyzeJob(): { jobId: string; job: DeskCliJob; tickers: string[] } {
  const symbols = getStaleAndMissingTickers();
  if (symbols.length === 0) {
    throw new Error("No stale or missing reports on the watchlist");
  }
  const watchlistFile = writeTempWatchlistFile(symbols);
  ensureDirs();
  const jobId = randomUUID();
  const cliArgs = ["tech-analyze", "--watchlist-file", watchlistFile];
  const command = `tradingagents tech-analyze --watchlist-file ${watchlistFile}`;

  const job: DeskCliJob = {
    job_id: jobId,
    desk_id: "tech-desk",
    action_id: "analyze-stale",
    cli_args: cliArgs,
    command,
    status: "pending",
    created_at: new Date().toISOString(),
  };

  const jobPath = path.join(JOBS_DIR, `${jobId}.json`);
  fs.writeFileSync(jobPath, JSON.stringify(job, null, 2), "utf-8");
  return { jobId, job, tickers: symbols };
}

export function getJob(jobId: string): DeskCliJob | null {
  const safeId = path.basename(jobId);
  return readJson<DeskCliJob>(path.join(JOBS_DIR, `${safeId}.json`));
}

export function getJobProgress(jobId: string): DeskCliJobProgress | null {
  const safeId = path.basename(jobId);
  const progressPath = path.join(JOBS_DIR, `${safeId}.progress.json`);
  const progress = readJson<DeskCliJobProgress>(progressPath);
  if (progress) return progress;

  const job = getJob(jobId);
  if (!job) return null;
  return {
    jobId,
    deskId: job.desk_id,
    actionId: job.action_id,
    command: job.command,
    status: job.status,
    percent: job.status === "completed" ? 100 : 0,
    lines: [],
    error: job.error ?? null,
    startedAt: job.started_at,
    completedAt: job.completed_at,
    exitCode: job.exit_code,
  };
}

function readAllJobs(): DeskCliJob[] {
  if (!fs.existsSync(JOBS_DIR)) return [];
  const jobs: DeskCliJob[] = [];
  for (const name of fs.readdirSync(JOBS_DIR)) {
    if (!name.endsWith(".json") || name.includes(".progress.")) continue;
    const job = readJson<DeskCliJob>(path.join(JOBS_DIR, name));
    if (job) jobs.push(job);
  }
  return jobs;
}

function sortJobsByRecency(jobs: DeskCliJob[]): DeskCliJob[] {
  return jobs.sort((a, b) =>
    (b.completed_at ?? b.created_at ?? "").localeCompare(
      a.completed_at ?? a.created_at ?? "",
    ),
  );
}

export function listRecentJobs(limit = 20): DeskCliJob[] {
  return sortJobsByRecency(readAllJobs()).slice(0, limit);
}

export function listRecentJobsForDesk(
  deskId: string,
  limit = 20,
): DeskCliJob[] {
  return sortJobsByRecency(
    readAllJobs().filter((job) => job.desk_id === deskId),
  ).slice(0, limit);
}

export interface JobWithProgress {
  job: DeskCliJob;
  progress: DeskCliJobProgress;
}

function jobsWithProgress(): JobWithProgress[] {
  return readAllJobs()
    .map((job) => {
      const progress = getJobProgress(job.job_id);
      return progress ? { job, progress } : null;
    })
    .filter((row): row is JobWithProgress => row !== null);
}

function sortByStartedDesc(rows: JobWithProgress[]): JobWithProgress[] {
  return rows.sort((a, b) =>
    (b.progress.startedAt ??
      b.job.started_at ??
      b.job.created_at ??
      "").localeCompare(
      a.progress.startedAt ?? a.job.started_at ?? a.job.created_at ?? "",
    ),
  );
}

/** No heartbeat for this long ⇒ treat as abandoned (crashed tab, killed process). */
const STALE_RUNNING_MS = 30 * 60 * 1000;
/** Running but no new output for this long ⇒ likely hung subprocess. */
const STALE_SILENT_MS = 5 * 60 * 1000;

function jobLastTouchMs(progress: DeskCliJobProgress, job: DeskCliJob): number {
  const ts =
    progress.updatedAt ??
    progress.startedAt ??
    job.started_at ??
    job.created_at;
  return ts ? new Date(ts).getTime() : 0;
}

export function isStaleActiveJob(row: JobWithProgress): boolean {
  const { job, progress } = row;
  if (progress.status !== "running" && progress.status !== "pending") {
    return false;
  }
  if (job.status === "completed" || job.status === "failed") {
    return true;
  }
  const lastTouch = jobLastTouchMs(progress, job);
  if (!lastTouch) return false;

  const silentFor = Date.now() - lastTouch;
  if (silentFor > STALE_RUNNING_MS) return true;
  if (silentFor > STALE_SILENT_MS && progress.percent < 95) return true;
  return false;
}

function reconcileStaleJob(row: JobWithProgress): void {
  const { job, progress } = row;
  const now = new Date().toISOString();
  const error =
    "Job timed out or was interrupted (process stopped responding)";

  const progressPath = path.join(JOBS_DIR, `${job.job_id}.progress.json`);
  const updatedProgress: DeskCliJobProgress = {
    ...progress,
    status: "failed",
    percent: 100,
    error,
    completedAt: now,
    updatedAt: now,
    exitCode: 1,
  };
  fs.writeFileSync(progressPath, JSON.stringify(updatedProgress, null, 2), "utf-8");

  const jobPath = path.join(JOBS_DIR, `${job.job_id}.json`);
  const updatedJob: DeskCliJob = {
    ...job,
    status: "failed",
    completed_at: now,
    exit_code: 1,
    error,
  };
  fs.writeFileSync(jobPath, JSON.stringify(updatedJob, null, 2), "utf-8");
}

/** Most recent job that is still pending or running. */
export function findActiveJobWithProgress(): JobWithProgress | null {
  const candidates = sortByStartedDesc(
    jobsWithProgress().filter(
      ({ progress }) => progress.status === "running" || progress.status === "pending",
    ),
  );

  for (const row of candidates) {
    if (isStaleActiveJob(row)) {
      reconcileStaleJob(row);
      continue;
    }
    return row;
  }
  return null;
}

/** Job that finished within the last `withinMs` milliseconds (when nothing is active). */
export function findRecentlyFinishedJob(withinMs = 15_000): JobWithProgress | null {
  const cutoff = Date.now() - withinMs;
  const finished = sortByStartedDesc(
    jobsWithProgress().filter(({ progress }) => {
      if (progress.status !== "completed" && progress.status !== "failed") {
        return false;
      }
      const doneAt = progress.completedAt ?? progress.updatedAt;
      if (!doneAt) return false;
      return new Date(doneAt).getTime() >= cutoff;
    }),
  );
  return finished[0] ?? null;
}
