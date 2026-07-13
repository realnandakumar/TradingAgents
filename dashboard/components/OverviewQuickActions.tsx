"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { notifyDeskJobStarted } from "@/lib/desk-cli-events";
import { useDeskJob } from "@/lib/desk-job-context";

const ACTIONS = [
  { deskId: "control-center", actionId: "eod-sync-now", label: "Sync now", primary: true },
  { deskId: "control-center", actionId: "all-dailies", label: "All dailies", primary: false },
  { deskId: "positions", actionId: "screen", label: "RS screen", primary: true },
  { deskId: "positions", actionId: "paper", label: "Refresh RS paper", primary: false },
] as const;

export function OverviewQuickActions() {
  const router = useRouter();
  const { isJobRunning } = useDeskJob();
  const [running, setRunning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (deskId: string, actionId: string) => {
    if (isJobRunning || running) return;
    setError(null);
    setRunning(actionId);
    try {
      const res = await fetch("/api/desk-cli", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deskId, actionId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to start");
      notifyDeskJobStarted(data.jobId, deskId, actionId);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start");
    } finally {
      setRunning(null);
    }
  };

  return (
    <section className="card p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
        <div>
          <h2 className="text-sm font-medium">Quick actions</h2>
          <p className="text-xs text-muted mt-0.5">
            Run common jobs from the dashboard — progress shows in the status bar above.
          </p>
        </div>
        <Link href="/command-center" className="text-xs text-accent hover:underline shrink-0">
          Full command center →
        </Link>
      </div>
      <div className="flex flex-wrap gap-2">
        {ACTIONS.map((a) => (
          <button
            key={a.actionId}
            type="button"
            disabled={Boolean(running) || isJobRunning}
            onClick={() => run(a.deskId, a.actionId)}
            className={
              a.primary
                ? "px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium disabled:opacity-50"
                : "px-3 py-1.5 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50"
            }
          >
            {running === a.actionId ? "Starting…" : a.label}
          </button>
        ))}
      </div>
      {error ? <p className="text-sm text-bear mt-2">{error}</p> : null}
    </section>
  );
}
