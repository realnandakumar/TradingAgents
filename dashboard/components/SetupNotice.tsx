import Link from "next/link";

export function SetupNotice() {
  return (
    <div className="card p-8 text-center">
      <h2 className="text-lg font-semibold">No local data yet</h2>
      <p className="text-muted mt-2 max-w-md mx-auto text-sm">
        This dashboard reads paper books and screens from{" "}
        <code className="text-accent">~/.tradingagents/</code> on your machine. Use{" "}
        <Link href="/command-center" className="text-accent hover:underline">
          Command center
        </Link>{" "}
        to run an RS screen or strategy daily jobs — no Supabase required.
      </p>
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  showCommandCenter = true,
}: {
  title: string;
  hint?: string;
  showCommandCenter?: boolean;
}) {
  return (
    <div className="card p-10 text-center">
      <div className="text-foreground font-medium">{title}</div>
      {hint ? <div className="text-muted text-sm mt-1 max-w-md mx-auto">{hint}</div> : null}
      {showCommandCenter ? (
        <Link
          href="/command-center"
          className="inline-block mt-3 text-sm text-accent hover:underline"
        >
          Open Command center →
        </Link>
      ) : null}
    </div>
  );
}
