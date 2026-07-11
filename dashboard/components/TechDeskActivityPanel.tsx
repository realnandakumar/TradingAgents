"use client";

import { useCallback, useEffect, useState } from "react";

import type { TechDeskStatus } from "@/lib/tech-desk-status-server";

export function TechDeskActivityPanel() {
  const [status, setStatus] = useState<TechDeskStatus | null>(null);

  const load = useCallback(async () => {
    const res = await fetch("/api/tech-desk/status");
    if (res.ok) setStatus((await res.json()) as TechDeskStatus);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const process = status?.latestProcess;
  const daily = status?.latestDaily;

  if (!process && !daily) return null;

  return (
    <section className="card p-4 sm:p-5 space-y-4">
      <h2 className="text-sm font-medium">Recent activity</h2>

      {process ? (
        <div className="text-xs space-y-1">
          <div className="text-muted uppercase tracking-wide text-[10px]">Last process</div>
          <div className="font-mono text-muted">
            Date {String(process.date ?? "—")} · opened{" "}
            {Array.isArray(process.opened) ? process.opened.length : 0} · waits{" "}
            {Array.isArray(process.waits) ? process.waits.length : 0} · closes{" "}
            {Array.isArray(process.closes) ? process.closes.length : 0}
            {Array.isArray(process.pending_replacements) &&
            (process.pending_replacements as unknown[]).length > 0
              ? ` · replacements ${(process.pending_replacements as unknown[]).length}`
              : ""}{" "}
            · open {String(process.open_positions ?? "—")}
          </div>
          {Array.isArray(process.stale_tickers) && process.stale_tickers.length > 0 ? (
            <div className="text-bear/90">
              Stale reports skipped: {(process.stale_tickers as string[]).join(", ")}
            </div>
          ) : null}
        </div>
      ) : null}

      {daily ? (
        <div className="text-xs space-y-1 border-t border-border pt-3">
          <div className="text-muted uppercase tracking-wide text-[10px]">Last daily</div>
          <div className="font-mono text-muted">
            Date {String(daily.date ?? "—")} · exits{" "}
            {Array.isArray(daily.exits) ? daily.exits.length : 0} · zone fills{" "}
            {Array.isArray(daily.zone_fills) ? daily.zone_fills.length : 0} · open{" "}
            {String(daily.open_positions ?? "—")} · pending{" "}
            {String(daily.pending_entries ?? "—")}
          </div>
        </div>
      ) : null}
    </section>
  );
}
