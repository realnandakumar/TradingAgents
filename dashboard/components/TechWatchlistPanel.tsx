"use client";

import { useCallback, useEffect, useState } from "react";

import { MarkdownViewer } from "@/components/MarkdownViewer";
import type { TickerReportMeta } from "@/lib/tech-reports-server";

interface WatchlistResponse {
  symbols: string[];
  path: string;
}

interface StatusReports {
  rows: TickerReportMeta[];
  fresh: number;
  stale: number;
  missing: number;
  maxAgeDays: number;
  reportsDir: string;
}

function freshnessClass(status: TickerReportMeta["status"]): string {
  if (status === "fresh") return "text-bull border-bull/30";
  if (status === "stale") return "text-accent border-accent/30";
  return "text-muted border-border";
}

function savedReportLabel(meta: TickerReportMeta | undefined, maxAge: number): string {
  if (!meta || meta.status === "missing") {
    return "No saved report in tech_reports/";
  }
  const age =
    meta.ageDays === 0
      ? "today"
      : meta.ageDays === 1
        ? "1 day ago"
        : `${meta.ageDays} days ago`;
  const status =
    meta.status === "fresh" ? "fresh" : meta.status === "stale" ? "stale" : "missing";
  return `Saved report ${meta.reportDate} (${age}) · ${status} (≤${maxAge}d for Process)`;
}

