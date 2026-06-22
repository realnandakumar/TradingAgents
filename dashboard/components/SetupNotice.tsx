export function SetupNotice() {
  return (
    <div className="card p-8 text-center">
      <h2 className="text-lg font-semibold">Connect your data</h2>
      <p className="text-muted mt-2 max-w-md mx-auto text-sm">
        This dashboard reads from Supabase. Set{" "}
        <code className="text-accent">NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
        <code className="text-accent">NEXT_PUBLIC_SUPABASE_ANON_KEY</code>, then run a screen on your
        machine to publish results. See <code>dashboard/SETUP.md</code>.
      </p>
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="card p-10 text-center">
      <div className="text-foreground font-medium">{title}</div>
      {hint && <div className="text-muted text-sm mt-1">{hint}</div>}
    </div>
  );
}
