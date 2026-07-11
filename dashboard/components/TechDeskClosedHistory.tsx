"use client";

import { useMemo, useState } from "react";

import { DeskClosedLedger } from "@/components/DeskClosedLedger";
import { inr } from "@/lib/format";
import type { TechDeskPosition } from "@/lib/tech-desk-server";

type Preset = "all" | "30d" | "90d" | "ytd" | "custom";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function offsetDate(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function yearStart(): string {
  const y = new Date().getFullYear();
  return `${y}-01-01`;
}

function inRange(exitDate: string | null | undefined, from: string, to: string): boolean {
  if (!exitDate) return false;
  return exitDate >= from && exitDate <= to;
}

export function TechDeskClosedHistory({ trades }: { trades: TechDeskPosition[] }) {
  const [preset, setPreset] = useState<Preset>("all");
  const [fromDate, setFromDate] = useState(offsetDate(90));
  const [toDate, setToDate] = useState(todayIso());

  const range = useMemo(() => {
    if (preset === "all") return { from: "1970-01-01", to: todayIso() };
    if (preset === "30d") return { from: offsetDate(30), to: todayIso() };
    if (preset === "90d") return { from: offsetDate(90), to: todayIso() };
    if (preset === "ytd") return { from: yearStart(), to: todayIso() };
    return { from: fromDate, to: toDate };
  }, [preset, fromDate, toDate]);

  const filtered = useMemo(
    () => trades.filter((t) => inRange(t.exit_date, range.from, range.to)),
    [trades, range.from, range.to],
  );

  const summary = useMemo(() => {
    if (filtered.length === 0) {
      return { count: 0, wins: 0, totalPnl: 0 };
    }
    const wins = filtered.filter((t) => (t.raw_return ?? 0) > 0).length;
    const totalPnl = filtered.reduce((s, t) => s + (t.rupee_pnl ?? 0), 0);
    return { count: filtered.length, wins, totalPnl };
  }, [filtered]);

  return (
    <section className="card mx-4 sm:mx-6 mt-4 mb-6 p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium">Closed trade history</h2>
          <p className="text-xs text-muted mt-0.5">
            Permanent archive of every closed Tech Desk paper trade ({trades.length} total).
          </p>
        </div>
        <div className="text-xs text-muted text-right tabular-nums">
          <div>
            {summary.count} in range · win{" "}
            {summary.count ? Math.round((100 * summary.wins) / summary.count) : 0}%
          </div>
          <div>P&amp;L {inr(summary.totalPnl)}</div>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <fieldset className="space-y-1">
          <legend className="text-[10px] uppercase text-muted tracking-wide">Period</legend>
          <div className="flex flex-wrap gap-1">
            {(
              [
                ["all", "All time"],
                ["30d", "Last 30d"],
                ["90d", "Last 90d"],
                ["ytd", "YTD"],
                ["custom", "Custom"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setPreset(id)}
                className={`px-2.5 py-1 rounded-md text-xs border ${
                  preset === id
                    ? "bg-accent/15 border-accent/40 text-accent"
                    : "bg-surface-2 border-border text-muted hover:text-foreground"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </fieldset>

        {preset === "custom" ? (
          <>
            <label className="space-y-1 text-xs">
              <span className="text-muted">From</span>
              <input
                type="date"
                value={fromDate}
                max={toDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="block px-2 py-1 rounded bg-surface-2 border border-border font-mono"
              />
            </label>
            <label className="space-y-1 text-xs">
              <span className="text-muted">To</span>
              <input
                type="date"
                value={toDate}
                min={fromDate}
                max={todayIso()}
                onChange={(e) => setToDate(e.target.value)}
                className="block px-2 py-1 rounded bg-surface-2 border border-border font-mono"
              />
            </label>
          </>
        ) : (
          <p className="text-[11px] text-muted font-mono pb-1">
            {range.from} → {range.to}
          </p>
        )}
      </div>

      <DeskClosedLedger positions={filtered} showAlpha={false} />
    </section>
  );
}
