import { NextResponse } from "next/server";

import { describeDeskJob } from "@/lib/desk-job-status";
import {
  findActiveJobWithProgress,
  findRecentlyFinishedJob,
} from "@/lib/desk-cli-server";

export const dynamic = "force-dynamic";

export async function GET() {
  const active = findActiveJobWithProgress();
  if (active) {
    const plain = describeDeskJob(
      active.job.desk_id,
      active.job.action_id,
      active.progress,
    );
    return NextResponse.json({
      mode: "active" as const,
      jobId: active.job.job_id,
      deskId: active.job.desk_id,
      actionId: active.job.action_id,
      status: active.progress.status,
      plain,
    });
  }

  const recent = findRecentlyFinishedJob();
  if (recent) {
    const plain = describeDeskJob(
      recent.job.desk_id,
      recent.job.action_id,
      recent.progress,
    );
    return NextResponse.json({
      mode: "recent" as const,
      jobId: recent.job.job_id,
      deskId: recent.job.desk_id,
      actionId: recent.job.action_id,
      status: recent.progress.status,
      plain,
    });
  }

  return NextResponse.json({ mode: "idle" as const });
}
