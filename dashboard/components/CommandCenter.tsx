"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { getDeskConfig, getDeskActionLabel } from "@/lib/desk-cli-config";
import { notifyDeskJobStarted } from "@/lib/desk-cli-events";
import { useDeskJob } from "@/lib/desk-job-context";
import type { DeskCliJob, DeskCliJobProgress } from "@/lib/desk-cli-server";
import type { PortfolioDeskSummary } from "@/lib/command-center-server";
import {
  type ReplacementApprovalRequest,
  useReplacementApproval,
} from "@/lib/useReplacementApproval";
import { ReplacementApprovalModal } from "@/components/ReplacementApprovalModal";

interface Props {
  portfolioDesks: PortfolioDeskSummary[];
  recentJobs: DeskCliJob[];
}

interface ActiveJob {
  deskId: string;
  actionId: string;
  label: string;
}

const BULK_ACTIONS = [
  { actionId: "all-dailies", label: "Run all dailies", primary: true },
  { actionId: "all-screeners", label: "Run all screeners", primary: true },
  { actionId: "rs-screen", label: "RS screen", primary: true },
  { actionId: "rs-paper", label: "RS paper refresh", primary: false },
] as const;

const TECH_ACTIONS: { actionId: string; label: string; primary?: boolean }[] = [
  { actionId: "analyze-stale", label: "Analyze stale" },
  { actionId: "process", label: "Process zones" },
  { actionId: "process-apply", label: "Apply replacements" },
  { actionId: "daily", label: "Daily run", primary: true },
  { actionId: "report", label: "Report" },
];

function jobStatusTone(status: string): string {
  if (status === "completed") return "text-bull";
  if (status === "failed") return "text-bear";
  if (status === "running") return "text-accent";
  return "text-muted";
}

function formatJobWhen(iso?: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
  } catch {
    return iso;
  }
}