export function TechWatchlistPanel() {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [filePath, setFilePath] = useState("");
  const [reportsDir, setReportsDir] = useState("");
  const [reportMeta, setReportMeta] = useState<Map<string, TickerReportMeta>>(new Map());
  const [maxAgeDays, setMaxAgeDays] = useState(14);
  const [newTicker, setNewTicker] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [editText, setEditText] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [previewTicker, setPreviewTicker] = useState<string | null>(null);
  const [previewMd, setPreviewMd] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const loadReports = useCallback(async () => {
    const stRes = await fetch("/api/tech-desk/status");
    if (!stRes.ok) return;
    const st = (await stRes.json()) as { reports: StatusReports };
    const map = new Map<string, TickerReportMeta>();
    for (const row of st.reports.rows) map.set(row.ticker, row);
    setReportMeta(map);
    setMaxAgeDays(st.reports.maxAgeDays);
    setReportsDir(st.reports.reportsDir);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const wlRes = await fetch("/api/watchlist");
      const wl = (await wlRes.json()) as WatchlistResponse & { error?: string };
      if (!wlRes.ok) throw new Error(wl.error ?? "Failed to load watchlist");
      setSymbols(wl.symbols);
      setFilePath(wl.path);
      setEditText(wl.symbols.join("\n"));
      await loadReports();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  }, [loadReports]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const onRefresh = () => loadReports();
    window.addEventListener("tech-desk-refresh", onRefresh);
    return () => window.removeEventListener("tech-desk-refresh", onRefresh);
  }, [loadReports]);

  const flash = (msg: string) => {
    setMessage(msg);
    setTimeout(() => setMessage(null), 2500);
  };

  const addTicker = async () => {
    const raw = newTicker.trim();
    if (!raw) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/watchlist", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ add: [raw] }),
      });
      const data = (await res.json()) as WatchlistResponse & { error?: string };
      if (!res.ok) throw new Error(data.error ?? "Failed to add ticker");
      await load();
      setNewTicker("");
      flash("Added ticker");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add ticker");
    } finally {
      setSaving(false);
    }
  };

  const removeTicker = async (sym: string) => {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/watchlist", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ remove: [sym] }),
      });
      const data = (await res.json()) as WatchlistResponse & { error?: string };
      if (!res.ok) throw new Error(data.error ?? "Failed to remove ticker");
      await load();
      flash(`Removed ${sym}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove ticker");
    } finally {
      setSaving(false);
    }
  };

  const saveBulkEdit = async () => {
    const lines = editText
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith("#"));
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/watchlist", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbols: lines }),
      });
      const data = (await res.json()) as WatchlistResponse & { error?: string };
      if (!res.ok) throw new Error(data.error ?? "Failed to save watchlist");
      await load();
      setEditMode(false);
      flash(`Saved ${data.symbols.length} ticker(s)`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save watchlist");
    } finally {
      setSaving(false);
    }
  };

  const openReport = async (sym: string) => {
    setPreviewTicker(sym);
    setPreviewLoading(true);
    setPreviewMd(null);
    try {
      const res = await fetch(`/api/tech-desk/report?ticker=${encodeURIComponent(sym)}`);
      const data = await res.json();
      setPreviewMd(res.ok ? data.markdown : "No saved report found. Run Analyze first.");
    } catch {
      setPreviewMd("Failed to load report.");
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <section className="card p-4 sm:p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium">Watchlist</h2>
          <p className="text-xs text-muted mt-0.5 leading-relaxed">
            Edit which tickers belong on your Tech Desk list.{" "}
            <strong className="text-foreground/80">Report status</strong> comes from saved files
            in <code className="text-accent">tech_reports/</code> (analysis as-of date) — not from
            when you added the ticker here.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted tabular-nums">
            {loading ? "…" : `${symbols.length} ticker${symbols.length === 1 ? "" : "s"}`}
          </span>
          <button
            type="button"
            onClick={() => load()}
            disabled={loading || saving}
            className="px-2.5 py-1 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50"
          >
            Refresh reports
          </button>
          <button
            type="button"
            onClick={() => {
              setEditMode((v) => !v);
              setEditText(symbols.join("\n"));
            }}
            disabled={loading || saving}
            className="px-2.5 py-1 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50 hover:bg-surface-2/80"
          >
            {editMode ? "Cancel edit" : "Edit all"}
          </button>
        </div>
      </div>

      {filePath ? (
        <p className="text-[10px] font-mono text-muted truncate">Watchlist: {filePath}</p>
      ) : null}
      {reportsDir ? (
        <p className="text-[10px] font-mono text-muted truncate">Reports: {reportsDir}</p>
      ) : null}

      {message ? <p className="text-xs text-bull">{message}</p> : null}
      {error ? <p className="text-sm text-bear">{error}</p> : null}

      {editMode ? (
        <div className="space-y-3">
          <label className="block space-y-1.5">
            <span className="text-xs text-muted">One ticker per line</span>
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              rows={8}
              disabled={saving}
              className="w-full px-3 py-2 rounded-lg bg-surface-2 border border-border text-sm font-mono focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50 resize-y min-h-[120px]"
            />
          </label>
          <button
            type="button"
            onClick={saveBulkEdit}
            disabled={saving}
            className="px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium disabled:opacity-50 hover:opacity-90"
          >
            {saving ? "Saving…" : "Save watchlist"}
          </button>
        </div>
      ) : (
        <>
          <div className="space-y-2 min-h-[2rem]">
            {loading ? (
              <span className="text-sm text-muted">Loading…</span>
            ) : symbols.length === 0 ? (
              <span className="text-sm text-muted">No tickers yet — add symbols below</span>
            ) : (
              symbols.map((sym) => {
                const meta = reportMeta.get(sym.toUpperCase());
                return (
                  <div
                    key={sym}
                    className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2 border-b border-border/30 last:border-0"
                  >
                    <span
                      className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-surface-2 border text-xs font-mono ${freshnessClass(meta?.status ?? "missing")}`}
                    >
                      {sym}
                      <button
                        type="button"
                        onClick={() => removeTicker(sym)}
                        disabled={saving}
                        className="text-muted hover:text-bear disabled:opacity-50"
                        aria-label={`Remove ${sym}`}
                      >
                        ×
                      </button>
                    </span>
                    <span className="text-[11px] text-muted">
                      {meta && meta.status !== "missing" ? (
                        <button
                          type="button"
                          onClick={() => openReport(sym)}
                          className="hover:text-accent hover:underline text-left"
                        >
                          {savedReportLabel(meta, maxAgeDays)} · view report
                        </button>
                      ) : (
                        savedReportLabel(meta, maxAgeDays)
                      )}
                    </span>
                  </div>
                );
              })
            )}
          </div>

          <div className="flex flex-wrap gap-2 items-end">
            <label className="flex-1 min-w-[160px] space-y-1.5">
              <span className="text-xs text-muted">Add ticker</span>
              <input
                type="text"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addTicker();
                  }
                }}
                placeholder="SWIGGY or TCS.NS"
                disabled={saving}
                className="w-full px-3 py-2 rounded-lg bg-surface-2 border border-border text-sm font-mono focus:outline-none focus:ring-1 focus:ring-accent disabled:opacity-50"
              />
            </label>
            <button
              type="button"
              onClick={addTicker}
              disabled={saving || !newTicker.trim()}
              className="px-3 py-2 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50 hover:bg-surface-2/80"
            >
              Add
            </button>
          </div>
        </>
      )}

      {previewTicker ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
          <div className="card max-w-2xl w-full max-h-[85vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <h3 className="text-sm font-medium font-mono">{previewTicker} — saved report</h3>
              <button
                type="button"
                onClick={() => {
                  setPreviewTicker(null);
                  setPreviewMd(null);
                }}
                className="text-muted hover:text-foreground text-lg leading-none"
              >
                ×
              </button>
            </div>
            <div className="p-4 overflow-y-auto flex-1">
              {previewLoading ? (
                <p className="text-sm text-muted">Loading…</p>
              ) : previewMd ? (
                <MarkdownViewer text={previewMd} />
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
