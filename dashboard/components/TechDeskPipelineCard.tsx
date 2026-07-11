"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { formatIstWhen } from "@/lib/market-calendar";
import type { TechDeskStatus } from "@/lib/tech-desk-status-server";

function inr(n: number): string {
  return n.toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  });
}

function stepTone(status: string | null): string {
  if (status === "completed") return "border-bull/40 bg-bull/5";
  if (status === "failed") return "border-bear/40 bg-bear/5";
  if (status === "running") return "border-accent/40 bg-accent/5";
  return "border-border bg-surface-2/30";
}

function buildProcessConfirmMessage(status: TechDeskStatus): string {
  const { fresh, stale, missing, rows } = status.reports;
  const staleTickers = rows.filter((r) => r.status === "stale").map((r) => r.ticker);
  const missingTickers = rows.filter((r) => r.status === "missing").map((r) => r.ticker);
  const freshTickers = rows.filter((r) => r.status === "fresh").map((r) => r.ticker);

  let msg =
    `Process uses watchlist tickers only — saved reports ≤14 days old.\n\n` +
    `✓ Fresh: ${fresh} ticker(s) — WILL be included\n`;
  if (stale > 0) {
    msg += `✗ Stale: ${stale} — EXCLUDED${staleTickers.length ? `: ${staleTickers.join(", ")}` : ""}\n`;
  }
  if (missing > 0) {
    msg += `✗ Missing: ${missing} — EXCLUDED${missingTickers.length ? `: ${missingTickers.join(", ")}` : ""}\n`;
  }
  if (fresh === 0) {
    msg += `\nNo fresh reports — Process will skip all tickers. Run Analyze first.`;
  } else {
    msg += `\n${freshTickers.slice(0, 8).join(", ")}${freshTickers.length > 8 ? "…" : ""}`;
    msg += `\n\nContinue Process with ${fresh} fresh report(s)?`;
  }
  return msg;
}

