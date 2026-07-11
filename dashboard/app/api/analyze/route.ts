import { spawn } from "child_process";
import { NextRequest, NextResponse } from "next/server";

import {
  analyzeJobScriptPath,
  createJob,
  getJob,
  getJobProgress,
  repoRootFromDashboard,
  type AnalyzeJobSpec,
} from "@/lib/analyze-server";
import { pythonExecutable } from "@/lib/desk-cli-server";
import { rootEnvForSpawn } from "@/lib/env-server";

export const dynamic = "force-dynamic";

function spawnAnalyzeJob(jobId: string): void {
  const script = analyzeJobScriptPath();
  const cwd = repoRootFromDashboard();
  const pythonCmd = pythonExecutable();

  const child = spawn(pythonCmd, [script, "--job-id", jobId], {
    cwd,
    detached: true,
    stdio: "ignore",
    env: { ...process.env, ...rootEnvForSpawn() },
  });
  child.unref();
}

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as AnalyzeJobSpec;
    if (!body.ticker?.trim()) {
      return NextResponse.json({ error: "ticker is required" }, { status: 400 });
    }

    const { jobId } = createJob(body);
    spawnAnalyzeJob(jobId);
    return NextResponse.json({ jobId });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to create job";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  const jobId = req.nextUrl.searchParams.get("jobId");
  if (!jobId) {
    return NextResponse.json({ error: "jobId query param required" }, { status: 400 });
  }

  const progress = getJobProgress(jobId);
  if (!progress) {
    return NextResponse.json({ error: "Job not found" }, { status: 404 });
  }

  const job = getJob(jobId);
  return NextResponse.json({ progress, job });
}
