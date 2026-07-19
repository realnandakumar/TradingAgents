"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { MarkdownViewer } from "@/components/MarkdownViewer";
import {
  formatCliCommand,
  getDeskConfig,
  type DeskAction,
} from "@/lib/desk-cli-config";
import { notifyDeskJobStarted } from "@/lib/desk-cli-events";
import { useDeskJob } from "@/lib/desk-job-context";
import type { DeskCliJobProgress } from "@/lib/desk-cli-server";
import type { TechDeskStatus } from "@/lib/tech-desk-status-server";

function actionCommand(action: DeskAction, ticker?: string): string {
  return formatCliCommand(action.cliArgs, ticker, {
    tickerAsOption: action.tickerAsOption,
    tickerFlag: action.tickerFlag,
  });
}

function CommandCard({
  action,
  ticker,
  running,
  apiBlocked,
  onRun,
}: {
  action: DeskAction;
  ticker: string;
  running: boolean;
  apiBlocked: boolean;
  onRun: (action: DeskAction) => void;
}) {
  const isPrimary = action.variant === "primary";
  const isDestructive = action.destructive;
  const disabled =
    running || (action.requiresApiKey && apiBlocked) || (action.needsTicker && !ticker.trim());

  return (
    <div
      className={`rounded-lg border p-3 space-y-2 ${
        isDestructive ? "border-bear/30 bg-bear/5" : "border-border bg-surface-2/30"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-sm font-medium">{action.label}</div>
          {action.description ? (
            <p className="text-xs text-muted mt-1 leading-relaxed">{action.description}</p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => onRun(action)}
          disabled={disabled}
          className={
            isPrimary
              ? "shrink-0 px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium disabled:opacity-50 hover:opacity-90"
              : isDestructive
                ? "shrink-0 px-3 py-1.5 rounded-lg bg-bear/10 border border-bear/30 text-bear text-xs font-medium disabled:opacity-50"
                : "shrink-0 px-3 py-1.5 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50 hover:bg-surface-2/80"
          }
        >
          Run
        </button>
      </div>
      <code className="block text-[10px] font-mono text-muted break-all">
        {actionCommand(
          action,
          action.needsTicker ? ticker : undefined,
        )}
      </code>
    </div>
  );
}

export function TechDeskActionsPanel() {
  const router = useRouter();
  const { isJobRunning } = useDeskJob();
  const config = getDeskConfig("tech-desk");
  const analyzeActions = config?.actions.filter((a) => a.group === "analyze") ?? [];
  const deskActions = config?.actions.filter((a) => a.group === "desk") ?? [];

  const [status, setStatus] = useState<TechDeskStatus | null>(null);
  const [ticker, setTicker] = useState("");
  const [activeAction, setActiveAction] = useState<DeskAction | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [command, setCommand] = useState<string | null>(null);
  const [progress, setProgress] = useState<DeskCliJobProgress | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewMarkdown, setReviewMarkdown] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logRef = useRef<HTMLDivElement | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/tech-desk/status");
      if (res.ok) {
        const data = (await res.json()) as TechDeskStatus;
        setStatus(data);
        if (data.latestReview.markdown) setReviewMarkdown(data.latestReview.markdown);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const notifyRefresh = useCallback(() => {
    window.dispatchEvent(new CustomEvent("tech-desk-refresh"));
  }, []);

  const pollJob = useCallback(
    (id: string, action: DeskAction) => {
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
              await loadStatus();
              notifyRefresh();
              if (action.id === "review" || action.id === "review-apply") {
                const st = await fetch("/api/tech-desk/status").then((r) => r.json());
                if (st.latestReview?.markdown) setReviewMarkdown(st.latestReview.markdown);
              }
            }
          }
        } catch {
          /* keep polling */
        }
      }, 2000);
    },
    [loadStatus, notifyRefresh, router, stopPolling],
  );

  useEffect(() => () => stopPolling(), [stopPolling]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [progress?.lines]);

  const startDeskJob = async (action: DeskAction) => {
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
          deskId: "tech-desk",
          actionId: action.id,
          ticker: action.needsTicker ? ticker.trim() : undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to start command");
      notifyDeskJobStarted(data.jobId, "tech-desk", action.id);
      setJobId(data.jobId);
      setCommand(data.command ?? null);
      pollJob(data.jobId, action);
    } catch (e) {
      setRunning(false);
      setActiveAction(null);
      setError(e instanceof Error ? e.message : "Failed to start command");
      throw e;
    }
  };

  const runAction = async (action: DeskAction) => {
    if (action.needsTicker && !ticker.trim()) {
      setError("Enter a ticker for single-ticker analysis");
      return;
    }
    if (isJobRunning || running) {
      setError("Another job is already running — check the status bar.");
      return;
    }
    if (action.requiresApiKey && status && !status.apiKey.configured) {
      setError(status.apiKey.message);
      return;
    }
    if (action.destructive) {
      const msg =
        action.id === "review-apply"
          ? "Apply review recommendations? This may close positions and raise stops on the Tech Desk book."
          : "This action changes the paper book. Continue?";
      const ok = window.confirm(msg);
      if (!ok) return;
    }

    await startDeskJob(action);
  };

  if (!config) return null;

  const apiWarning = status && !status.apiKey.configured;
  const watchlistCount = status?.watchlist.count ?? 0;
  const analyzeWatchlist = analyzeActions.find((a) => a.id === "analyze-watchlist");
  const analyzeTicker = analyzeActions.find((a) => a.id === "analyze-ticker");
  const analyzeStale = analyzeActions.find((a) => a.id === "analyze-stale");
  const staleCount = (status?.reports.stale ?? 0) + (status?.reports.missing ?? 0);

  return (
    <div className="space-y-4">
      {apiWarning ? (
        <div className="rounded-lg border border-bear/40 bg-bear/5 px-4 py-3 text-sm text-bear">
          {status.apiKey.message}
        </div>
      ) : null}

      {/* Ticker analysis — two explicit options */}
      <section className="card p-4 sm:p-5 space-y-4">
        <div>
          <h2 className="text-sm font-medium">Ticker analysis</h2>
          <p className="text-xs text-muted mt-0.5 leading-relaxed">
            Generates AI technical reports saved to{" "}
            <code className="text-accent">tech_reports/TICKER/YYYY-MM-DD/</code>. Watchlist
            freshness below uses the report as-of date from those files — not when you added the
            ticker to the watchlist.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 gap-3">
          {analyzeWatchlist ? (
            <div className="rounded-lg border border-border bg-surface-2/30 p-3 space-y-2">
              <div className="text-sm font-medium">Entire watchlist</div>
              <p className="text-xs text-muted leading-relaxed">{analyzeWatchlist.description}</p>
              <button
                type="button"
                onClick={() => runAction(analyzeWatchlist)}
                disabled={running || isJobRunning || apiWarning || watchlistCount === 0}
                className="w-full px-3 py-2 rounded-lg bg-accent text-white text-xs font-medium disabled:opacity-50 hover:opacity-90"
              >
                {running && activeAction?.id === "analyze-watchlist"
                  ? "Running…"
                  : `Analyze all (${watchlistCount} ticker${watchlistCount === 1 ? "" : "s"})`}
              </button>
              <code className="block text-[10px] font-mono text-muted">
                {actionCommand(analyzeWatchlist)}
              </code>
            </div>
          ) : null}

          {analyzeTicker ? (
            <div className="rounded-lg border border-border bg-surface-2/30 p-3 space-y-2">
              <div className="text-sm font-medium">One ticker</div>
              <p className="text-xs text-muted leading-relaxed">{analyzeTicker.description}</p>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                placeholder="RELIANCE or TCS.NS"
                disabled={running}
                className="w-full px-3 py-2 rounded-lg bg-surface-2 border border-border text-sm font-mono focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50"
              />
              <button
                type="button"
                onClick={() => runAction(analyzeTicker)}
                disabled={running || isJobRunning || apiWarning || !ticker.trim()}
                className="w-full px-3 py-2 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50 hover:bg-surface-2/80"
              >
                {running && activeAction?.id === "analyze-ticker" ? "Running…" : "Analyze this ticker"}
              </button>
              <code className="block text-[10px] font-mono text-muted">
                {ticker.trim()
                  ? actionCommand(analyzeTicker, ticker)
                  : "tradingagents tech-analyze --ticker TICKER"}
              </code>
            </div>
          ) : null}
        </div>

        {analyzeStale ? (
          <div className="rounded-lg border border-border bg-surface-2/30 p-3 space-y-2">
            <div className="text-sm font-medium">Stale &amp; missing only</div>
            <p className="text-xs text-muted leading-relaxed">{analyzeStale.description}</p>
            <button
              type="button"
              onClick={() => runAction(analyzeStale)}
              disabled={running || isJobRunning || apiWarning || staleCount === 0}
              className="w-full sm:w-auto px-4 py-2 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50 hover:bg-surface-2/80"
            >
              {running && activeAction?.id === "analyze-stale"
                ? "Running…"
                : `Analyze stale & missing (${staleCount})`}
            </button>
            <code className="block text-[10px] font-mono text-muted">
              tradingagents tech-analyze --watchlist-file …/stale_watchlist.txt
            </code>
          </div>
        ) : null}
      </section>

      {/* Desk CLI commands with descriptions */}
      <section className="card p-4 sm:p-5 space-y-4" id="desk-commands">
        <div>
          <h2 className="text-sm font-medium">Desk commands</h2>
          <p className="text-xs text-muted mt-0.5">
            Paper portfolio operations after reports exist. Daily run is rules-only (no API cost).
          </p>
        </div>

        <div className="grid sm:grid-cols-2 gap-3">
          {deskActions.map((action) => (
            <CommandCard
              key={action.id}
              action={action}
              ticker={ticker}
              running={running || isJobRunning}
              apiBlocked={Boolean(apiWarning)}
              onRun={runAction}
            />
          ))}
        </div>

        {command ? (
          <code className="block text-[10px] font-mono text-muted bg-surface-2 px-2 py-1 rounded">
            Running: {command}
          </code>
        ) : null}

        {error ? <p className="text-sm text-bear">{error}</p> : null}

        {(running || progress) && (
          <div className="space-y-3 pt-1 border-t border-border">
            <div className="flex items-center justify-between gap-4 text-xs">
              <span className="text-muted">
                {activeAction?.label ?? "Running"}
                {progress ? <span className="ml-2 capitalize">{progress.status}</span> : null}
              </span>
              {jobId ? (
                <span className="font-mono text-[10px] text-muted truncate">{jobId}</span>
              ) : null}
            </div>

            {progress ? (
              <>
                <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
                  <div
                    className={`h-full transition-all ${progress.status === "failed" ? "bg-bear" : "bg-accent"}`}
                    style={{ width: `${progress.percent}%` }}
                  />
                </div>
                {progress.error ? <p className="text-sm text-bear">{progress.error}</p> : null}
                {progress.lines.length > 0 ? (
                  <div
                    ref={logRef}
                    className="max-h-56 overflow-y-auto rounded-lg bg-surface-2 border border-border p-3 font-mono text-[11px] space-y-0.5"
                  >
                    {progress.lines.map((line, i) => (
                      <div key={i} className={line.startsWith("[err]") ? "text-bear/90" : "text-muted"}>
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

      {reviewMarkdown ? (
        <section className="card p-4 sm:p-5">
          <h2 className="text-sm font-medium mb-3">Latest weekly review</h2>
          <MarkdownViewer text={reviewMarkdown} />
        </section>
      ) : null}
    </div>
  );
}
