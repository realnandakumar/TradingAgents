import { CommandCenter } from "@/components/CommandCenter";
import { getPortfolioDeskSummaries } from "@/lib/command-center-server";
import { listRecentJobs } from "@/lib/desk-cli-server";

export const dynamic = "force-dynamic";

export default function CommandCenterPage() {
  const portfolioDesks = getPortfolioDeskSummaries();
  const recentJobs = listRecentJobs(5);

  return (
    <CommandCenter portfolioDesks={portfolioDesks} recentJobs={recentJobs} />
  );
}
