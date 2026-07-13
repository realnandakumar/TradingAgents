"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  DESK_JOB_STARTED_EVENT,
  dismissDeskJob,
  getDismissedJobId,
} from "@/lib/desk-cli-events";
import type { PlainJobStatus } from "@/lib/desk-job-status";

interface ActivePayload {
  mode: "active" | "recent";
  jobId: string;
  deskId: string;
  actionId: string;
  status: string;
  plain: PlainJobStatus;
}

const DESK_PATHS: Record<string, string> = {
  swing: "/swing",
  momentum: "/momentum",
  nss: "/nss",
  "supertrend-rsi": "/supertrend-rsi",
  trama: "/trama",
  "gap-fill": "/gap-fill",
  "nw-envelope": "/nw-envelope",
  "pattern-forecast": "/pattern-forecast",
  "tech-desk": "/tech-desk",
  "control-center": "/command-center",
  positions: "/positions",
  screens: "/screens",
  "gap-screener": "/gap-fill",
  "chart-patterns": "/chart-patterns",
};

function barTone(phase: PlainJobStatus["phase"]): string {
  if (phase === "success") return "border-bull/50 bg-bull/10";
  if (phase === "failed") return "border-bear/50 bg-bear/10";
  return "border-accent/50 bg-accent/10";
}

function dotTone(phase: PlainJobStatus["phase"]): string {
  if (phase === "success") return "bg-bull";
  if (phase === "failed") return "bg-bear";
  return "bg-accent animate-pulse";
}

export function DeskJobStatusBar() {
  const pathname = usePathname();
  const [payload, setPayload] = useState<ActivePayload | null>(null);
  const [expanded, setExpanded] = useState(false);
  const dismissTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearDismissTimer = useCallback(() => {
    if (dismissTimer.current) {
      clearTimeout(dismissTimer.current);
      dismissTimer.current = null;
    }
  }, []);

  const scheduleDismiss = useCallback(
    (ms: number) => {
      clearDismissTimer();
      dismissTimer.current = setTimeout(() => {
        setPayload(null);
        setExpanded(false);
      }, ms);
    },
    [clearDismissTimer],
  );

  const poll = useCallback(async () => {
    try {
      const res = await fetch("/api/desk-cli/active", { cache: "no-store" });
      if (!res.ok) return;
      const data = (await res.json()) as ActivePayload | { mode: "idle" };

      if (data.mode === "idle") {
        setPayload(null);
        return;
      }

      if (getDismissedJobId() === data.jobId) {
        setPayload(null);
        return;
      }

      setPayload(data);
      clearDismissTimer();

      if (data.mode === "recent") {
        scheduleDismiss(data.plain.phase === "failed" ? 14_000 : 9_000);
      }
    } catch {
      /* keep polling */
    }
  }, [clearDismissTimer, scheduleDismiss]);

  useEffect(() => {
    poll();
    pollRef.current = setInterval(poll, 2000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      clearDismissTimer();
    };
  }, [poll, clearDismissTimer]);

  useEffect(() => {
    const onStarted = () => {
      clearDismissTimer();
      poll();
    };
    window.addEventListener(DESK_JOB_STARTED_EVENT, onStarted);
    return () => window.removeEventListener(DESK_JOB_STARTED_EVENT, onStarted);
  }, [clearDismissTimer, poll]);

  if (!payload) return null;

  const { plain, deskId, jobId } = payload;
  const deskHref = DESK_PATHS[deskId];
  const onDeskPage =
    deskHref &&
    (pathname === deskHref || (deskHref !== "/" && pathname.startsWith(deskHref)));

  const dismiss = () => {
    clearDismissTimer();
    dismissDeskJob(jobId);
    setPayload(null);
    setExpanded(false);
  };

  return (
    <div
      className={`sticky top-14 z-20 border-b ${barTone(plain.phase)}`}
      role="status"
      aria-live="polite"
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-2.5 flex items-start gap-3">
        <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${dotTone(plain.phase)}`} />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="text-sm font-medium">{plain.headline}</span>
            {plain.phase === "running" ? (
              <span className="text-[10px] tabular-nums text-muted">{plain.percent}%</span>
            ) : null}
            {deskHref && !onDeskPage ? (
              <Link
                href={deskHref}
                className="text-[10px] text-accent hover:underline"
              >
                Open desk
              </Link>
            ) : null}
          </div>
          <p className={`text-xs text-muted mt-0.5 ${expanded ? "" : "line-clamp-1"}`}>
            {plain.detail}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {plain.detail.length > 72 ? (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="text-[10px] text-muted hover:text-foreground"
            >
              {expanded ? "Less" : "More"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={dismiss}
            className="text-[10px] text-muted hover:text-foreground px-1.5"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      </div>

      {plain.phase === "running" ? (
        <div className="h-0.5 bg-surface-2">
          <div
            className="h-full bg-accent transition-all duration-500"
            style={{ width: `${Math.max(plain.percent, 4)}%` }}
          />
        </div>
      ) : null}
    </div>
  );
}
