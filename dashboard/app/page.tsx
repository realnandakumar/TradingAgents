import { CandidatesTable } from "@/components/CandidatesTable";
import { OverviewQuickActions } from "@/components/OverviewQuickActions";
import { ReliabilityChart } from "@/components/ReliabilityChart";
import { EmptyState } from "@/components/SetupNotice";
import { StatCard } from "@/components/StatCard";
import { getLatestPaper, getLatestScreen } from "@/lib/paper-server";
import { computeRsDeskStats, readAllRsDeskClosedTrades, readRsDeskBook } from "@/lib/rs-desk-server";
import { inr, pct, timeAgo } from "@/lib/format";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const paper = getLatestPaper();
  const screen = getLatestScreen();
  const rsBook = readRsDeskBook();
  const rsStats = computeRsDeskStats(readAllRsDeskClosedTrades());
  const rsOpenCount = (rsBook?.positions ?? []).filter((p) => p.status === "open").length;
  const legacyOpenCount = (paper?.data.positions ?? []).filter((p) => p.status === "open").length;
  const stats = paper?.data.stats;

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Overview</h1>
          <p className="text-muted text-sm">
            High relative-strength NSE stocks, AI-vetted, paper-traded for reliability.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted">
          {rsBook?.updated_at ? <span>RS book updated {timeAgo(rsBook.updated_at)}</span> : null}
          <Link href="/data-health" className="text-accent hover:underline">
            Data health
          </Link>
        </div>
      </div>

      <OverviewQuickActions />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Win rate"
          value={rsStats.winRate != null ? `${rsStats.winRate.toFixed(0)}%` : "—"}
          sub={`${rsStats.trades} closed RS trades`}
          tone={rsStats.winRate != null && rsStats.winRate >= 50 ? "bull" : "default"}
        />
        <StatCard
          label="Avg return"
          value={pct(rsStats.avgReturn)}
          sub="per closed trade"
          tone={rsStats.avgReturn != null ? (rsStats.avgReturn >= 0 ? "bull" : "bear") : "default"}
        />
        <StatCard
          label="Avg R"
          value={rsStats.avgR != null ? rsStats.avgR.toFixed(2) : "—"}
          sub="risk multiple"
          tone={rsStats.avgR != null ? (rsStats.avgR >= 0 ? "bull" : "bear") : "default"}
        />
        <StatCard
          label="Realized P&L"
          value={inr(rsStats.totalPnl)}
          sub={`${rsOpenCount} open RS positions`}
          tone={rsStats.totalPnl ? (rsStats.totalPnl >= 0 ? "bull" : "bear") : "default"}
        />
      </div>
      {rsOpenCount > 0 || legacyOpenCount > 0 ? (
        <p className="text-xs text-muted -mt-4">
          <Link href="/positions" className="text-accent hover:underline">
            {rsOpenCount > 0
              ? "View open RS positions →"
              : `View ${legacyOpenCount} legacy paper position${legacyOpenCount === 1 ? "" : "s"} →`}
          </Link>
          {rsOpenCount > 0 && legacyOpenCount > 0 ? (
            <span>
              {" "}
              · {legacyOpenCount} legacy still open
            </span>
          ) : null}
        </p>
      ) : null}

      <section className="card p-5">
        <h2 className="font-medium mb-1">Legacy RS reliability by signal</h2>
        <p className="text-muted text-xs mb-3">
          Win rate of closed paper trades, grouped by which technical signal fired.
        </p>
        {stats ? <ReliabilityChart stats={stats} /> : <EmptyState title="No legacy paper data yet" />}
      </section>

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
            hint="Use Quick actions above to run an RS screen from the dashboard."
          />
        )}
      </section>
    </div>
  );
}
