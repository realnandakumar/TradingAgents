import { DeskActionsPanel } from "@/components/DeskActionsPanel";
import { CandidatesTable } from "@/components/CandidatesTable";
import { EmptyState } from "@/components/SetupNotice";
import { getScreens } from "@/lib/paper-server";
import { timeAgo } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function ScreensPage() {
  const screens = getScreens(30);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Screen history</h1>
        <p className="text-muted text-sm">
          Each run: high-RS NSE stocks ranked by technical signals, then deep-analyzed by the AI.
        </p>
      </div>

      <DeskActionsPanel deskId="screens" />

      {screens.length === 0 ? (
        <EmptyState
          title="No screens published yet"
          hint="Use Run screen in Desk actions above, or Quick actions on Overview."
        />
      ) : (
        screens.map((s) => {
          const opened = s.data.opened?.length ?? 0;
          return (
            <section key={s.id} className="card p-5">
              <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                <h2 className="font-medium">
                  {s.data.trade_date}
                  <span className="text-muted font-normal text-sm">
                    {" "}
                    · {s.data.candidates.length} picks · {opened} paper-traded
                  </span>
                </h2>
                <span className="text-muted text-xs">{timeAgo(s.created_at)}</span>
              </div>
              <CandidatesTable candidates={s.data.candidates} />
            </section>
          );
        })
      )}
    </div>
  );
}
