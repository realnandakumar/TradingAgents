import fs from "fs";
import os from "os";
import path from "path";

import type {
  TechDeskBook,
  TechDeskPendingEntry,
  TechDeskPosition,
} from "@/lib/tech-desk-server";
import { computeTechDeskStats } from "@/lib/tech-desk-server";

const DEFAULT_BOOK = path.join(os.homedir(), ".tradingagents", "rs_desk", "positions.json");
const DEFAULT_PENDING = path.join(
  os.homedir(),
  ".tradingagents",
  "rs_desk",
  "pending_entries.json",
);
const DEFAULT_CLOSED_HISTORY = path.join(
  os.homedir(),
  ".tradingagents",
  "rs_desk",
  "closed_history.json",
);

export type RsDeskPosition = TechDeskPosition;
export type RsDeskPendingEntry = TechDeskPendingEntry;
export type RsDeskBook = TechDeskBook;

export function rsDeskBookPath(): string {
  return (
    process.env.RS_DESK_BOOK_PATH ??
    process.env.TRADINGAGENTS_RS_DESK_BOOK_PATH ??
    DEFAULT_BOOK
  );
}

export function rsDeskPendingPath(): string {
  return (
    process.env.RS_DESK_PENDING_PATH ??
    process.env.TRADINGAGENTS_RS_DESK_PENDING_PATH ??
    DEFAULT_PENDING
  );
}

export function rsDeskClosedHistoryPath(): string {
  return (
    process.env.RS_DESK_CLOSED_HISTORY_PATH ??
    process.env.TRADINGAGENTS_RS_DESK_CLOSED_HISTORY_PATH ??
    DEFAULT_CLOSED_HISTORY
  );
}

function tradeKey(p: TechDeskPosition): string {
  return `${p.ticker}|${p.screen_date}|${p.exit_date ?? ""}`;
}

export function readAllRsDeskClosedTrades(): TechDeskPosition[] {
  const book = readRsDeskBook();
  const fromBook = (book?.positions ?? []).filter((p) => p.status === "closed");

  let archived: TechDeskPosition[] = [];
  try {
    const raw = fs.readFileSync(rsDeskClosedHistoryPath(), "utf-8");
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

export function readRsDeskBook(): TechDeskBook | null {
  try {
    const raw = fs.readFileSync(rsDeskBookPath(), "utf-8");
    return JSON.parse(raw) as TechDeskBook;
  } catch {
    return null;
  }
}

export function readRsDeskPending(): TechDeskPendingEntry[] {
  try {
    const raw = fs.readFileSync(rsDeskPendingPath(), "utf-8");
    const data = JSON.parse(raw) as { pending?: TechDeskPendingEntry[] };
    return data.pending ?? [];
  } catch {
    return [];
  }
}

export { computeTechDeskStats as computeRsDeskStats };