export function TechDeskPipelineCard() {
  const router = useRouter();
  const [status, setStatus] = useState<TechDeskStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState<string | null>(null);
  const [forceDaily, setForceDaily] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/tech-desk/status");
      if (res.ok) setStatus((await res.json()) as TechDeskStatus);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, [load]);

  useEffect(() => () => {
    if (pollRef.current) clearInterval(pollRef.current);
  }, []);

  const stopPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const pollJob = (jobId: string) => {
    stopPoll();
    pollRef.current = setInterval(async () => {
      const res = await fetch(`/api/desk-cli?jobId=${encodeURIComponent(jobId)}`);
      if (!res.ok) return;
      const data = (await res.json()) as { progress: { status: string } };
      if (data.progress.status === "completed" || data.progress.status === "failed") {
        stopPoll();
        setRunning(null);
        router.refresh();
        await load();
        window.dispatchEvent(new CustomEvent("tech-desk-refresh"));
      }
    }, 2000);
  };

  const runAction = async (
    actionId: string,
    opts?: { confirm?: string; destructive?: boolean; force?: boolean },
  ) => {
    if (status && !status.apiKey.configured && actionId !== "daily") {
      alert(status.apiKey.message);
      return;
    }
    if (opts?.confirm && !window.confirm(opts.confirm)) return;
    if (opts?.destructive) {
      const ok = window.confirm(
        "Apply review actions? This may close positions and raise stops.",
      );
      if (!ok) return;
    }

    setRunning(actionId);
    try {
      const res = await fetch("/api/desk-cli", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          deskId: "tech-desk",
          actionId,
          force: opts?.force,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to start");
      pollJob(data.jobId);
    } catch (e) {
      setRunning(null);
      alert(e instanceof Error ? e.message : "Failed to start job");
    }
  };

  const onProcess = () => {
    if (!status) return;
    window.alert(buildProcessConfirmMessage(status));
    if (status.reports.fresh === 0) return;
    runAction("process");
  };

  const staleMissing = (status?.reports.stale ?? 0) + (status?.reports.missing ?? 0);
  const processSummary = status?.latestProcess;
  const pnl = status?.pnl;
  const next = status?.nextAction;

  return (
    <section className="card p-4 sm:p-5 space-y-4">
      {/* P&L — primary success metric */}
      <div className="rounded-lg border border-border bg-surface-2/40 p-3 sm:p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium">Desk P&amp;L</h2>
            <p className="text-xs text-muted mt-0.5">
              Realized from closed trades (paper). Open MTM lives in the blotter below.
            </p>
          </div>
          {!loading && pnl ? (
            <div className="text-right tabular-nums">
              <div
                className={`text-lg font-semibold ${pnl.realizedTotal >= 0 ? "text-bull" : "text-bear"}`}
              >
                {inr(pnl.realizedTotal)}
              </div>
              <div className="text-[10px] text-muted">all-time realized</div>
            </div>
          ) : null}
        </div>
        {pnl ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3 text-xs">
            <div>
              <div className="text-muted text-[10px] uppercase">30d realized</div>
              <div className={`font-medium tabular-nums ${pnl.realized30d >= 0 ? "text-bull" : "text-bear"}`}>
                {inr(pnl.realized30d)}
              </div>
            </div>
            <div>
              <div className="text-muted text-[10px] uppercase">Win rate</div>
              <div className="font-medium tabular-nums">
                {pnl.winRate != null ? `${pnl.winRate.toFixed(0)}%` : "—"}
              </div>
              <div className="text-[10px] text-muted">{pnl.realizedTrades} closed</div>
            </div>
            <div>
              <div className="text-muted text-[10px] uppercase">Open</div>
              <div className="font-medium tabular-nums">{pnl.openCount}</div>
            </div>
            <div>
              <div className="text-muted text-[10px] uppercase">Pending zones</div>
              <div className="font-medium tabular-nums">{pnl.pendingCount}</div>
            </div>
          </div>
        ) : null}
      </div>

      {/* Next action */}
      {next ? (
        <div
          className={`rounded-lg border px-3 py-2 text-xs ${
            next.tone === "bull"
              ? "border-bull/30 bg-bull/5 text-bull"
              : next.tone === "bear"
                ? "border-bear/30 bg-bear/5 text-bear"
                : next.tone === "accent"
                  ? "border-accent/30 bg-accent/5 text-accent"
                  : "border-border text-muted"
          }`}
        >
          <span className="font-medium">Next: </span>
          {next.message}
          {next.actionId ? (
            <button
              type="button"
              disabled={Boolean(running)}
              onClick={() => {
                if (next.actionId === "process") onProcess();
                else if (next.actionId) runAction(next.actionId);
              }}
              className="ml-2 underline hover:no-underline disabled:opacity-50"
            >
              Run
            </button>
          ) : null}
        </div>
      ) : null}

      {/* Research pipeline (weekly) */}
      <div className="space-y-2">
        <div className="text-[10px] uppercase tracking-wide text-muted">
          Research pipeline · weekly (LLM)
        </div>
        <div className="grid sm:grid-cols-3 gap-2">
          <div className={`rounded-lg border px-3 py-2 ${stepTone(null)}`}>
            <div className="text-[10px] uppercase opacity-80">1 · Watchlist</div>
            <div className="text-xs mt-1">
              {loading ? "…" : `${status?.watchlist.count ?? 0} tickers`}
            </div>
            <div className="text-[10px] text-muted mt-0.5">
              {status?.reports.fresh ?? 0} fresh · {status?.reports.stale ?? 0} stale ·{" "}
              {status?.reports.missing ?? 0} missing
            </div>
          </div>

          <div className={`rounded-lg border px-3 py-2 ${stepTone(status?.pipeline.analyze.status ?? null)}`}>
            <div className="text-[10px] uppercase opacity-80">2 · Analyze</div>
            <div className="text-xs mt-1 tabular-nums">
              {formatIstWhen(status?.pipeline.analyze.at ?? null)}
            </div>
            <div className="flex flex-wrap gap-1 mt-2">
              {staleMissing > 0 ? (
                <button
                  type="button"
                  disabled={Boolean(running)}
                  onClick={() => runAction("analyze-stale")}
                  className="px-2 py-0.5 rounded text-[10px] bg-accent text-white disabled:opacity-50"
                >
                  {running === "analyze-stale" ? "…" : `Stale (${staleMissing})`}
                </button>
              ) : null}
              <button
                type="button"
                disabled={Boolean(running) || (status?.watchlist.count ?? 0) === 0}
                onClick={() => runAction("analyze-watchlist")}
                className="px-2 py-0.5 rounded text-[10px] bg-surface-2 border border-border disabled:opacity-50"
              >
                {running === "analyze-watchlist" ? "…" : "All"}
              </button>
            </div>
          </div>

          <div className={`rounded-lg border px-3 py-2 ${stepTone(status?.pipeline.process.status ?? null)}`}>
            <div className="text-[10px] uppercase opacity-80">3 · Process</div>
            <div className="text-xs mt-1 tabular-nums">
              {formatIstWhen(status?.pipeline.process.at ?? null)}
            </div>
            {processSummary ? (
              <div className="text-[10px] text-muted mt-0.5">
                opened {Array.isArray(processSummary.opened) ? processSummary.opened.length : 0} · waits{" "}
                {Array.isArray(processSummary.waits) ? processSummary.waits.length : 0}
              </div>
            ) : null}
            <button
              type="button"
              disabled={Boolean(running) || (status?.reports.fresh ?? 0) === 0}
              onClick={onProcess}
              className="mt-2 px-2 py-0.5 rounded text-[10px] bg-surface-2 border border-border disabled:opacity-50 hover:bg-surface-2/80"
            >
              {running === "process" ? "Running…" : `Process (${status?.reports.fresh ?? 0} fresh)`}
            </button>
          </div>
        </div>
      </div>

      {/* Ops pipeline (daily) */}
      <div className="space-y-2">
        <div className="text-[10px] uppercase tracking-wide text-muted">
          Ops pipeline · daily + weekly
        </div>
        <div className="grid sm:grid-cols-2 gap-2">
          <div
            className={`rounded-lg border px-3 py-2 ${stepTone(status?.pipeline.daily.status ?? null)} ${
              status?.dailyOps.dailyDue ? "ring-1 ring-accent/50" : ""
            }`}
          >
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase opacity-80">4 · Daily</span>
              {status?.dailyOps.dailyDue ? (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-accent/20 text-accent font-medium">
                  Run today
                </span>
              ) : null}
            </div>
            <div className="text-xs mt-1 tabular-nums">
              Last: {status?.dailyOps.lastDailyDate ?? "Never"}
            </div>
            <p className="text-[10px] text-muted mt-1 leading-relaxed">
              Rules-only: stops, targets, time exits, pullback zone fills. No API cost.
            </p>
            <label className="mt-2 flex items-center gap-1.5 text-[10px] text-muted">
              <input
                type="checkbox"
                checked={forceDaily}
                onChange={(e) => setForceDaily(e.target.checked)}
                disabled={Boolean(running)}
                className="accent-accent"
              />
              Force on weekends (<code className="text-accent">--force</code>)
            </label>
            <button
              type="button"
              disabled={Boolean(running)}
              onClick={() => runAction("daily", { force: forceDaily })}
              className="mt-2 px-2 py-0.5 rounded text-[10px] bg-accent text-white disabled:opacity-50 hover:opacity-90"
            >
              {running === "daily" ? "Running…" : "Daily run"}
            </button>
          </div>

          <div className={`rounded-lg border px-3 py-2 ${stepTone(status?.pipeline.review.status ?? null)}`}>
            <div className="text-[10px] uppercase opacity-80">5 · Review</div>
            <div className="text-xs mt-1 tabular-nums">
              {formatIstWhen(status?.pipeline.review.at ?? null)}
            </div>
            <p className="text-[10px] text-muted mt-1 leading-relaxed">
              Weekly LLM memo on open positions — read recommendations only; does not trade until
              you Apply.
            </p>
            <div className="flex flex-wrap gap-1 mt-2">
              <button
                type="button"
                disabled={Boolean(running)}
                onClick={() => runAction("review")}
                className="px-2 py-0.5 rounded text-[10px] bg-surface-2 border border-border disabled:opacity-50"
              >
                {running === "review" ? "…" : "Review"}
              </button>
              <button
                type="button"
                disabled={Boolean(running)}
                onClick={() => runAction("review-apply", { destructive: true })}
                className="px-2 py-0.5 rounded text-[10px] border border-bear/30 text-bear disabled:opacity-50"
              >
                {running === "review-apply" ? "…" : "Apply"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
