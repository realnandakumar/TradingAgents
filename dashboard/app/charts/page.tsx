import { Suspense } from "react";

import { ChartWorkspace } from "@/components/charts/ChartWorkspace";

export const dynamic = "force-dynamic";

export default function ChartsPage() {
  return (
    <div className="-mx-4 sm:-mx-6 max-w-none">
      <Suspense
        fallback={
          <div className="card mx-4 sm:mx-6 p-12 text-center text-muted text-sm">
            Loading charts…
          </div>
        }
      >
        <ChartWorkspace />
      </Suspense>
    </div>
  );
}
