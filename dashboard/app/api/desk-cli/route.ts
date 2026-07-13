import { spawn } from "child_process";
import { NextRequest, NextResponse } from "next/server";

import { getDeskAction } from "@/lib/desk-cli-config";
import {
  createJob,
  createStaleAnalyzeJob,
  deskCliJobScriptPath,
  getJob,
  getJobProgress,
  pythonExecutable,
  repoRootFromDashboard,
} from "@/lib/desk-cli-server";
import { rootEnvForSpawn } from "@/lib/env-server";

export const dynamic = "force-dynamic";

function spawnDeskCliJob(jobId: string): void {
  const script = deskCliJobScriptPath();
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
    const body = (await req.json()) as {
      deskId?: string;
      actionId?: string;
      ticker?: string;
      force?: boolean;
      proposalIds?: string[];
      processDate?: string;
    };

    if (!body.deskId?.trim() || !body.actionId?.trim()) {
      return NextResponse.json(
        { error: "deskId and actionId are required" },
        { status: 400 },
      );
    }

    const action = getDeskAction(body.deskId, body.actionId);
    if (!action) {
      return NextResponse.json({ error: "Unknown desk action" }, { status: 400 });
    }

    if (body.actionId === "analyze-stale") {
      const { jobId, job, tickers } = createStaleAnalyzeJob();
      spawnDeskCliJob(jobId);
      return NextResponse.json({ jobId, command: job.command, tickers });
    }

    const { jobId, job } = createJob(body.deskId, body.actionId, body.ticker, {
      force: body.force,
      proposalIds: body.proposalIds,
      processDate: body.processDate,
    });
    spawnDeskCliJob(jobId);
    return NextResponse.json({ jobId, command: job.command });
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
