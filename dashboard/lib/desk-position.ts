/** Shared desk position metadata (dates, qty, notional, days in trade). */

export interface PartialExitLeg {
  date?: string;
  price?: number;
  pct?: number;
  reason?: string;
  return?: number;
  rupee_pnl?: number;
}

export interface DeskPositionMeta {
  ticker: string;
  status?: "open" | "closed";
  entry_date?: string;
  screen_date?: string;
  exit_date?: string | null;
  entry_price?: number;
  exit_price?: number | null;
  shares?: number;
  notional?: number;
  alloc?: number;
  trading_days_held?: number | null;
  holding_days_actual?: number | null;
  raw_return?: number | null;
  alpha_return?: number | null;
  rupee_pnl?: number | null;
  exit_reason?: string | null;
  partial_exits?: PartialExitLeg[];
}

export function entryDate(p: DeskPositionMeta): string {
  return p.entry_date || p.screen_date || "—";
}

export function purchaseNotional(p: DeskPositionMeta): number {
  if (p.notional != null) return p.notional;
  const sh = p.shares ?? 0;
  const ep = p.entry_price ?? 0;
  return Math.round(sh * ep * 100) / 100;
}

export function slotBudget(p: DeskPositionMeta): number {
  return p.alloc ?? 0;
}

export function withinBudget(p: DeskPositionMeta, tolerance = 0.01): boolean {
  const alloc = slotBudget(p);
  if (alloc <= 0) return true;
  return purchaseNotional(p) <= alloc * (1 + tolerance);
}

function parseDay(s: string): Date {
  return new Date(`${s.slice(0, 10)}T12:00:00`);
}

export function tradingDaysBetweenCalendar(start: string, end: string): number {
  if (!start || !end) return 0;
  const s = parseDay(start);
  const e = parseDay(end);
  if (e < s) return 0;
  let count = 0;
  const d = new Date(s);
  while (d <= e) {
    const day = d.getDay();
    if (day !== 0 && day !== 6) count += 1;
    d.setDate(d.getDate() + 1);
  }
  return count;
}

export function asOfTradingDay(asOf?: string): string {
  const d = asOf ? parseDay(asOf) : new Date();
  while (d.getDay() === 0 || d.getDay() === 6) {
    d.setDate(d.getDate() - 1);
  }
  return d.toISOString().slice(0, 10);
}

export function daysInTrade(p: DeskPositionMeta, asOf?: string): number {
  const entry = entryDate(p);
  if (entry === "—") return 0;
  if (p.status === "closed") {
    if (p.trading_days_held != null) return p.trading_days_held;
    if (p.holding_days_actual != null) return p.holding_days_actual;
    if (p.exit_date) return tradingDaysBetweenCalendar(entry, p.exit_date);
    return 0;
  }
  return tradingDaysBetweenCalendar(entry, asOfTradingDay(asOf));
}

export function partialLegs(p: DeskPositionMeta): PartialExitLeg[] {
  return Array.isArray(p.partial_exits) ? p.partial_exits : [];
}
