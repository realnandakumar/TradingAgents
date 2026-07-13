"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { JobProgress, ReportMeta } from "@/lib/analyze-server";

const ANALYST_OPTIONS = [
  { key: "market", label: "Market" },
  { key: "social", label: "Sentiment" },
  { key: "news", label: "News" },
  { key: "fundamentals", label: "Fundamentals" },
];

const DEPTH_OPTIONS = [
  { value: 1, label: "Shallow (1 round)" },
  { value: 3, label: "Medium (3 rounds)" },
  { value: 5, label: "Deep (5 rounds)" },
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function statusColor(status: string): string {
  if (status === "completed") return "text-bull";
  if (status === "in_progress") return "text-accent";
  if (status === "failed") return "text-bear";
  return "text-muted";
}

function SimpleMarkdown({ text }: { text: string }) {
  const blocks = useMemo(() => {
    const lines = text.split("\n");
    const out: { type: "h1" | "h2" | "h3" | "p"; content: string }[] = [];
    let buf: string[] = [];

    const flush = () => {
      if (buf.length) {
        out.push({ type: "p", content: buf.join("\n") });
        buf = [];
      }
    };

    for (const line of lines) {
      if (line.startsWith("# ")) {
        flush();
        out.push({ type: "h1", content: line.slice(2) });
      } else if (line.startsWith("## ")) {
        flush();
        out.push({ type: "h2", content: line.slice(3) });
      } else if (line.startsWith("### ")) {
        flush();
        out.push({ type: "h3", content: line.slice(4) });
      } else {
        buf.push(line);
      }
    }
    flush();
    return out;
  }, [text]);

  return (
    <div className="space-y-4 text-sm leading-relaxed">
      {blocks.map((b, i) => {
        if (b.type === "h1")
          return (
            <h2 key={i} className="text-lg font-semibold text-foreground">
              {b.content}
            </h2>
          );
        if (b.type === "h2")
          return (
            <h3 key={i} className="text-base font-medium text-accent mt-6">
              {b.content}
            </h3>
          );
        if (b.type === "h3")
          return (
            <h4 key={i} className="text-sm font-medium text-foreground mt-4">
              {b.content}
            </h4>
          );
        return (
          <pre
            key={i}
            className="whitespace-pre-wrap font-sans text-muted text-sm"
          >
            {b.content}
          </pre>
        );
      })}
    </div>
  );
}

interface Props {
  initialReports: ReportMeta[];
}

export function AnalyzePanel({ initialReports }: Props) {
  const [tickers, setTickers] = useState<string[]>([]);
  const [tickerQuery, setTickerQuery] = useState("");
  const [ticker, setTicker] = useState("");
  const [analysisDate, setAnalysisDate] = useState(todayIso);
  const [researchDepth, setResearchDepth] = useState(1);
  const [analysts, setAnalysts] = useState<string[]>(
    ANALYST_OPTIONS.map((a) => a.key),
  );
  const [reports, setReports] = useState<ReportMeta[]>(initialReports);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [reportMarkdown, setReportMarkdown] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<JobProgress | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiWarning, setApiWarning] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    fetch("/api/env/status")
      .then((r) => r.json())
      .then((d: { apiKey?: { configured: boolean; message: string } }) => {
        if (d.apiKey && !d.apiKey.configured) setApiWarning(d.apiKey.message);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetch("/api/tickers")
      .then((r) => r.json())
      .then((d: { tickers?: string[] }) => setTickers(d.tickers ?? []))
      .catch(() => setTickers([]));
  }, []);

  const filteredTickers = useMemo(() => {
    const q = tickerQuery.trim().toUpperCase();
    if (!q) return tickers.slice(0, 30);
    return tickers.filter((t) => t.includes(q)).slice(0, 30);
  }, [tickers, tickerQuery]);

  const refreshReports = useCallback(async () => {
    const res = await fetch("/api/analyze/reports");
    if (!res.ok) return;
    const data = (await res.json()) as { reports: ReportMeta[] };
    setReports(data.reports);
  }, []);

  const loadReport = useCallback(async (id: string) => {
    setSelectedReportId(id);
    const res = await fetch(`/api/analyze/reports/${encodeURIComponent(id)}`);
    if (!res.ok) {
      setReportMarkdown(null);
      return;
    }
    const data = (await res.json()) as { markdown: string };
    setReportMarkdown(data.markdown);
  }, []);

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
          const res = await fetch(`/api/analyze?jobId=${encodeURIComponent(id)}`);
          if (!res.ok) return;
          const data = (await res.json()) as { progress: JobProgress };
          setProgress(data.progress);
          if (data.progress.status === "completed" || data.progress.status === "failed") {
            stopPolling();
            setRunning(false);
            await refreshReports();
            if (data.progress.reportId) {
              await loadReport(data.progress.reportId);
            }
          }
        } catch {
          /* keep polling */
        }
      }, 2000);
    },
    [loadReport, refreshReports, stopPolling],
  );

  useEffect(() => () => stopPolling(), [stopPolling]);

  const toggleAnalyst = (key: string) => {
    setAnalysts((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };

  const runAnalysis = async () => {
    const sym = (ticker || tickerQuery).trim().toUpperCase();
    if (!sym) {
      setError("Enter a ticker symbol");
      return;
    }
    if (analysts.length === 0) {
      setError("Select at least one analyst");
      return;
    }

    setError(null);
    setRunning(true);
    setProgress(null);
    setJobId(null);
    setReportMarkdown(null);
    setSelectedReportId(null);

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: sym,
          analysisDate,
          researchDepth,
          analysts,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error ?? "Failed to start analysis");
      }
      setJobId(data.jobId);
      pollJob(data.jobId);
    } catch (e) {
      setRunning(false);
      setError(e instanceof Error ? e.message : "Failed to start analysis");
    }
  };

  return (
    <div className="space-y-4">
      {apiWarning ? (
        <div className="rounded-lg border border-bear/40 bg-bear/5 px-4 py-3 text-sm text-bear">
          {apiWarning}
        </div>
      ) : null}
      <p className="text-xs text-muted">
        Full multi-agent research pipeline. For watchlist technical reports used by Tech Desk, see{" "}
        <a href="/tech-desk" className="text-accent hover:underline">
          Tech desk
        </a>
        .
      </p>
    <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
      {/* Saved reports sidebar */}
      <aside className="card p-4 h-fit lg:sticky lg:top-20">
        <h2 className="text-xs font-medium uppercase tracking-wide text-muted mb-3">
          Saved reports
        </h2>
        {reports.length === 0 ? (
          <p className="text-sm text-muted">No reports yet. Run an analysis to save one.</p>
        ) : (
          <ul className="space-y-1 max-h-[420px] overflow-y-auto">
            {reports.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => loadReport(r.id)}
                  className={`w-full text-left px-2 py-1.5 rounded-lg text-sm transition-colors ${
                    selectedReportId === r.id
                      ? "bg-surface-2 text-foreground"
                      : "text-muted hover:text-foreground hover:bg-surface-2/60"
                  }`}
                >
                  <div className="font-mono text-xs">{r.ticker}</div>
                  <div className="text-[10px] text-muted">
                    {new Date(r.createdAt).toLocaleString()}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      <div className="space-y-6">
        {/* Run form */}
        <section className="card p-5 space-y-4">
          <h2 className="text-sm font-medium">New analysis</h2>

          <div className="grid sm:grid-cols-2 gap-4">
            <label className="block space-y-1.5">
              <span className="text-xs text-muted">Ticker</span>
              <input
                type="text"
                list="ticker-suggestions"
                value={tickerQuery}
                onChange={(e) => {
                  setTickerQuery(e.target.value);
                  setTicker(e.target.value);
                }}
                placeholder="RELIANCE.NS or AAPL"
                className="w-full px-3 py-2 rounded-lg bg-surface-2 border border-border text-sm font-mono focus:outline-none focus:ring-1 focus:ring-accent"
              />
              <datalist id="ticker-suggestions">
                {filteredTickers.map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
            </label>

            <label className="block space-y-1.5">
              <span className="text-xs text-muted">Analysis date</span>
              <input
                type="date"
                value={analysisDate}
                max={todayIso()}
                onChange={(e) => setAnalysisDate(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-surface-2 border border-border text-sm focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </label>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <label className="block space-y-1.5">
              <span className="text-xs text-muted">Research depth</span>
              <select
                value={researchDepth}
                onChange={(e) => setResearchDepth(Number(e.target.value))}
                className="w-full px-3 py-2 rounded-lg bg-surface-2 border border-border text-sm focus:outline-none focus:ring-1 focus:ring-accent"
              >
                {DEPTH_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>

            <fieldset className="space-y-1.5">
              <legend className="text-xs text-muted">Analysts</legend>
              <div className="flex flex-wrap gap-2">
                {ANALYST_OPTIONS.map((a) => (
                  <label
                    key={a.key}
                    className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-md bg-surface-2 border border-border cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={analysts.includes(a.key)}
                      onChange={() => toggleAnalyst(a.key)}
                      className="accent-accent"
                    />
                    {a.label}
                  </label>
                ))}
              </div>
            </fieldset>
          </div>

          {error ? <p className="text-sm text-bear">{error}</p> : null}

          <button
            type="button"
            onClick={runAnalysis}
            disabled={running}
            className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium disabled:opacity-50 hover:opacity-90 transition-opacity"
          >
            {running ? "Running analysis…" : "Run analysis"}
          </button>
        </section>

        {/* Live progress */}
        {(running || progress) && (
          <section className="card p-5 space-y-4">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-sm font-medium">Progress</h2>
              {jobId ? (
                <span className="text-[10px] font-mono text-muted truncate">{jobId}</span>
              ) : null}
            </div>

            {progress ? (
              <>
                <div className="space-y-2">
                  <div className="flex justify-between text-xs text-muted">
                    <span className="capitalize">{progress.stage}</span>
                    <span>{progress.percent}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-surface-2 overflow-hidden">
                    <div
                      className="h-full bg-accent transition-all duration-500"
                      style={{ width: `${progress.percent}%` }}
                    />
                  </div>
                </div>

                {progress.decision ? (
                  <div className="p-3 rounded-lg bg-surface-2 border border-border">
                    <div className="text-xs text-muted mb-1">Final decision</div>
                    <div className="text-sm font-medium">{progress.decision}</div>
                  </div>
                ) : null}

                {progress.error ? (
                  <p className="text-sm text-bear">{progress.error}</p>
                ) : null}

                {Object.keys(progress.agentStatus).length > 0 ? (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {Object.entries(progress.agentStatus).map(([agent, status]) => (
                      <div
                        key={agent}
                        className="text-[11px] px-2 py-1 rounded bg-surface-2 border border-border"
                      >
                        <span className="text-muted">{agent}: </span>
                        <span className={statusColor(status)}>{status}</span>
                      </div>
                    ))}
                  </div>
                ) : null}

                {progress.messages.length > 0 ? (
                  <div className="max-h-48 overflow-y-auto rounded-lg bg-surface-2 border border-border p-3 font-mono text-[11px] space-y-1">
                    {progress.messages.map((m, i) => (
                      <div key={i} className="text-muted">
                        <span className="text-foreground/60">{m.time}</span>{" "}
                        <span className="text-accent">[{m.type}]</span> {m.content}
                      </div>
                    ))}
                  </div>
                ) : null}
              </>
            ) : (
              <p className="text-sm text-muted">Starting job…</p>
            )}
          </section>
        )}

        {/* Report viewer */}
        {reportMarkdown ? (
          <section className="card p-5">
            <h2 className="text-sm font-medium mb-4">Report</h2>
            <SimpleMarkdown text={reportMarkdown} />
          </section>
        ) : null}
      </div>
    </div>
    </div>
  );
}
