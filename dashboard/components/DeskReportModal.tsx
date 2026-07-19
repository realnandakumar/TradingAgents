"use client";

import { useEffect, useState } from "react";

import { MarkdownViewer } from "@/components/MarkdownViewer";
import { shortSymbol } from "@/lib/format";
import type { PmLevels, TraderReport } from "@/lib/tech-reports-server";

type TabId = "ma" | "trader" | "levels";

export interface DeskReportTarget {
  ticker: string;
  reportDate?: string | null;
  reportPath?: string | null;
}

function fmt(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return String(n);
}

function LevelsTable({ levels }: { levels: PmLevels }) {
  const rows: [string, string][] = [
    ["Proposal", levels.proposal != null ? String(levels.proposal) : "—"],
    ["Bias", levels.bias != null ? String(levels.bias) : "—"],
    ["Confidence", fmt(levels.confidence as number | null)],
    [
      "Entry zone",
      levels.entry_zone_low != null && levels.entry_zone_high != null
        ? `${levels.entry_zone_low}–${levels.entry_zone_high}`
        : "—",
    ],
    ["Stop", fmt(levels.stop as number | null)],
    ["Target 1", fmt(levels.target_1 as number | null)],
    ["Target 2", fmt(levels.target_2 as number | null)],
    ["ATR", fmt(levels.atr as number | null)],
    ["50 SMA", fmt(levels.sma_50 as number | null)],
    ["200 SMA", fmt(levels.sma_200 as number | null)],
    ["Support", levels.key_support != null ? String(levels.key_support) : "—"],
    ["Resistance", levels.key_resistance != null ? String(levels.key_resistance) : "—"],
    ["Invalidation", levels.invalidation != null ? String(levels.invalidation) : "—"],
  ];
  return (
    <table className="w-full text-xs font-mono">
      <tbody>
        {rows.map(([k, v]) => (
          <tr key={k} className="border-b border-border/40">
            <td className="py-1.5 pr-3 text-muted whitespace-nowrap">{k}</td>
            <td className="py-1.5 text-foreground">{v}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TraderPanel({ trader }: { trader: TraderReport }) {
  if (trader.markdown) {
    return <MarkdownViewer text={trader.markdown} />;
  }
  const zone =
    trader.zone_low != null && trader.zone_high != null
      ? `${trader.zone_low}–${trader.zone_high}`
      : "—";
  return (
    <div className="space-y-3 text-sm">
      <div className="text-xs font-mono text-muted">
        Source: {trader.source ?? "—"}
        {trader.process_date ? ` · process ${trader.process_date}` : ""}
      </div>
      <div className="text-base font-medium">
        Disposition:{" "}
        <span className="text-accent uppercase">{trader.disposition}</span>
      </div>
      {trader.disposition === "skip" ? (
        <p className="text-muted leading-relaxed">{trader.skip_reason ?? "—"}</p>
      ) : (
        <LevelsTable
          levels={{
            proposal: trader.disposition,
            bias: trader.bias ?? undefined,
            confidence: trader.confidence,
            entry_zone_low: trader.zone_low,
            entry_zone_high: trader.zone_high,
            stop: trader.stop_loss,
            target_1: trader.target_1,
            target_2: trader.target_2,
            invalidation: trader.invalidation,
          }}
        />
      )}
      {trader.reward_risk != null ? (
        <p className="text-xs font-mono text-muted">R:R (zone mid): {trader.reward_risk}</p>
      ) : null}
      {trader.rationale ? (
        <div>
          <div className="text-[10px] uppercase text-muted mb-1">Rationale</div>
          <p className="text-muted leading-relaxed">{trader.rationale}</p>
        </div>
      ) : null}
      {trader.disposition !== "skip" ? (
        <p className="text-xs text-muted font-mono">Zone {zone}</p>
      ) : null}
    </div>
  );
}

export function DeskReportModal({
  target,
  onClose,
  initialTab = "ma",
}: {
  target: DeskReportTarget | null;
  onClose: () => void;
  initialTab?: TabId;
}) {
  const [tab, setTab] = useState<TabId>(initialTab);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [narrative, setNarrative] = useState<string | null>(null);
  const [levels, setLevels] = useState<PmLevels | null>(null);
  const [trader, setTrader] = useState<TraderReport | null>(null);
  const [date, setDate] = useState<string | null>(null);

  useEffect(() => {
    if (!target) return;
    setTab(initialTab);
    setLoading(true);
    setError(null);
    setNarrative(null);
    setLevels(null);
    setTrader(null);
    setDate(null);

    const params = new URLSearchParams({ ticker: target.ticker });
    if (target.reportDate) params.set("date", target.reportDate);
    if (target.reportPath) params.set("path", target.reportPath);

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/tech-desk/report?${params.toString()}`);
        const data = await res.json();
        if (cancelled) return;
        if (!res.ok) {
          setError(data.error ?? "Report not found");
          return;
        }
        setNarrative(typeof data.narrative === "string" ? data.narrative : data.markdown);
        setLevels(data.levels ?? null);
        setTrader(data.trader ?? null);
        setDate(data.date ?? target.reportDate ?? null);
        // Prefer trader tab when MA missing but trader exists
        if (!data.narrative && !data.markdown && data.trader) {
          setTab("trader");
        }
      } catch {
        if (!cancelled) setError("Failed to load report.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [target, initialTab]);

  if (!target) return null;

  const tabs: { id: TabId; label: string }[] = [
    { id: "ma", label: "MA" },
    { id: "trader", label: "Trader" },
    { id: "levels", label: "Levels" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="card max-w-2xl w-full max-h-[85vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-border">
          <div>
            <h3 className="text-sm font-medium font-mono">
              {shortSymbol(target.ticker)}
              {date ? ` · ${date}` : ""}
            </h3>
            <div className="flex gap-1 mt-2">
              {tabs.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTab(t.id)}
                  className={`px-2.5 py-1 text-[11px] font-mono rounded-md border ${
                    tab === t.id
                      ? "border-accent text-accent bg-accent/10"
                      : "border-border text-muted hover:text-foreground"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-muted hover:text-foreground text-lg leading-none"
          >
            ×
          </button>
        </div>
        <div className="p-4 overflow-y-auto flex-1">
          {loading ? (
            <p className="text-sm text-muted">Loading…</p>
          ) : error && !narrative && !trader && !levels ? (
            <p className="text-sm text-muted">{error}</p>
          ) : tab === "ma" ? (
            narrative ? (
              <MarkdownViewer text={narrative} />
            ) : (
              <p className="text-sm text-muted">No Market Analyst report saved.</p>
            )
          ) : tab === "trader" ? (
            trader ? (
              <TraderPanel trader={trader} />
            ) : (
              <p className="text-sm text-muted">
                No trader report yet. Run Process zones to save trader.json.
              </p>
            )
          ) : levels ? (
            <LevelsTable levels={levels} />
          ) : (
            <p className="text-sm text-muted">No structured levels (pm_summary) found.</p>
          )}
        </div>
      </div>
    </div>
  );
}
