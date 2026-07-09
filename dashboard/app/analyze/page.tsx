import { AnalyzePanel } from "@/components/AnalyzePanel";
import { listReports } from "@/lib/analyze-server";

export const dynamic = "force-dynamic";

export default function AnalyzePage() {
  const reports = listReports();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">AI Analyze</h1>
        <p className="text-sm text-muted mt-1">
          Run the multi-agent trading analysis pipeline on any ticker. Reports are saved under{" "}
          <code className="text-accent text-xs">~/.tradingagents/analyze/reports</code>.
        </p>
      </div>
      <AnalyzePanel initialReports={reports} />
    </div>
  );
}
