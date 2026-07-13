import Link from "next/link";

import {
  getCrossDeskPnl,
  getDataHealthMeta,
  getDataHealthRows,
} from "@/lib/data-health-server";
import { getPortfolioDeskSummaries } from "@/lib/command-center-server";

export const dynamic = "force-dynamic";

function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
  } catch {
    return iso;
  }
}

export default function DataHealthPage() {
  const rows = getDataHealthRows();
  const meta = getDataHealthMeta();
  const desks = getPortfolioDeskSummaries();
  const crossDesk = getCrossDeskPnl();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Data health</h1>
        <p className="text-muted text-sm mt-1">
          Local filesystem data used by the dashboard — paths, freshness, and API readiness.
        </p>
      </div>

      <section className="card p-5">
        <h2 className="text-sm font-medium mb-3">Environment</h2>
        <dl className="grid sm:grid-cols-2 gap-3 text-xs">
          <div>
            <dt className="text-muted">TRADINGAGENTS_HOME</dt>
            <dd className="font-mono mt-0.5 break-all">{meta.tradingagentsHome}</dd>
          </div>
          <div>
            <dt className="text-muted">LLM API ({meta.apiKey.provider})</dt>
            <dd className={meta.apiKey.configured ? "text-bull" : "text-bear"}>
              {meta.apiKey.configured ? "Configured" : meta.apiKey.message}
            </dd>
          </div>
        </dl>
      </section>

      <section className="card overflow-hidden">
        <div className="px-5 py-3 border-b border-border">
          <h2 className="text-sm font-medium">Data files</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-muted uppercase border-b border-border bg-surface-2/30">
                <th className="text-left py-2 px-4">Source</th>
                <th className="text-left py-2 px-4">Status</th>
                <th className="text-left py-2 px-4">Updated</th>
                <th className="text-left py-2 px-4">Detail</th>
                <th className="text-left py-2 px-4">Path</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border/40">
                  <td className="py-2 px-4 font-medium">{r.label}</td>
                  <td className={`py-2 px-4 ${r.exists ? "text-bull" : "text-bear"}`}>
                    {r.exists ? "OK" : "Missing"}
                  </td>
                  <td className="py-2 px-4 tabular-nums text-muted">{formatWhen(r.updatedAt)}</td>
                  <td className="py-2 px-4 text-muted">{r.detail}</td>
                  <td className="py-2 px-4 font-mono text-[10px] text-muted max-w-[200px] truncate">
                    {r.path}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card p-5">
        <h2 className="text-sm font-medium mb-3">Portfolio desks — open slots</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {desks.map((d) => (
            <Link
              key={d.id}
              href={d.href}
              className="rounded-lg border border-border px-3 py-2 hover:bg-surface-2/50 transition-colors"
            >
              <div className="text-sm font-medium">{d.label}</div>
              <div className="text-xs text-muted mt-0.5">
                {d.openCount != null ? `${d.openCount} open` : "No book"}
              </div>
            </Link>
          ))}
        </div>
        <p className="text-xs text-muted mt-3">
          Cross-desk realized P&amp;L aggregation: see each desk&apos;s closed ledger or Tech Desk
          pipeline for detailed stats.
        </p>
      </section>

      <p className="text-xs text-muted">
        Data is read from local JSON under{" "}
        <code className="text-accent">~/.tradingagents/</code> — not Supabase. Run jobs from{" "}
        <Link href="/command-center" className="text-accent hover:underline">
          Command center
        </Link>
        .
      </p>
    </div>
  );
}
