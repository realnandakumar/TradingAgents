"use client";

export const DESK_JOB_STARTED_EVENT = "desk-cli-job-started";

const ACTIVE_JOB_KEY = "desk-cli-active-job";
const DISMISSED_JOB_KEY = "desk-cli-dismissed-job";

export interface DeskJobStartedDetail {
  jobId: string;
  deskId: string;
  actionId: string;
}

export function notifyDeskJobStarted(
  jobId: string,
  deskId: string,
  actionId: string,
): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(ACTIVE_JOB_KEY, jobId);
    sessionStorage.removeItem(DISMISSED_JOB_KEY);
  } catch {
    /* ignore */
  }
  window.dispatchEvent(
    new CustomEvent<DeskJobStartedDetail>(DESK_JOB_STARTED_EVENT, {
      detail: { jobId, deskId, actionId },
    }),
  );
}

export function getTrackedJobId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return sessionStorage.getItem(ACTIVE_JOB_KEY);
  } catch {
    return null;
  }
}

export function clearTrackedJobId(): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(ACTIVE_JOB_KEY);
    sessionStorage.removeItem(DISMISSED_JOB_KEY);
  } catch {
    /* ignore */
  }
}

export function dismissDeskJob(jobId: string): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(DISMISSED_JOB_KEY, jobId);
  } catch {
    /* ignore */
  }
}

export function getDismissedJobId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return sessionStorage.getItem(DISMISSED_JOB_KEY);
  } catch {
    return null;
  }
}
