"use client";

import { inr, pct, shortSymbol } from "@/lib/format";
import { useQuotes } from "@/lib/useQuotes";
import type { GapFillPosition } from "@/lib/gap-fill-server";
import { shortSector } from "@/lib/swing-types";

const MAX_POSITIONS = 10;
const MAX_HOLD_DAYS = 15;

function phaseLabel(phase?: string): string {
  return phase === "runner" ? "RUN" : "INIT";
}

function cushionPct(last: number | null, stop: number): number | null {
  if (last == null || last <= 0) return null;
  return ((last - stop) / last) * 100;
}

export function GapFillBlotter({ positions }: { positions: GapFillPosition[] }) {
  const { quotes, loading } = useQuotes(positions.map((p) => p.ticker));
  const open = positions.filter((p) => p.status === "open");

  let mtmSum = 0;
  let haveLive = false;

  const rows = open.map((p) => {
    const q = quotes[p.ticker];
    const live = q?.price ?? p.entry_price;
    const stop = p.trailing_stop ?? p.stop_loss;
    const rem = (p.remaining_pct ?? 100) / 100;
    const mtmPct = ((live - p.entry_price) / p.entry_price) * 100;
    const mtmAbs = (live - p.entry_price) * rem;
    if (q?.price != null) {
      mtmSum += mtmAbs;
      haveLive = true;
    }
    const cushion = cushionPct(live, stop);
    const tight = cushion != null && cushion < 7;
    return {
      p,
      live,
      stop,
      mtmPct,
      cushion,
      tight,
      gapAge: p.gap_age,
      gapPct: p.gap_pct,
      fillPct: p.fill_pct,
      fillTarget: p.fill_target,
    };
  });

  const avgRisk =
    open.reduce((s, p) => s + Math.abs(p.stop_loss_pct), 0) / (open.length || 1);
  const avgT2 = open.reduce((s, p) => s + p.target_2_pct, 0) / (open.length || 1);

  return (
    <div className="space-y-0">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 border-b border-border bg-surface-2/50">
        {[
          { label: "Open", value: `${open.length}/${MAX_POSITIONS}`, sub: "slots" },
          {
            label: "MTM P&L",
            value: haveLive ? inr(mtmSum) : loading ? "…" : inr(0),
            sub: "per share",
            tone: haveLive ? (mtmSum >= 0 ? "text-bull" : "text-bear") : "text-muted",
          },
          { label: "Slots free", value: String(MAX_POSITIONS - open.length), sub: "capacity" },
          { label: "Avg risk", value: pct(-avgRisk), sub: "to stop", tone: "text-bear" },
          { label: "Avg T2", value: pct(avgT2, 2), sub: "upside", tone: "text-bull" },
          { label: "Max hold", value: `${MAX_HOLD_DAYS}d`, sub: "time exit" },
        ].map((k) => (
          <div key={k.label} className="px-4 py-3 border-r border-border/60 last:border-r-0">
            <div className="text-[10px] uppercase tracking-wider text-muted">{k.label}</div>
            <div className={`text-lg font-semibold tabular-nums ${k.tone ?? ""}`}>{k.value}</div>
            <div className="text-[10px] text-muted">{k.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-[1fr_240px]">
        <div className="border-r border-border min-w-0">
          <div className="px-4 py-2.5 border-b border-border/60 flex items-center gap-2 text-xs">
            <span className="font-medium uppercase tracking-wide">Position blotter</span>
            <span className="text-muted">{open.length} lines</span>
            <span className="ml-auto text-muted">1D · Gap Fill · 15-day hold</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-muted uppercase border-b border-border bg-surface-2/30">
                  <th className="text-left py-2 px-3">SYM</th>
                  <th className="text-right py-2 px-2">Age</th>
                  <th className="text-right py-2 px-2">Gap%</th>
                  <th className="text-right py-2 px-2">Fill%</th>
                  <th className="text-right py-2 px-2">Last</th>
                  <th className="text-right py-2 px-2">Tgt</th>
                  <th className="text-right py-2 px-2">MTM</th>
                  <th className="text-right py-2 px-2">Stop</th>
                  <th className="text-right py-2 px-2">Cush</th>
                  <th className="text-right py-2 px-2">T2</th>
                  <th className="text-center py-2 px-2">Ph</th>
                  <th className="text-left py-2 px-3">Sector</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(({ p, live, stop, mtmPct, cushion, tight, gapAge, gapPct, fillPct, fillTarget }) => (
                  <tr
                    key={p.ticker}
                    className={`border-b border-border/40 hover:bg-surface-2/40 ${
                      tight ? "bg-bear/5" : ""
                    }`}
                  >
                    <td className="py-2 px-3 font-medium">{shortSymbol(p.ticker)}</td>
                    <td className="py-2 px-2 text-right tabular-nums">{gapAge ?? "—"}</td>
                    <td className="py-2 px-2 text-right tabular-nums">
                      {gapPct != null ? pct(gapPct, 1) : "—"}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums">
                      {fillPct != null ? `${fillPct.toFixed(0)}%` : "—"}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums">{inr(live)}</td>
                    <td className="py-2 px-2 text-right tabular-nums text-muted">
                      {fillTarget != null ? inr(fillTarget) : "—"}
                    </td>
                    <td
                      className={`py-2 px-2 text-right tabular-nums ${
                        mtmPct >= 0 ? "text-bull" : "text-bear"
                      }`}
                    >
                      {pct(mtmPct, 1)}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums text-bear">{inr(stop)}</td>
                    <td className="py-2 px-2 text-right tabular-nums">
                      {cushion != null ? pct(cushion, 1) : "—"}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums text-bull">
                      {pct(p.target_2_pct, 1)}
                    </td>
                    <td className="py-2 px-2 text-center">{phaseLabel(p.phase)}</td>
                    <td className="py-2 px-3 text-muted truncate max-w-[100px]">
                      {shortSector(p.sector)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="p-4 space-y-4 text-xs">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted mb-2">Remarks</div>
            {rows.length === 0 ? (
              <p className="text-muted">No open positions.</p>
            ) : (
              <ul className="space-y-2 font-mono text-[10px] leading-snug">
                {rows.map(({ p, mtmPct }) => (
                  <li key={p.ticker} className="border-b border-border/30 pb-2">
                    <div className="font-medium">{shortSymbol(p.ticker)}</div>
                    <div className="text-muted">{p.remark ?? "—"}</div>
                    <div className={mtmPct >= 0 ? "text-bull" : "text-bear"}>
                      {pct(mtmPct, 1)}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
