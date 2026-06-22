type Tone = "default" | "bull" | "bear";

export function StatCard({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: Tone;
}) {
  const valueColor =
    tone === "bull" ? "text-bull" : tone === "bear" ? "text-bear" : "text-foreground";
  return (
    <div className="card p-4 sm:p-5">
      <div className="text-muted text-xs uppercase tracking-wide">{label}</div>
      <div className={`mt-2 text-2xl sm:text-3xl font-semibold tabular-nums ${valueColor}`}>
        {value}
      </div>
      {sub && <div className="text-muted text-xs mt-1">{sub}</div>}
    </div>
  );
}
