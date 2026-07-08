import { CandidatesTable } from "@/components/CandidatesTable";
import { ReliabilityChart } from "@/components/ReliabilityChart";
import { EmptyState } from "@/components/SetupNotice";
import { StatCard } from "@/components/StatCard";
import { getLatestPaper, getLatestScreen } from "@/lib/paper-server";
import { inr, pct, timeAgo } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const paper = getLatestPaper();
  const screen = getLatestScreen();
  const stats = paper?.data.stats;
  const o = stats?.overall;

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
          <p className="text-muted text-sm">
            High relative-strength NSE stocks, AI-vetted, paper-traded for reliability.
          </p>
        </div>
        {paper && <span className="text-muted text-xs">Updated {timeAgo(paper.created_at)}</span>}
      </div>

      {/* Reliability stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Win rate"
          value={o?.win_rate != null ? `${o.win_rate}%` : "—"}
          sub={`${o?.trades ?? 0} closed trades`}
          tone={o?.win_rate != null && o.win_rate >= 50 ? "bull" : "default"}
        />
        <StatCard
          label="Avg return"
          value={pct(o?.avg_return)}
          sub="per closed trade"
          tone={o?.avg_return != null ? (o.avg_return >= 0 ? "bull" : "bear") : "default"}
        />
        <StatCard
          label="Avg alpha vs Nifty"
          value={pct(o?.avg_alpha)}
          sub="excess vs benchmark"
          tone={o?.avg_alpha != null ? (o.avg_alpha >= 0 ? "bull" : "bear") : "default"}
        />
        <StatCard
          label="Realized P&L"
          value={inr(o?.total_pnl)}
          sub={`${stats?.open_positions ?? 0} open positions`}
          tone={o?.total_pnl ? (o.total_pnl >= 0 ? "bull" : "bear") : "default"}
        />
      </div>

      {/* Reliability by signal */}
      <section className="card p-5">
        <h2 className="font-medium mb-1">Reliability by signal</h2>
        <p className="text-muted text-xs mb-3">
          Win rate of closed paper trades, grouped by which technical signal fired. This is how we
          learn which patterns actually predict winners.
        </p>
        {stats ? <ReliabilityChart stats={stats} /> : <EmptyState title="No paper data yet" />}
      </section>

      {/* Latest screen */}
      <section className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium">Latest screen</h2>
          {screen && (
            <span className="text-muted text-xs">
              {screen.data.trade_date} · {screen.data.candidates.length} picks
            </span>
          )}
        </div>
        {screen && screen.data.candidates.length > 0 ? (
          <CandidatesTable candidates={screen.data.candidates} live />
        ) : (
          <EmptyState
            title="No screens yet"
            hint="Run `tradingagents screen` on your machine to publish picks here."
          />
        )}
      </section>
    </div>
  );
}
