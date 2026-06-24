import { ratingTone, SIGNAL_ABBREV, SIGNAL_TONE, signalLabel } from "@/lib/format";

export function RatingBadge({ rating }: { rating: string | null }) {
  if (!rating) return <span className="text-muted">—</span>;
  const tone = ratingTone(rating);
  const cls =
    tone === "bull"
      ? "bg-bull/15 text-bull border-bull/30"
      : tone === "bear"
      ? "bg-bear/15 text-bear border-bear/30"
      : "bg-surface-2 text-muted border-border";
  return (
    <span className={`inline-block px-2 py-0.5 rounded-md text-xs font-medium border ${cls}`}>
      {rating}
    </span>
  );
}

export function SignalBadge({ signal, abbrev = false }: { signal: string; abbrev?: boolean }) {
  const tone = SIGNAL_TONE[signal] ?? "approx";
  const cls =
    tone === "reliable"
      ? "bg-accent/12 text-accent border-accent/25"
      : "bg-surface-2 text-muted border-border";
  const text = abbrev ? SIGNAL_ABBREV[signal] ?? signalLabel(signal) : signalLabel(signal);
  return (
    <span
      className={`inline-block px-1.5 py-0.5 rounded text-[11px] leading-none border ${cls}`}
      title={`${signalLabel(signal)} — ${tone === "reliable" ? "reliable signal" : "approximate / heuristic pattern"}`}
    >
      {text}
    </span>
  );
}

export function SignalList({ signals, abbrev = false }: { signals: string[]; abbrev?: boolean }) {
  if (!signals || signals.length === 0) return <span className="text-muted text-xs">none</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {signals.map((s) => (
        <SignalBadge key={s} signal={s} abbrev={abbrev} />
      ))}
    </div>
  );
}
