import fs from "fs";
import os from "os";
import path from "path";

const DEFAULT_BOOK = path.join(os.homedir(), ".tradingagents", "tech_desk", "positions.json");
const DEFAULT_PENDING = path.join(os.homedir(), ".tradingagents", "tech_desk", "pending_entries.json");
const DEFAULT_CLOSED_HISTORY = path.join(
  os.homedir(),
  ".tradingagents",
  "tech_desk",
  "closed_history.json",
);

export function techDeskBookPath(): string {
  return (
    process.env.TECH_DESK_BOOK_PATH ??
    process.env.TRADINGAGENTS_TECH_DESK_BOOK_PATH ??
    DEFAULT_BOOK
  );
}

export function techDeskPendingPath(): string {
  return (
    process.env.TECH_DESK_PENDING_PATH ??
    process.env.TRADINGAGENTS_TECH_DESK_PENDING_PATH ??
    DEFAULT_PENDING
  );
}

export interface TechDeskPosition {
  ticker: string;
  screen_date: string;
  entry_price: number;
  shares: number;
  notional?: number;
  alloc?: number;
  stop_loss: number;
  stop_loss_pct: number;
  target_1: number;
  target_1_pct?: number;
  target_2?: number | null;
  holding_days?: number;
  confidence?: number;
  bias?: string;
  report_path?: string | null;
  report_date?: string | null;
  status: "open" | "closed";
  raw_return?: number | null;
  rupee_pnl?: number | null;
  exit_reason?: string | null;
  exit_date?: string | null;
  trading_days_held?: number | null;
  partial_exits?: Array<{
    date?: string;
    price?: number;
    pct?: number;
    reason?: string;
    return?: number;
    rupee_pnl?: number;
  }>;
}

export interface TechDeskPendingEntry {
  ticker: string;
  zone_low?: number;
  zone_high?: number;
  stop_loss: number;
  target_1: number;
  confidence?: number;
  report_date?: string | null;
}

export interface TechDeskBook {
  strategy: string;
  updated_at: string;
  positions: TechDeskPosition[];
}

export function closedHistoryPath(): string {
  return (
    process.env.TECH_DESK_CLOSED_HISTORY_PATH ??
    process.env.TRADINGAGENTS_TECH_DESK_CLOSED_HISTORY_PATH ??
    DEFAULT_CLOSED_HISTORY
  );
}

function tradeKey(p: TechDeskPosition): string {
  return `${p.ticker}|${p.screen_date}|${p.exit_date ?? ""}`;
}

/** All closed trades: append-only archive merged with current book (deduped). */
export function readAllClosedTrades(): TechDeskPosition[] {
  const book = readTechDeskBook();
  const fromBook = (book?.positions ?? []).filter((p) => p.status === "closed");

  let archived: TechDeskPosition[] = [];
  try {
    const raw = fs.readFileSync(closedHistoryPath(), "utf-8");
    const data = JSON.parse(raw) as { trades?: TechDeskPosition[] };
    archived = (data.trades ?? []).map((t) => ({ ...t, status: "closed" as const }));
  } catch {
    archived = [];
  }

  const byKey = new Map<string, TechDeskPosition>();
  for (const t of [...archived, ...fromBook]) {
    byKey.set(tradeKey(t), t);
  }

  return Array.from(byKey.values()).sort((a, b) =>
    (b.exit_date ?? b.screen_date).localeCompare(a.exit_date ?? a.screen_date),
  );
}

export function readTechDeskBook(): TechDeskBook | null {
  try {
    const raw = fs.readFileSync(techDeskBookPath(), "utf-8");
    return JSON.parse(raw) as TechDeskBook;
  } catch {
    return null;
  }
}

export function readTechDeskPending(): TechDeskPendingEntry[] {
  try {
    const raw = fs.readFileSync(techDeskPendingPath(), "utf-8");
    const data = JSON.parse(raw) as { pending?: TechDeskPendingEntry[] };
    return data.pending ?? [];
  } catch {
    return [];
  }
}

export function computeTechDeskStats(positions: TechDeskPosition[]) {
  const closed = positions.filter((p) => p.status === "closed");
  const open = positions.filter((p) => p.status === "open");
  if (closed.length === 0) {
    return {
      trades: 0,
      winRate: null as number | null,
      avgReturn: null as number | null,
      avgR: null as number | null,
      totalPnl: 0,
      openCount: open.length,
    };
  }
  const wins = closed.filter((p) => (p.raw_return ?? 0) > 0).length;
  const avgReturn =
    closed.reduce((s, p) => s + (p.raw_return ?? 0), 0) / closed.length;
  const totalPnl = closed.reduce((s, p) => s + (p.rupee_pnl ?? 0), 0);
  const rMultiples = closed
    .map((p) => {
      const entry = p.entry_price;
      const stop = p.stop_loss;
      const ext = (p as TechDeskPosition & { exit_price?: number }).exit_price;
      if (ext == null || entry <= stop) return null;
      return (ext - entry) / (entry - stop);
    })
    .filter((r): r is number => r != null);
  return {
    trades: closed.length,
    winRate: (100 * wins) / closed.length,
    avgReturn: avgReturn * 100,
    avgR: rMultiples.length ? rMultiples.reduce((a, b) => a + b, 0) / rMultiples.length : null,
    totalPnl,
    openCount: open.length,
  };
}
