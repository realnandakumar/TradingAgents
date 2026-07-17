"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { getDeskConfig, type DeskAction } from "@/lib/desk-cli-config";
import { notifyDeskJobStarted } from "@/lib/desk-cli-events";
import { useDeskJob } from "@/lib/desk-job-context";
import type { DeskCliJobProgress } from "@/lib/desk-cli-server";

interface Props {
  deskId: string;
}

export function DeskActionsPanel({ deskId }: Props) {
  const router = useRouter();
  const { isJobRunning } = useDeskJob();
  const config = getDeskConfig(deskId);
  const hasTickerActions = useMemo(
    () => config?.actions.some((a) => a.needsTicker) ?? false,
    [config],
  );

  const [ticker, setTicker] = useState("");
  const [activeAction, setActiveAction] = useState<DeskAction | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [command, setCommand] = useState<string | null>(null);
  const [progress, setProgress] = useState<DeskCliJobProgress | null>(null);
  const [running, setRunning] = useState(false);
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
          if (data.progress.status === "completed" || data.progress.status === "failed") {
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

  const startDeskJob = useCallback(
    async (action: DeskAction) => {
      setError(null);
      setRunning(true);
      setActiveAction(action);
      setProgress(null);
      setJobId(null);
      setCommand(null);

      try {
        const res = await fetch("/api/desk-cli", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            deskId,
            actionId: action.id,
            ticker: action.needsTicker ? ticker.trim() : undefined,
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          throw new Error(data.error ?? "Failed to start command");
        }
        notifyDeskJobStarted(data.jobId, deskId, action.id);
        setJobId(data.jobId);
        setCommand(data.command ?? null);
        pollJob(data.jobId);
      } catch (e) {
        setRunning(false);
        setActiveAction(null);
        setError(e instanceof Error ? e.message : "Failed to start command");
        throw e;
      }
    },
    [deskId, pollJob, ticker],
  );

  useEffect(() => () => stopPolling(), [stopPolling]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [progress?.lines]);

  const runAction = async (action: DeskAction) => {
    if (action.needsTicker && !ticker.trim()) {
      setError("Enter a ticker for this action");
      return;
    }
    if (isJobRunning || running) {
      setError("Another job is already running — check the status bar.");
      return;
    }

    await startDeskJob(action);
  };

  if (!config) return null;

  return (
    <>
      <section className="card p-4 sm:p-5 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium">Desk actions</h2>
            <p className="text-xs text-muted mt-0.5">
              Run CLI commands without leaving the dashboard
            </p>
          </div>
          {command ? (
            <code className="text-[10px] font-mono text-muted bg-surface-2 px-2 py-1 rounded max-w-full truncate">
              {command}
            </code>
          ) : null}
        </div>

        {hasTickerActions ? (
          <label className="block space-y-1.5 max-w-xs">
            <span className="text-xs text-muted">Ticker (for explain actions)</span>
            <input
              type="text"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="RELIANCE"
              disabled={running}
              className="w-full px-3 py-2 rounded-lg bg-surface-2 border border-border text-sm font-mono focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50"
            />
          </label>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {config.actions
            .filter((action) => action.id !== "screener")
            .map((action) => {
            const isPrimary = action.variant === "primary";
            return (
              <button
                key={action.id}
                type="button"
                onClick={() => runAction(action)}
                disabled={running || isJobRunning}
                title={action.description}
                className={
                  isPrimary
                    ? "px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
                    : "px-3 py-1.5 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50 hover:bg-surface-2/80 transition-colors"
                }
              >
                {action.label}
              </button>
            );
          })}
        </div>

        {error ? <p className="text-sm text-bear">{error}</p> : null}

        {(running || progress) && (
          <div className="space-y-3 pt-1 border-t border-border">
            <div className="flex items-center justify-between gap-4 text-xs">
              <span className="text-muted">
                {activeAction?.label ?? "Running"}
                {progress ? (
                  <span className="ml-2 capitalize">{progress.status}</span>
                ) : null}
              </span>
              {jobId ? (
                <span className="font-mono text-[10px] text-muted truncate">{jobId}</span>
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
                    className="max-h-56 overflow-y-auto rounded-lg bg-surface-2 border border-border p-3 font-mono text-[11px] space-y-0.5"
                  >
                    {progress.lines.map((line, i) => (
                      <div
                        key={i}
                        className={
                          line.startsWith("[err]") ? "text-bear/90" : "text-muted"
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
        )}
      </section>
    </>
  );
}
