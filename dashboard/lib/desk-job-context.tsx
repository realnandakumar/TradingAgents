"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { DESK_JOB_STARTED_EVENT } from "@/lib/desk-cli-events";

interface ActiveJobState {
  jobId: string;
  deskId: string;
  actionId: string;
  status: string;
}

interface DeskJobContextValue {
  activeJob: ActiveJobState | null;
  isJobRunning: boolean;
  refresh: () => void;
}

const DeskJobContext = createContext<DeskJobContextValue>({
  activeJob: null,
  isJobRunning: false,
  refresh: () => {},
});

export function DeskJobProvider({ children }: { children: ReactNode }) {
  const [activeJob, setActiveJob] = useState<ActiveJobState | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/desk-cli/active", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      if (data.mode === "active") {
        setActiveJob({
          jobId: data.jobId,
          deskId: data.deskId,
          actionId: data.actionId,
          status: data.status,
        });
      } else {
        setActiveJob(null);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 2000);
    const onStarted = () => refresh();
    window.addEventListener(DESK_JOB_STARTED_EVENT, onStarted);
    return () => {
      clearInterval(id);
      window.removeEventListener(DESK_JOB_STARTED_EVENT, onStarted);
    };
  }, [refresh]);

  const value = useMemo(
    () => ({
      activeJob,
      isJobRunning: activeJob?.status === "running" || activeJob?.status === "pending",
      refresh,
    }),
    [activeJob, refresh],
  );

  return <DeskJobContext.Provider value={value}>{children}</DeskJobContext.Provider>;
}

export function useDeskJob() {
  return useContext(DeskJobContext);
}
