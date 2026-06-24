// Display helpers shared across the dashboard.

export function pct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

// Stats already arrive as percentages (e.g. 12.5 = 12.5%); returns on positions
// arrive as fractions (0.10 = 10%). Use `fromFraction` for the latter.
export function pctFromFraction(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return "—";
  return pct(v * 100, digits);
}

export function inr(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(v);
}

export function qty(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(v);
}

export function signalLabel(s: string): string {
  return s
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export const SIGNAL_TONE: Record<string, "reliable" | "approx"> = {
  rsi_breakout: "reliable",
  volume_surge: "reliable",
  breakout_soon: "reliable",
  ascending_triangle: "approx",
  cup_and_handle: "approx",
  pullback_in_uptrend: "approx",
};

// Short chips so the signals column stays one line; full name shown on hover.
export const SIGNAL_ABBREV: Record<string, string> = {
  rsi_breakout: "RSI",
  volume_surge: "Vol",
  breakout_soon: "Sqz",
  ascending_triangle: "Tri",
  cup_and_handle: "Cup",
  pullback_in_uptrend: "Pull",
};

export function ratingTone(rating: string | null): "bull" | "bear" | "neutral" {
  if (rating === "Buy" || rating === "Overweight") return "bull";
  if (rating === "Sell" || rating === "Underweight") return "bear";
  return "neutral";
}

export function shortSymbol(sym: string): string {
  return sym.replace(/\.NS$/, "");
}

// Format an ISO timestamp in IST (so all viewers see market-local time),
// e.g. "21 Jun, 8:36 PM". Returns "—" for null/invalid input.
export function dateTimeIST(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(d);
}

export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime();
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}