export function CommandCenter({ portfolioDesks, recentJobs }: Props) {
  const router = useRouter();
  const { isJobRunning } = useDeskJob();
  const [running, setRunning] = useState(false);
  const [activeJob, setActiveJob] = useState<ActiveJob | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [command, setCommand] = useState<string | null>(null);
  const [progress, setProgress] = useState<DeskCliJobProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollJob = useCallback(
    (id: string) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetch(`/api/desk-cli?jobId=${encodeURIComponent(id)}`);
          if (!res.ok) return;
          const data = (await res.json()) as { progress: DeskCliJobProgress };
          setProgress(data.progress);
          if (
            data.progress.status === "completed" ||
            data.progress.status === "failed"
          ) {
            stopPolling();
            setRunning(false);
            if (data.progress.status === "completed") {
              router.refresh();
            }
          }
        } catch {
          /* keep polling */
        }
      }, 2000);
    },
    [router, stopPolling],
  );

  useEffect(() => () => stopPolling(), [stopPolling]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [progress?.lines]);

  const startDeskJob = async (
    deskId: string,
    actionId: string,
    label: string,
    extra?: { proposalIds?: string[]; processDate?: string },
  ) => {
    setError(null);
    setRunning(true);
    setActiveJob({ deskId, actionId, label });
    setProgress(null);
    setJobId(null);
    setCommand(null);

    try {
      const res = await fetch("/api/desk-cli", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          deskId,
          actionId,
          proposalIds: extra?.proposalIds,
          processDate: extra?.processDate,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error ?? "Failed to start command");
      }
      notifyDeskJobStarted(data.jobId, deskId, actionId);
      setJobId(data.jobId);
      setCommand(data.command ?? null);
      pollJob(data.jobId);
    } catch (e) {
      setRunning(false);
      setActiveJob(null);
      setError(e instanceof Error ? e.message : "Failed to start command");
      throw e;
    }
  };

  const replacement = useReplacementApproval({
    onApprove: async (request: ReplacementApprovalRequest) => {
      const label = getDeskActionLabel(request.deskId, request.actionId);
      await startDeskJob(request.deskId, request.actionId, label, {
        proposalIds: request.proposalIds,
        processDate: request.processDate,
      });
    },
    onEmpty: (_deskId, actionId) => {
      setError(
        actionId === "process-apply"
          ? "No queued portfolio replacements from the latest Tech Desk process run."
          : "No pending portfolio replacements.",
      );
    },
    onError: (message) => setError(message),
  });

  const runAction = async (deskId: string, actionId: string, label: string) => {
    if (running || isJobRunning || replacement.loading) return;

    if (replacement.isReplacementAction(actionId)) {
      const action = getDeskConfig(deskId)?.actions.find((a) => a.id === actionId);
      const handled = await replacement.openReplacementModal({
        deskId,
        actionId,
        title: action?.label ?? label,
        description:
          action?.description ??
          "Select replacements to approve. This may foreclose open positions.",
      });
      if (handled) return;
    }

    await startDeskJob(deskId, actionId, label);
  };

  const controlCenter = getDeskConfig("control-center");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Command Center</h1>
          <p className="text-sm text-muted mt-1">
            Run bulk jobs and quick desk actions from one place
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_220px]">
        <div className="space-y-6">
          {/* Bulk operations */}
          <section className="card p-4 sm:p-5 space-y-4">
            <div>
              <h2 className="text-sm font-medium">Bulk operations</h2>
              <p className="text-xs text-muted mt-0.5">
                Shared-download scripts and RS paper tools
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {BULK_ACTIONS.map((item) => {
                const action = controlCenter?.actions.find((a) => a.id === item.actionId);
                return (
                  <button
                    key={item.actionId}
                    type="button"
                    onClick={() =>
                      runAction("control-center", item.actionId, item.label)
                    }
                    disabled={running || isJobRunning}
                    title={action?.description}
                    className={
                      item.primary
                        ? "text-left p-4 rounded-lg bg-accent/10 border border-accent/30 hover:bg-accent/15 transition-colors disabled:opacity-50"
                        : "text-left p-4 rounded-lg bg-surface-2 border border-border hover:bg-surface-2/80 transition-colors disabled:opacity-50"
                    }
                  >
                    <div
                      className={`text-sm font-medium ${item.primary ? "text-accent" : ""}`}
                    >
                      {item.label}
                    </div>
                    {action?.description ? (
                      <p className="text-xs text-muted mt-1 line-clamp-2">
                        {action.description}
                      </p>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </section>

          {/* Portfolio desks */}
          <section className="space-y-3">
            <div>
              <h2 className="text-sm font-medium">Portfolio desks</h2>
              <p className="text-xs text-muted mt-0.5">
                Quick actions per strategy paper book
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {portfolioDesks.map((desk) => (
                <div key={desk.id} className="card p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <Link
                        href={desk.href}
                        className="text-sm font-medium hover:text-accent transition-colors"
                      >
                        {desk.label}
                      </Link>
                      {desk.openCount !== null ? (
                        <p className="text-xs text-muted mt-0.5">
                          {desk.openCount} open position{desk.openCount === 1 ? "" : "s"}
                        </p>
                      ) : null}
                    </div>
                    <Link
                      href={desk.href}
                      className="text-[10px] text-muted hover:text-foreground"
                    >
                      Open →
                    </Link>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {getDeskConfig(desk.id)?.actions.some((a) => a.id === "daily") ? (
                      <button
                        type="button"
                        disabled={running || isJobRunning}
                        onClick={() => runAction(desk.id, "daily", `${desk.label} daily`)}
                        className="px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
                      >
                        Daily
                      </button>
                    ) : null}
                    {getDeskConfig(desk.id)?.actions.some((a) => a.id === "screener") ? (
                      <button
                        type="button"
                        disabled={running || isJobRunning}
                        onClick={() =>
                          runAction(desk.id, "screener", `${desk.label} screener`)
                        }
                        className="px-3 py-1.5 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50 hover:bg-surface-2/80 transition-colors"
                      >
                        Screener
                      </button>
                    ) : null}
                    {getDeskConfig(desk.id)?.actions.some((a) => a.id === "approve") ? (
                      <button
                        type="button"
                        disabled={running || isJobRunning || replacement.loading}
                        onClick={() =>
                          runAction(desk.id, "approve", `${desk.label} approve`)
                        }
                        className="px-3 py-1.5 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50 hover:bg-surface-2/80 transition-colors"
                      >
                        Approve
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Tech desk */}
          <section className="card p-4 sm:p-5 space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-medium">Tech Desk</h2>
                <p className="text-xs text-muted mt-0.5">
                  Analyze, process zones, and daily rules-only run
                </p>
              </div>
              <Link
                href="/tech-desk"
                className="text-xs text-muted hover:text-foreground"
              >
                Full desk →
              </Link>
            </div>
            <div className="flex flex-wrap gap-2">
              {TECH_ACTIONS.map((item) => (
                <button
                  key={item.actionId}
                  type="button"
                  disabled={running || isJobRunning || replacement.loading}
                  onClick={() =>
                    runAction("tech-desk", item.actionId, item.label)
                  }
                  className={
                    item.primary
                      ? "px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
                      : "px-3 py-1.5 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50 hover:bg-surface-2/80 transition-colors"
                  }
                >
                  {item.label}
                </button>
              ))}
            </div>
          </section>

          {/* Job monitor */}
          <section className="card p-4 sm:p-5 space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-medium">Job monitor</h2>
                <p className="text-xs text-muted mt-0.5">
                  Live output from the current command
                </p>
              </div>
              {command ? (
                <code className="text-[10px] font-mono text-muted bg-surface-2 px-2 py-1 rounded max-w-full truncate">
                  {command}
                </code>
              ) : null}
            </div>

            {error ? <p className="text-sm text-bear">{error}</p> : null}

            {running || progress ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-4 text-xs">
                  <span className="text-muted">
                    {activeJob?.label ?? "Running"}
                    {progress ? (
                      <span className="ml-2 capitalize">{progress.status}</span>
                    ) : null}
                  </span>
                  {jobId ? (
                    <span className="font-mono text-[10px] text-muted truncate">
                      {jobId}
                    </span>
                  ) : null}
                </div>

                {progress ? (
                  <>
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-xs text-muted">
                        <span>Output</span>
                        <span>{progress.percent}%</span>
                      </div>
                      <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
                        <div
                          className={`h-full transition-all duration-500 ${
                            progress.status === "failed" ? "bg-bear" : "bg-accent"
                          }`}
                          style={{ width: `${progress.percent}%` }}
                        />
                      </div>
                    </div>

                    {progress.error ? (
                      <p className="text-sm text-bear">{progress.error}</p>
                    ) : null}

                    {progress.lines.length > 0 ? (
                      <div
                        ref={logRef}
                        className="max-h-72 overflow-y-auto rounded-lg bg-surface-2 border border-border p-3 font-mono text-[11px] space-y-0.5"
                      >
                        {progress.lines.map((line, i) => (
                          <div
                            key={i}
                            className={
                              line.startsWith("[err]")
                                ? "text-bear/90"
                                : "text-muted"
                            }
                          >
                            {line}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-muted">Waiting for output…</p>
                    )}
                  </>
                ) : (
                  <p className="text-sm text-muted">Starting job…</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-muted">
                No job running. Start a bulk action or desk command above.
              </p>
            )}
          </section>
        </div>

        {/* Recent jobs sidebar */}
        <aside className="card p-4 space-y-3 h-fit">
          <h2 className="text-xs font-medium uppercase tracking-wide text-muted">
            Recent jobs
          </h2>
          {recentJobs.length === 0 ? (
            <p className="text-xs text-muted">No jobs yet</p>
          ) : (
            <ul className="space-y-2">
              {recentJobs.map((job) => (
                <li
                  key={job.job_id}
                  className="text-[11px] border-b border-border/60 pb-2 last:border-0 last:pb-0"
                >
                  <div className="font-medium truncate">
                    {getDeskActionLabel(job.desk_id, job.action_id)}
                  </div>
                  <div className={`capitalize ${jobStatusTone(job.status)}`}>
                    {job.status}
                  </div>
                  <div className="text-muted font-mono truncate mt-0.5">
                    {formatJobWhen(job.completed_at ?? job.created_at)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>

      <ReplacementApprovalModal
        open={replacement.open}
        title={replacement.modalTitle}
        description={replacement.modalDescription}
        items={replacement.items}
        loading={replacement.loading}
        submitting={replacement.submitting}
        selectedIds={replacement.selectedIds}
        onToggle={replacement.toggleId}
        onToggleAll={replacement.toggleAll}
        onApprove={replacement.approveSelected}
        onCancel={replacement.closeModal}
      />
    </div>
  );
}
