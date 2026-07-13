"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

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

export function TechDeskPipelineCard() {
  const [status, setStatus] = useState<TechDeskStatus | null>(null);
  const [loading, setLoading] = useState(true);

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

  const pnl = status?.pnl;
  const next = status?.nextAction;
  const processSummary = status?.latestProcess;

  return (
    <section className="card p-4 sm:p-5 space-y-4">
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
              <div
                className={`font-medium tabular-nums ${pnl.realized30d >= 0 ? "text-bull" : "text-bear"}`}
              >
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

      {next ? (
        <div
          className={`rounded-lg border px-3 py-2 text-xs flex flex-wrap items-center gap-2 ${
            next.tone === "bull"
              ? "border-bull/30 bg-bull/5 text-bull"
              : next.tone === "bear"
                ? "border-bear/30 bg-bear/5 text-bear"
                : next.tone === "accent"
                  ? "border-accent/30 bg-accent/5 text-accent"
                  : "border-border text-muted"
          }`}
        >
          <span>
            <span className="font-medium">Next: </span>
            {next.message}
          </span>
          <Link href="#desk-commands" className="text-accent underline hover:no-underline">
            Run in Desk commands →
          </Link>
        </div>
      ) : null}

      <div className="space-y-2">
        <div className="text-[10px] uppercase tracking-wide text-muted">
          Pipeline status · use Desk commands below to run steps
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-2">
          <div className={`rounded-lg border px-3 py-2 ${stepTone(null)}`}>
            <div className="text-[10px] uppercase opacity-80">Watchlist</div>
            <div className="text-xs mt-1">{loading ? "…" : `${status?.watchlist.count ?? 0} tickers`}</div>
            <div className="text-[10px] text-muted mt-0.5">
              {status?.reports.fresh ?? 0} fresh · {status?.reports.stale ?? 0} stale
            </div>
          </div>
          <div className={`rounded-lg border px-3 py-2 ${stepTone(status?.pipeline.analyze.status ?? null)}`}>
            <div className="text-[10px] uppercase opacity-80">Analyze</div>
            <div className="text-xs mt-1 tabular-nums">
              {formatIstWhen(status?.pipeline.analyze.at ?? null)}
            </div>
          </div>
          <div className={`rounded-lg border px-3 py-2 ${stepTone(status?.pipeline.process.status ?? null)}`}>
            <div className="text-[10px] uppercase opacity-80">Process</div>
            <div className="text-xs mt-1 tabular-nums">
              {formatIstWhen(status?.pipeline.process.at ?? null)}
            </div>
            {processSummary ? (
              <div className="text-[10px] text-muted mt-0.5">
                opened {Array.isArray(processSummary.opened) ? processSummary.opened.length : 0}
              </div>
            ) : null}
          </div>
          <div
            className={`rounded-lg border px-3 py-2 ${stepTone(status?.pipeline.daily.status ?? null)} ${
              status?.dailyOps.dailyDue ? "ring-1 ring-accent/50" : ""
            }`}
          >
            <div className="text-[10px] uppercase opacity-80">Daily</div>
            <div className="text-xs mt-1">Last: {status?.dailyOps.lastDailyDate ?? "Never"}</div>
            {status?.dailyOps.dailyDue ? (
              <span className="text-[9px] text-accent">Due today</span>
            ) : null}
          </div>
          <div className={`rounded-lg border px-3 py-2 ${stepTone(status?.pipeline.review.status ?? null)}`}>
            <div className="text-[10px] uppercase opacity-80">Review</div>
            <div className="text-xs mt-1 tabular-nums">
              {formatIstWhen(status?.pipeline.review.at ?? null)}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
